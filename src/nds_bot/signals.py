from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from itertools import pairwise

from nds_bot.models import (
    Candle,
    CycleDirection,
    TradeSide,
)
from nds_bot.pipeline import CycleAnalysis
from nds_bot.replay import (
    ReplayEvent,
    ReplayResult,
)


@dataclass(frozen=True)
class SignalPolicy:
    """
    Map confirmed cycle directions to trading sides.

    The default policy is a reversal strategy:
        BULL cycle -> SELL
        BEAR cycle -> BUY
    """

    bull_cycle_side: TradeSide = TradeSide.SELL
    bear_cycle_side: TradeSide = TradeSide.BUY

    def side_for(
        self,
        direction: CycleDirection,
    ) -> TradeSide:
        if direction is CycleDirection.BULL:
            return self.bull_cycle_side

        if direction is CycleDirection.BEAR:
            return self.bear_cycle_side

        raise ValueError(f"Unsupported cycle direction: {direction}")


@dataclass(frozen=True)
class TradeSignal:
    """
    A trading signal generated from a valid replay event.

    The reference price is the close price of the confirmation
    candle. It is not yet an executed trade price.
    """

    side: TradeSide
    generated_at_index: int
    generated_at_time: datetime
    reference_price: float
    analysis: CycleAnalysis

    def __post_init__(self) -> None:
        if self.generated_at_index < 0:
            raise ValueError("Signal index cannot be negative.")

        if self.reference_price <= 0:
            raise ValueError("Signal reference price must be positive.")

    @property
    def cycle_direction(self) -> CycleDirection:
        return self.analysis.cycle.direction

    @property
    def cycle_indexes(self) -> tuple[int, ...]:
        return tuple(node.index for node in self.analysis.cycle.nodes)

    @property
    def n3_price(self) -> float:
        return self.analysis.cycle.n3.price


def build_trade_signals(
    candles: Sequence[Candle],
    replay_result: ReplayResult,
    *,
    policy: SignalPolicy | None = None,
) -> tuple[TradeSignal, ...]:
    """
    Build trading signals from valid chronological replay events.

    Rejected replay events never produce trading signals.
    """
    active_policy = policy or SignalPolicy()

    _validate_candle_order(candles)

    signals: list[TradeSignal] = []

    for event in replay_result.valid_events:
        confirmation_candle = _get_confirmation_candle(
            candles,
            event,
        )

        signals.append(
            TradeSignal(
                side=active_policy.side_for(event.analysis.cycle.direction),
                generated_at_index=event.confirmed_at_index,
                generated_at_time=event.confirmed_at_time,
                reference_price=confirmation_candle.close,
                analysis=event.analysis,
            )
        )

    return tuple(signals)


def _get_confirmation_candle(
    candles: Sequence[Candle],
    event: ReplayEvent,
) -> Candle:
    index = event.confirmed_at_index

    if index < 0 or index >= len(candles):
        raise ValueError("Replay event confirmation index is outside the candle data.")

    candle = candles[index]

    if candle.time != event.confirmed_at_time:
        raise ValueError(
            "Replay event confirmation time does not match the candle at its confirmation index."
        )

    return candle


def _validate_candle_order(
    candles: Sequence[Candle],
) -> None:
    for current, next_candle in pairwise(candles):
        if current.time >= next_candle.time:
            raise ValueError("Candles must be ordered by increasing time.")
