from dataclasses import dataclass
from statistics import fmean

from nds_bot.quality.legs import CycleLegs


@dataclass(frozen=True)
class NsiResult:
    score: float
    comparison_differences: tuple[float, float, float]
    mean_leg_magnitude: float
    mean_comparison_difference: float


def calculate_nsi(legs: CycleLegs) -> NsiResult:
    """
    Calculate the Nodal Symmetry Index for a five-leg NDS cycle.

    Comparisons:
        abs(|delta_1| - |delta_3|)
        abs(|delta_2| - |delta_4|)
        abs(|delta_3| - |delta_5|)

    NSI:
        mean(comparison differences) / mean(leg magnitudes)
    """
    delta_1, delta_2, delta_3, delta_4, delta_5 = legs.magnitudes

    comparison_differences = (
        abs(delta_1 - delta_3),
        abs(delta_2 - delta_4),
        abs(delta_3 - delta_5),
    )

    mean_leg_magnitude = fmean(legs.magnitudes)

    if mean_leg_magnitude == 0:
        raise ValueError("Mean leg magnitude cannot be zero.")

    mean_comparison_difference = fmean(comparison_differences)
    score = mean_comparison_difference / mean_leg_magnitude

    return NsiResult(
        score=score,
        comparison_differences=comparison_differences,
        mean_leg_magnitude=mean_leg_magnitude,
        mean_comparison_difference=mean_comparison_difference,
    )
