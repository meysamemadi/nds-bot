import pytest

from nds_bot.models import NDSCycle
from nds_bot.quality.legs import CycleLegs, calculate_cycle_legs
from nds_bot.quality.validation import (
    QualityThresholds,
    evaluate_cycle_quality,
)


def test_documented_cycle_passes_default_quality(
    bull_cycle: NDSCycle,
) -> None:
    legs = calculate_cycle_legs(bull_cycle)

    result = evaluate_cycle_quality(legs)

    assert result.first_hook_valid is True
    assert result.second_hook_valid is True
    assert result.nsi_valid is True
    assert result.is_valid is True


def test_first_hook_below_minimum_is_rejected() -> None:
    legs = CycleLegs(
        delta_1=2.0,
        delta_2=-0.4,
        delta_3=2.0,
        delta_4=-1.0,
        delta_5=2.0,
    )

    result = evaluate_cycle_quality(legs)

    assert result.hook_ratios.first == pytest.approx(0.2)
    assert result.first_hook_valid is False
    assert result.is_valid is False


def test_second_hook_above_maximum_is_rejected() -> None:
    legs = CycleLegs(
        delta_1=2.0,
        delta_2=-1.0,
        delta_3=2.0,
        delta_4=-2.0,
        delta_5=2.0,
    )

    result = evaluate_cycle_quality(legs)

    assert result.hook_ratios.second == pytest.approx(1.0)
    assert result.second_hook_valid is False
    assert result.is_valid is False


def test_high_nsi_is_rejected_even_when_hooks_are_valid() -> None:
    legs = CycleLegs(
        delta_1=0.4,
        delta_2=-0.2,
        delta_3=1.9,
        delta_4=-1.0,
        delta_5=0.35,
    )

    result = evaluate_cycle_quality(legs)

    assert result.hooks_valid is True
    assert result.nsi.score > 0.60
    assert result.nsi_valid is False
    assert result.is_valid is False


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (
            {"hook_minimum": -0.1},
            "Minimum hook ratio cannot be negative",
        ),
        (
            {
                "hook_minimum": 0.9,
                "hook_maximum": 0.5,
            },
            "Maximum hook ratio cannot be below minimum hook ratio",
        ),
        (
            {
                "hook_minimum": 0.25,
                "hook_ideal": 1.0,
                "hook_maximum": 0.92,
            },
            "Ideal hook ratio must be inside the accepted range",
        ),
        (
            {"maximum_nsi": -0.1},
            "Maximum NSI cannot be negative",
        ),
    ],
)
def test_invalid_quality_thresholds_are_rejected(
    kwargs: dict[str, float],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        QualityThresholds(**kwargs)
