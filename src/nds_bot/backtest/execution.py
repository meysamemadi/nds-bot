from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from itertools import pairwise
from statistics import fmean

from nds_bot.models import Candle, TradeSide
from nds_bot.signals import TradeSignal


class ExitReason(str, Enum):
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    END_OF_DATA = "END_OF_DATA"


class IntrabarPriority(str, Enum):
    """
    Define which level is assumed to be hit first when both
    Stop Loss and Take Profit are inside the same OHLC candle.
    """

    STOP_FIRST = "STOP_FIRST"
    TAKE_PROFIT_FIRST = "TAKE_PROFIT_FIRST"


@dataclass(frozen=True)
class ExecutionPolicy:
    """
    Engineering choices used by the execution simulator.

    reward_to_risk:
        Target distance divided by stop distance.

    stop_buffer_fraction:
        Optional fractional buffer beyond N3.

    intrabar_priority:
        Resolution rule when Stop Loss and Take Profit are both
        touched by one candle.
    """

    reward_to_risk: float = 2.0
    stop_buffer_fraction: float = 0.0
    intrabar_priority: IntrabarPriority = IntrabarPriority.STOP_FIRST

    def __post_init__(self) -> None:
        if self.reward_to_risk <= 0:
            raise ValueError("Reward-to-risk ratio must be positive.")

        if not 0 <= self.stop_buffer_fraction < 1:
            raise ValueError("Stop buffer fraction must be between 0 and 1.")


@dataclass(frozen=True)
class ExecutedTrade:
    """
    One signal executed on the next candle open.

    PnL values are expressed in price units, not account currency.
    """

    signal: TradeSignal

    entry_index: int
    entry_time: datetime
    entry_price: float

    stop_loss: float
    take_profit: float

    exit_index: int
    exit_time: datetime
    exit_price: float
    exit_reason: ExitReason

    def __post_init__(self) -> None:
        if self.entry_index < 0:
            raise ValueError("Trade entry index cannot be negative.")

        if self.exit_index < self.entry_index:
            raise ValueError("Trade exit cannot occur before entry.")

        if (
            min(
                self.entry_price,
                self.stop_loss,
                self.take_profit,
                self.exit_price,
            )
            <= 0
        ):
            raise ValueError("Trade prices must be positive.")

        if self.side is TradeSide.BUY and not (
            self.stop_loss < self.entry_price < self.take_profit
        ):
            raise ValueError("BUY trade levels must satisfy stop_loss < entry_price < take_profit.")

        if self.side is TradeSide.SELL and not (
            self.take_profit < self.entry_price < self.stop_loss
        ):
            raise ValueError(
                "SELL trade levels must satisfy take_profit < entry_price < stop_loss."
            )

    @property
    def side(self) -> TradeSide:
        return self.signal.side

    @property
    def risk_per_unit(self) -> float:
        return abs(self.entry_price - self.stop_loss)

    @property
    def price_pnl(self) -> float:
        """
        Return profit or loss in raw price units.

        This is not monetary PnL because quantity and account size
        have not been introduced yet.
        """
        if self.side is TradeSide.BUY:
            return self.exit_price - self.entry_price

        return self.entry_price - self.exit_price

    @property
    def return_fraction(self) -> float:
        return self.price_pnl / self.entry_price

    @property
    def r_multiple(self) -> float:
        return self.price_pnl / self.risk_per_unit

    @property
    def is_winner(self) -> bool:
        return self.price_pnl > 0

    @property
    def holding_candles(self) -> int:
        return self.exit_index - self.entry_index + 1


@dataclass(frozen=True)
class ExecutionResult:
    """
    Complete output of signal execution.

    A signal is unfilled when no candle exists after its
    generation candle.
    """

    trades: tuple[ExecutedTrade, ...]
    unfilled_signals: tuple[TradeSignal, ...]

    @property
    def winning_trades(self) -> tuple[ExecutedTrade, ...]:
        return tuple(trade for trade in self.trades if trade.is_winner)

    @property
    def losing_trades(self) -> tuple[ExecutedTrade, ...]:
        return tuple(trade for trade in self.trades if not trade.is_winner)

    @property
    def total_price_pnl(self) -> float:
        return sum(trade.price_pnl for trade in self.trades)

    @property
    def win_rate(self) -> float:
        if not self.trades:
            return 0.0

        return len(self.winning_trades) / len(self.trades)

    @property
    def mean_r_multiple(self) -> float:
        if not self.trades:
            return 0.0

        return fmean(trade.r_multiple for trade in self.trades)


