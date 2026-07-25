import pytest

from nds_bot.models import NDSCycle
from nds_bot.quality.legs import calculate_cycle_legs


def test_calculates_documented_bull_cycle_legs(
    bull_cycle: NDSCycle,
) -> None:
    legs = calculate_cycle_legs(bull_cycle)

    assert legs.values == pytest.approx(
        (
            0.006000479578218857,
            -0.0038731143953836212,
            0.00800630053196993,
            -0.004593485339189984,
            0.008070476672643111,
        ),
        abs=1e-12,
    )


def test_bull_cycle_has_expected_leg_signs(
    bull_cycle: NDSCycle,
) -> None:
    legs = calculate_cycle_legs(bull_cycle)

    assert legs.delta_1 > 0
    assert legs.delta_2 < 0
    assert legs.delta_3 > 0
    assert legs.delta_4 < 0
    assert legs.delta_5 > 0


def test_bear_cycle_has_expected_leg_signs(
    bear_cycle: NDSCycle,
) -> None:
    legs = calculate_cycle_legs(bear_cycle)

    assert legs.delta_1 < 0
    assert legs.delta_2 > 0
    assert legs.delta_3 < 0
    assert legs.delta_4 > 0
    assert legs.delta_5 < 0


def test_impulse_and_correction_legs_are_exposed(
    bull_cycle: NDSCycle,
) -> None:
    legs = calculate_cycle_legs(bull_cycle)

    assert legs.impulse_legs == (
        legs.delta_1,
        legs.delta_3,
        legs.delta_5,
    )

    assert legs.correction_legs == (
        legs.delta_2,
        legs.delta_4,
    )


def test_leg_magnitudes_are_absolute_values(
    bull_cycle: NDSCycle,
) -> None:
    legs = calculate_cycle_legs(bull_cycle)

    assert legs.magnitudes == tuple(abs(value) for value in legs.values)
