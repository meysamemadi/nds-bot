from dataclasses import dataclass

from nds_bot.quality.hook_ratio import HookRatios, calculate_hook_ratios
from nds_bot.quality.legs import CycleLegs
from nds_bot.quality.nsi import NsiResult, calculate_nsi


@dataclass(frozen=True)
class QualityThresholds:
    hook_ideal: float = 0.86
    hook_minimum: float = 0.25
    hook_maximum: float = 0.92
    maximum_nsi: float = 0.60

    def __post_init__(self) -> None:
        if self.hook_minimum < 0:
            raise ValueError("Minimum hook ratio cannot be negative.")

        if self.hook_maximum < self.hook_minimum:
            raise ValueError("Maximum hook ratio cannot be below minimum hook ratio.")

        if not self.hook_minimum <= self.hook_ideal <= self.hook_maximum:
            raise ValueError("Ideal hook ratio must be inside the accepted range.")

        if self.maximum_nsi < 0:
            raise ValueError("Maximum NSI cannot be negative.")


@dataclass(frozen=True)
class QualityAssessment:
    hook_ratios: HookRatios
    nsi: NsiResult
    first_hook_valid: bool
    second_hook_valid: bool
    nsi_valid: bool

    @property
    def hooks_valid(self) -> bool:
        return self.first_hook_valid and self.second_hook_valid

    @property
    def is_valid(self) -> bool:
        return self.hooks_valid and self.nsi_valid


def evaluate_cycle_quality(
    legs: CycleLegs,
    *,
    thresholds: QualityThresholds | None = None,
) -> QualityAssessment:
    """
    Evaluate the hook ratios and NSI of an NDS cycle.
    """
    active_thresholds = thresholds or QualityThresholds()

    hook_ratios = calculate_hook_ratios(legs)
    nsi = calculate_nsi(legs)

    first_hook_valid = (
        active_thresholds.hook_minimum <= hook_ratios.first <= active_thresholds.hook_maximum
    )

    second_hook_valid = (
        active_thresholds.hook_minimum <= hook_ratios.second <= active_thresholds.hook_maximum
    )

    nsi_valid = nsi.score <= active_thresholds.maximum_nsi

    return QualityAssessment(
        hook_ratios=hook_ratios,
        nsi=nsi,
        first_hook_valid=first_hook_valid,
        second_hook_valid=second_hook_valid,
        nsi_valid=nsi_valid,
    )
