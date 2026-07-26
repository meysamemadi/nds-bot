from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

from nds_bot.backtest.account import AccountPolicy
from nds_bot.backtest.contracts import ContractSpecification
from nds_bot.backtest.costs import TradingCostPolicy
from nds_bot.backtest.execution import (
    ExecutionPolicy,
    ExitReason,
    execute_signals,
)
from nds_bot.backtest.margin import MarginPolicy
from nds_bot.broker.base import BrokerAdapter
from nds_bot.broker.models import (
    PaperClosedTrade,
    PaperEquityPoint,
    PaperOrder,
    PaperOrderRequest,
    PaperOrderStatus,
    PaperPosition,
)
from nds_bot.broker.paper import PaperBroker
from nds_bot.models import Candle
from nds_bot.pipeline import ScanConfig
from nds_bot.replay import replay_candles
from nds_bot.signals import (
    SignalPolicy,
    TradeSignal,
    build_trade_signals,
)


@dataclass(frozen=True)
class PaperTradingMetrics:
    """Summary of one chronological paper-trading run."""

    candle_count: int
    order_count: int
    closed_order_count: int
    rejected_order_count: int
    cancelled_order_count: int
    open_position_count: int
    closed_trade_count: int
    winning_trade_count: int

    initial_balance: float
    ending_balance: float
    net_profit: float
    return_fraction: float
    maximum_drawdown_amount: float
    maximum_drawdown_fraction: float

    @property
    def win_rate(self) -> float:
        if self.closed_trade_count == 0:
            return 0.0

        return self.winning_trade_count / self.closed_trade_count


@dataclass(frozen=True)
class PaperTradingResult:
    """Complete output of an offline chronological paper session."""

    symbol: str
    signals: tuple[TradeSignal, ...]
    orders: tuple[PaperOrder, ...]
    open_positions: tuple[PaperPosition, ...]
    closed_trades: tuple[PaperClosedTrade, ...]
    equity_curve: tuple[PaperEquityPoint, ...]
    metrics: PaperTradingMetrics


def run_paper_trading(
    candles: Sequence[Candle],
    *,
    symbol: str,
    config: ScanConfig | None = None,
    signal_policy: SignalPolicy | None = None,
    execution_policy: ExecutionPolicy | None = None,
    account_policy: AccountPolicy | None = None,
    cost_policy: TradingCostPolicy | None = None,
    contract_specification: ContractSpecification | None = None,
    margin_policy: MarginPolicy | None = None,
    broker_adapter: BrokerAdapter | None = None,
) -> PaperTradingResult:
    """
    Replay candles one at a time through an in-memory paper broker.

    New signals create pending market orders. Orders fill only when the
    next candle exists. Positions remain open at the end of the supplied
    data instead of being force-closed at the last candle close.
    """
    if not symbol.strip():
        raise ValueError("Paper-trading symbol cannot be empty.")

    candle_tuple = tuple(candles)
    _validate_candle_order(candle_tuple)

    active_execution_policy = execution_policy or ExecutionPolicy()
    active_account_policy = account_policy or AccountPolicy()

    broker = broker_adapter or PaperBroker(
        account_policy=active_account_policy,
        cost_policy=cost_policy,
        contract_specification=contract_specification,
        margin_policy=margin_policy,
    )

    order_id_by_signal: dict[tuple[object, ...], str] = {}
    signal_by_key: dict[tuple[object, ...], TradeSignal] = {}

    for current_index in range(len(candle_tuple)):
        prefix = candle_tuple[: current_index + 1]
        replay_result = replay_candles(
            prefix,
            config=config,
        )
        signals = build_trade_signals(
            prefix,
            replay_result,
            policy=signal_policy,
        )

        for signal in signals:
            key = _signal_key(signal)

            if key in order_id_by_signal:
                continue

            order = broker.submit_order(
                PaperOrderRequest(
                    symbol=symbol,
                    signal=signal,
                )
            )
            order_id_by_signal[key] = order.order_id
            signal_by_key[key] = signal

        execution_result = execute_signals(
            prefix,
            signals,
            policy=active_execution_policy,
        )
        raw_trade_by_signal = {
            _signal_key(trade.signal): trade for trade in execution_result.trades
        }

        for order in broker.orders:
            if order.status is not PaperOrderStatus.PENDING:
                continue

            if order.scheduled_entry_index > current_index:
                continue

            raw_trade = raw_trade_by_signal.get(_signal_key(order.signal))

            if raw_trade is None:
                continue

            broker.open_position(
                order_id=order.order_id,
                raw_trade=raw_trade,
            )

        for position in broker.open_positions:
            raw_trade = raw_trade_by_signal.get(_signal_key(position.signal))

            if raw_trade is None:
                continue

            if raw_trade.exit_reason is ExitReason.END_OF_DATA:
                continue

            broker.close_position(
                position_id=position.position_id,
                raw_trade=raw_trade,
            )

    broker.cancel_pending_orders()

    metrics = _build_metrics(
        candle_count=len(candle_tuple),
        orders=broker.orders,
        open_positions=broker.open_positions,
        closed_trades=broker.closed_trades,
        equity_curve=broker.equity_curve,
        initial_balance=broker.initial_balance,
        ending_balance=broker.balance,
    )

    return PaperTradingResult(
        symbol=symbol,
        signals=tuple(signal_by_key.values()),
        orders=broker.orders,
        open_positions=broker.open_positions,
        closed_trades=broker.closed_trades,
        equity_curve=broker.equity_curve,
        metrics=metrics,
    )


def _build_metrics(
    *,
    candle_count: int,
    orders: tuple[PaperOrder, ...],
    open_positions: tuple[PaperPosition, ...],
    closed_trades: tuple[PaperClosedTrade, ...],
    equity_curve: tuple[PaperEquityPoint, ...],
    initial_balance: float,
    ending_balance: float,
) -> PaperTradingMetrics:
    maximum_drawdown_amount = max(point.drawdown_amount for point in equity_curve)
    maximum_drawdown_fraction = max(point.drawdown_fraction for point in equity_curve)

    return PaperTradingMetrics(
        candle_count=candle_count,
        order_count=len(orders),
        closed_order_count=sum(order.status is PaperOrderStatus.CLOSED for order in orders),
        rejected_order_count=sum(order.status is PaperOrderStatus.REJECTED for order in orders),
        cancelled_order_count=sum(order.status is PaperOrderStatus.CANCELLED for order in orders),
        open_position_count=len(open_positions),
        closed_trade_count=len(closed_trades),
        winning_trade_count=sum(trade.is_winner for trade in closed_trades),
        initial_balance=initial_balance,
        ending_balance=ending_balance,
        net_profit=ending_balance - initial_balance,
        return_fraction=ending_balance / initial_balance - 1,
        maximum_drawdown_amount=maximum_drawdown_amount,
        maximum_drawdown_fraction=maximum_drawdown_fraction,
    )


def _signal_key(
    signal: TradeSignal,
) -> tuple[object, ...]:
    return (
        signal.side,
        signal.generated_at_index,
        signal.cycle_indexes,
    )


def _validate_candle_order(
    candles: Sequence[Candle],
) -> None:
    for current, next_candle in pairwise(candles):
        if current.time >= next_candle.time:
            raise ValueError("Candles must be ordered by increasing time.")
