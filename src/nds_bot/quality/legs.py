from dataclasses import dataclass

from nds_bot.models import NDSCycle
from nds_bot.quality.displacement import log_displacement


@dataclass(frozen=True)
class CycleLegs:
    delta_1: float
    delta_2: float
    delta_3: float
    delta_4: float
    delta_5: float

    @property
    def values(self) -> tuple[float, float, float, float, float]:
        return (
            self.delta_1,
            self.delta_2,
            self.delta_3,
            self.delta_4,
            self.delta_5,
        )

    @property
    def magnitudes(self) -> tuple[float, float, float, float, float]:
        return tuple(abs(value) for value in self.values)

    @property
    def impulse_legs(self) -> tuple[float, float, float]:
        return (
            self.delta_1,
            self.delta_3,
            self.delta_5,
        )

    @property
    def correction_legs(self) -> tuple[float, float]:
        return (
            self.delta_2,
            self.delta_4,
        )


def calculate_cycle_legs(cycle: NDSCycle) -> CycleLegs:
    """
    Calculate the five logarithmic displacements of an NDS cycle.
    """
    return CycleLegs(
        delta_1=log_displacement(cycle.z.price, cycle.n1.price),
        delta_2=log_displacement(cycle.n1.price, cycle.s1.price),
        delta_3=log_displacement(cycle.s1.price, cycle.n2.price),
        delta_4=log_displacement(cycle.n2.price, cycle.s2.price),
        delta_5=log_displacement(cycle.s2.price, cycle.n3.price),
    )
