from dataclasses import dataclass

from nds_bot.models import NDSCycle
from nds_bot.quality.legs import CycleLegs, calculate_cycle_legs


@dataclass(frozen=True)
class HookRatios:
    first: float
    second: float

    @property
    def values(self) -> tuple[float, float]:
        return (
            self.first,
            self.second,
        )

    @property
    def mean(self) -> float:
        return (self.first + self.second) / 2


def calculate_hook_ratios(legs: CycleLegs) -> HookRatios:
    """
    Calculate correction-to-impulse ratios for an NDS cycle.

    First hook:
        abs(delta_2) / abs(delta_1)

    Second hook:
        abs(delta_4) / abs(delta_3)
    """
    return HookRatios(
        first=_calculate_retracement_ratio(
            impulse=legs.delta_1,
            correction=legs.delta_2,
        ),
        second=_calculate_retracement_ratio(
            impulse=legs.delta_3,
            correction=legs.delta_4,
        ),
    )


def calculate_cycle_hook_ratios(cycle: NDSCycle) -> HookRatios:
    """
    Calculate hook ratios directly from an NDS cycle.
    """
    legs = calculate_cycle_legs(cycle)

    return calculate_hook_ratios(legs)


def _calculate_retracement_ratio(
    *,
    impulse: float,
    correction: float,
) -> float:
    if impulse == 0:
        raise ValueError("Impulse displacement cannot be zero.")

    return abs(correction) / abs(impulse)
