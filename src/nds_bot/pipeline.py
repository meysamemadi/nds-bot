from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import pairwise

from nds_bot.models import Candle, NDSCycle, Node
from nds_bot.quality.legs import CycleLegs, calculate_cycle_legs
from nds_bot.quality.validation import (
    QualityAssessment,
    QualityThresholds,
    evaluate_cycle_quality,
)
from nds_bot.topology.candidates import build_alternating_nodes
from nds_bot.topology.extrema import detect_local_extrema
from nds_bot.topology.sequences import detect_nds_cycles


@dataclass(frozen=True)
class ScanConfig:
    """
    Runtime configuration for the NDS scanning pipeline.
    """

    extrema_window: int = 6
    quality_thresholds: QualityThresholds = field(default_factory=QualityThresholds)

    def __post_init__(self) -> None:
        if self.extrema_window < 1:
            raise ValueError("Extrema window must be at least 1.")


@dataclass(frozen=True)
class CycleAnalysis:
    """
    Complete analysis result for one detected NDS cycle.
    """

    cycle: NDSCycle
    legs: CycleLegs
    quality: QualityAssessment

    @property
    def is_valid(self) -> bool:
        return self.quality.is_valid

    @property
    def rejection_reasons(self) -> tuple[str, ...]:
        reasons: list[str] = []

        if not self.quality.first_hook_valid:
            reasons.append("first_hook")

        if not self.quality.second_hook_valid:
            reasons.append("second_hook")

        if not self.quality.nsi_valid:
            reasons.append("nsi")

        return tuple(reasons)


@dataclass(frozen=True)
class ScanResult:
    """
    Complete output of one NDS market scan.
    """

    raw_nodes: tuple[Node, ...]
    alternating_nodes: tuple[Node, ...]
    cycles: tuple[NDSCycle, ...]
    analyses: tuple[CycleAnalysis, ...]

    @property
    def valid_analyses(self) -> tuple[CycleAnalysis, ...]:
        return tuple(analysis for analysis in self.analyses if analysis.is_valid)

    @property
    def rejected_analyses(self) -> tuple[CycleAnalysis, ...]:
        return tuple(analysis for analysis in self.analyses if not analysis.is_valid)


def scan_candles(
    candles: Sequence[Candle],
    *,
    config: ScanConfig | None = None,
) -> ScanResult:
    """
    Run the complete NDS detection and quality-analysis pipeline.

    Processing stages:
        1. Validate chronological candle order.
        2. Detect local peaks and troughs.
        3. Normalize extrema into alternating nodes.
        4. Detect six-node NDS cycles.
        5. Calculate cycle legs.
        6. Evaluate hook ratios and NSI.
    """
    active_config = config or ScanConfig()

    _validate_candle_order(candles)

    raw_nodes = detect_local_extrema(
        candles,
        window=active_config.extrema_window,
    )

    alternating_nodes = build_alternating_nodes(raw_nodes)
    cycles = detect_nds_cycles(alternating_nodes)

    analyses = tuple(
        _analyze_cycle(
            cycle,
            thresholds=active_config.quality_thresholds,
        )
        for cycle in cycles
    )

    return ScanResult(
        raw_nodes=tuple(raw_nodes),
        alternating_nodes=tuple(alternating_nodes),
        cycles=tuple(cycles),
        analyses=analyses,
    )


def _analyze_cycle(
    cycle: NDSCycle,
    *,
    thresholds: QualityThresholds,
) -> CycleAnalysis:
    legs = calculate_cycle_legs(cycle)

    quality = evaluate_cycle_quality(
        legs,
        thresholds=thresholds,
    )

    return CycleAnalysis(
        cycle=cycle,
        legs=legs,
        quality=quality,
    )


def _validate_candle_order(candles: Sequence[Candle]) -> None:
    for current, next_candle in pairwise(candles):
        if current.time >= next_candle.time:
            raise ValueError("Candles must be ordered by increasing time.")