def execute_signals(
    candles: Sequence[Candle],
    signals: Sequence[TradeSignal],
    *,
    policy: ExecutionPolicy | None = None,
) -> ExecutionResult:
    """
    Execute each signal at the next candle open.

    Signals are processed independently. Position overlap and
    account-level risk management are not handled in this stage.
    """
    active_policy = policy or ExecutionPolicy()

    _validate_candle_order(candles)
    _validate_signal_order(signals)

    trades: list[ExecutedTrade] = []
    unfilled_signals: list[TradeSignal] = []

    for signal in signals:
        _validate_signal_generation(
            candles,
            signal,
        )

        entry_index = signal.generated_at_index + 1

        if entry_index >= len(candles):
            unfilled_signals.append(signal)
            continue

        trades.append(
            _execute_signal(
                candles,
                signal,
                entry_index=entry_index,
                policy=active_policy,
            )
        )

    return ExecutionResult(
        trades=tuple(trades),
        unfilled_signals=tuple(unfilled_signals),
    )


def _execute_signal(
    candles: Sequence[Candle],
    signal: TradeSignal,
    *,
    entry_index: int,
    policy: ExecutionPolicy,
) -> ExecutedTrade:
    entry_candle = candles[entry_index]
    entry_price = entry_candle.open

    stop_loss, take_profit = _build_trade_levels(
        signal,
        entry_price=entry_price,
        policy=policy,
    )

    (
        exit_index,
        exit_price,
        exit_reason,
    ) = _find_exit(
        candles,
        side=signal.side,
        entry_index=entry_index,
        stop_loss=stop_loss,
        take_profit=take_profit,
        intrabar_priority=policy.intrabar_priority,
    )

    return ExecutedTrade(
        signal=signal,
        entry_index=entry_index,
        entry_time=entry_candle.time,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        exit_index=exit_index,
        exit_time=candles[exit_index].time,
        exit_price=exit_price,
        exit_reason=exit_reason,
    )


def _build_trade_levels(
    signal: TradeSignal,
    *,
    entry_price: float,
    policy: ExecutionPolicy,
) -> tuple[float, float]:
    n3_price = signal.n3_price
    buffer = policy.stop_buffer_fraction

    if signal.side is TradeSide.SELL:
        stop_loss = n3_price * (1 + buffer)

        if stop_loss <= entry_price:
            raise ValueError("SELL stop loss must be above entry price.")

        risk = stop_loss - entry_price

        take_profit = entry_price - risk * policy.reward_to_risk

    else:
        stop_loss = n3_price * (1 - buffer)

        if stop_loss >= entry_price:
            raise ValueError("BUY stop loss must be below entry price.")

        risk = entry_price - stop_loss

        take_profit = entry_price + risk * policy.reward_to_risk

    if take_profit <= 0:
        raise ValueError("Calculated take-profit price must be positive.")

    return stop_loss, take_profit


def _find_exit(
    candles: Sequence[Candle],
    *,
    side: TradeSide,
    entry_index: int,
    stop_loss: float,
    take_profit: float,
    intrabar_priority: IntrabarPriority,
) -> tuple[int, float, ExitReason]:
    for index in range(
        entry_index,
        len(candles),
    ):
        candle = candles[index]

        stop_hit, take_profit_hit = _detect_hits(
            candle,
            side=side,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

        if stop_hit and take_profit_hit:
            if intrabar_priority is IntrabarPriority.STOP_FIRST:
                return (
                    index,
                    stop_loss,
                    ExitReason.STOP_LOSS,
                )

            return (
                index,
                take_profit,
                ExitReason.TAKE_PROFIT,
            )

        if stop_hit:
            return (
                index,
                stop_loss,
                ExitReason.STOP_LOSS,
            )

        if take_profit_hit:
            return (
                index,
                take_profit,
                ExitReason.TAKE_PROFIT,
            )

    last_index = len(candles) - 1
    last_candle = candles[last_index]

    return (
        last_index,
        last_candle.close,
        ExitReason.END_OF_DATA,
    )


def _detect_hits(
    candle: Candle,
    *,
    side: TradeSide,
    stop_loss: float,
    take_profit: float,
) -> tuple[bool, bool]:
    if side is TradeSide.BUY:
        stop_hit = candle.low <= stop_loss
        take_profit_hit = candle.high >= take_profit
    else:
        stop_hit = candle.high >= stop_loss
        take_profit_hit = candle.low <= take_profit

    return stop_hit, take_profit_hit


def _validate_signal_generation(
    candles: Sequence[Candle],
    signal: TradeSignal,
) -> None:
    index = signal.generated_at_index

    if index < 0 or index >= len(candles):
        raise ValueError("Signal generation index is outside the candle data.")

    if candles[index].time != signal.generated_at_time:
        raise ValueError(
            "Signal generation time does not match the candle at its generation index."
        )


def _validate_candle_order(
    candles: Sequence[Candle],
) -> None:
    for current, next_candle in pairwise(candles):
        if current.time >= next_candle.time:
            raise ValueError("Candles must be ordered by increasing time.")


def _validate_signal_order(
    signals: Sequence[TradeSignal],
) -> None:
    for current, next_signal in pairwise(signals):
        if current.generated_at_index > next_signal.generated_at_index:
            raise ValueError("Signals must be ordered by increasing generation index.")
