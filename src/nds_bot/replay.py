from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from itertools import pairwise

from nds_bot.models import Candle, CycleDirection
from nds_bot.pipeline import (
    CycleAnalysis,
    ScanConfig,
    scan_candles,
)


@dataclass(frozen=True)
class ReplayEvent:
    """
    A cycle discovered for the first time during chronological replay.
    """

    confirmed_at_index: int
    confirmed_at_time: datetime
    analysis: CycleAnalysis

    @property
    def cycle_indexes(self) -> tuple[int, ...]:
        """
        Return the candle indexes of Z, N1, S1, N2, S2, and N3.
        """
        return tuple(node.index for node in self.analysis.cycle.nodes)

    @property
    def is_valid(self) -> bool:
        return self.analysis.is_valid

    @property
    def rejection_reasons(self) -> tuple[str, ...]:
        return self.analysis.rejection_reasons


@dataclass(frozen=True)
class ReplayResult:
    """
    Complete output of a chronological candle replay.
    """

    events: tuple[ReplayEvent, ...]

    @property
    def valid_events(self) -> tuple[ReplayEvent, ...]:
        return tuple(event for event in self.events if event.is_valid)

    @property
    def rejected_events(self) -> tuple[ReplayEvent, ...]:
        return tuple(event for event in self.events if not event.is_valid)


def replay_candles(
    candles: Sequence[Candle],
    *,
    config: ScanConfig | None = None,
) -> ReplayResult:
    """
    Replay candles chronologically and emit each cycle once.

    A cycle is emitted when it appears for the first time using only
    candles available up to that replay step.
    """
    active_config = config or ScanConfig()

    _validate_candle_order(candles)

    if not candles:
        return ReplayResult(events=())

    minimum_prefix_size = (2 * active_config.extrema_window) + 1

    if len(candles) < minimum_prefix_size:
        return ReplayResult(events=())

    events: list[ReplayEvent] = []

    seen_cycles: set[
        tuple[
            CycleDirection,
            tuple[int, ...],
        ]
    ] = set()

    for prefix_size in range(
        minimum_prefix_size,
        len(candles) + 1,
    ):
        current_index = prefix_size - 1

        current_candles = candles[:prefix_size]

        scan_result = scan_candles(
            current_candles,
            config=active_config,
        )

        for analysis in scan_result.analyses:
            cycle_key = _build_cycle_key(analysis)

            if cycle_key in seen_cycles:
                continue

            seen_cycles.add(cycle_key)

            events.append(
                ReplayEvent(
                    confirmed_at_index=current_index,
                    confirmed_at_time=candles[current_index].time,
                    analysis=analysis,
                )
            )

    return ReplayResult(
        events=tuple(events),
    )


def _build_cycle_key(
    analysis: CycleAnalysis,
) -> tuple[
    CycleDirection,
    tuple[int, ...],
]:
    """
    Build a stable identity for one detected cycle.
    """
    cycle_indexes = tuple(node.index for node in analysis.cycle.nodes)

    return (
        analysis.cycle.direction,
        cycle_indexes,
    )


def _validate_candle_order(
    candles: Sequence[Candle],
) -> None:
    for current, next_candle in pairwise(candles):
        if current.time >= next_candle.time:
            raise ValueError("Candles must be ordered by increasing time.")
