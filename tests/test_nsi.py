import pytest

from nds_bot.models import NDSCycle
from nds_bot.quality.legs import CycleLegs, calculate_cycle_legs
from nds_bot.quality.nsi import calculate_nsi


def test_calculates_healthy_cycle_nsi(
    bull_cycle: NDSCycle,
) -> None:
    legs = calculate_cycle_legs(bull_cycle)

    result = calculate_nsi(legs)

    assert result.score == pytest.approx(
        0.15226019001237984,
        abs=1e-12,
    )


def test_calculates_documented_unhealthy_nsi() -> None:
    legs = CycleLegs(
        delta_1=0.0040,
        delta_2=-0.0010,
        delta_3=0.0190,
        delta_4=-0.0150,
        delta_5=0.0035,
    )

    result = calculate_nsi(legs)

    assert result.score == pytest.approx(
        1.745098039215686,
        abs=1e-12,
    )


def test_nsi_uses_leg_magnitudes() -> None:
    alternating_legs = CycleLegs(
        delta_1=0.006,
        delta_2=-0.004,
        delta_3=0.008,
        delta_4=-0.005,
        delta_5=0.0081,
    )

    positive_legs = CycleLegs(
        delta_1=0.006,
        delta_2=0.004,
        delta_3=0.008,
        delta_4=0.005,
        delta_5=0.0081,
    )

    alternating_result = calculate_nsi(alternating_legs)
    positive_result = calculate_nsi(positive_legs)

    assert alternating_result.score == pytest.approx(positive_result.score)


def test_nsi_exposes_three_comparison_differences() -> None:
    legs = CycleLegs(
        delta_1=1.0,
        delta_2=-0.5,
        delta_3=1.5,
        delta_4=-0.75,
        delta_5=1.25,
    )

    result = calculate_nsi(legs)

    assert result.comparison_differences == pytest.approx(
        (
            0.5,
            0.25,
            0.25,
        )
    )


def test_zero_mean_leg_magnitude_is_rejected() -> None:
    legs = CycleLegs(
        delta_1=0.0,
        delta_2=0.0,
        delta_3=0.0,
        delta_4=0.0,
        delta_5=0.0,
    )

    with pytest.raises(
        ValueError,
        match="Mean leg magnitude cannot be zero",
    ):
        calculate_nsi(legs)
