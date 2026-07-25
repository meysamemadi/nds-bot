import pytest

from nds_bot.models import NDSCycle
from nds_bot.quality.hook_ratio import (
    calculate_cycle_hook_ratios,
    calculate_hook_ratios,
)
from nds_bot.quality.legs import CycleLegs


def test_calculates_bull_cycle_hook_ratios(
    bull_cycle: NDSCycle,
) -> None:
    ratios = calculate_cycle_hook_ratios(bull_cycle)

    assert ratios.first == pytest.approx(
        0.6454674738736952,
        abs=1e-12,
    )
    assert ratios.second == pytest.approx(
        0.5737338138691839,
        abs=1e-12,
    )


def test_calculates_bear_cycle_hook_ratios(
    bear_cycle: NDSCycle,
) -> None:
    ratios = calculate_cycle_hook_ratios(bear_cycle)

    assert ratios.first == pytest.approx(
        0.6468309824092926,
        abs=1e-12,
    )
    assert ratios.second == pytest.approx(
        0.5756847020224563,
        abs=1e-12,
    )


def test_hook_ratios_use_absolute_values() -> None:
    legs = CycleLegs(
        delta_1=-2.0,
        delta_2=1.0,
        delta_3=4.0,
        delta_4=-1.0,
        delta_5=2.0,
    )

    ratios = calculate_hook_ratios(legs)

    assert ratios.first == pytest.approx(0.5)
    assert ratios.second == pytest.approx(0.25)


def test_hook_ratio_mean_is_calculated(
    bull_cycle: NDSCycle,
) -> None:
    ratios = calculate_cycle_hook_ratios(bull_cycle)

    expected_mean = (ratios.first + ratios.second) / 2

    assert ratios.mean == pytest.approx(expected_mean)


def test_hook_ratio_values_preserve_order(
    bull_cycle: NDSCycle,
) -> None:
    ratios = calculate_cycle_hook_ratios(bull_cycle)

    assert ratios.values == (
        ratios.first,
        ratios.second,
    )


@pytest.mark.parametrize(
    "legs",
    [
        CycleLegs(
            delta_1=0.0,
            delta_2=-1.0,
            delta_3=2.0,
            delta_4=-1.0,
            delta_5=2.0,
        ),
        CycleLegs(
            delta_1=2.0,
            delta_2=-1.0,
            delta_3=0.0,
            delta_4=-1.0,
            delta_5=2.0,
        ),
    ],
)
def test_zero_impulse_is_rejected(legs: CycleLegs) -> None:
    with pytest.raises(
        ValueError,
        match="Impulse displacement cannot be zero",
    ):
        calculate_hook_ratios(legs)
