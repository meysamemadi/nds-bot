import pytest

from nds_bot.quality.displacement import log_displacement


def test_upward_log_displacement() -> None:
    result = log_displacement(100.0, 150.0)

    assert result == pytest.approx(0.405465, abs=1e-6)


def test_downward_log_displacement() -> None:
    result = log_displacement(150.0, 100.0)

    assert result == pytest.approx(-0.405465, abs=1e-6)


def test_equal_prices_have_zero_displacement() -> None:
    result = log_displacement(100.0, 100.0)

    assert result == pytest.approx(0.0, abs=1e-12)


def test_round_trip_displacements_cancel_each_other() -> None:
    upward = log_displacement(100.0, 150.0)
    downward = log_displacement(150.0, 100.0)

    assert upward + downward == pytest.approx(0.0, abs=1e-12)


@pytest.mark.parametrize(
    ("start_price", "end_price"),
    [
        (0.0, 100.0),
        (-1.0, 100.0),
        (100.0, 0.0),
        (100.0, -1.0),
    ],
)
def test_non_positive_prices_are_rejected(
    start_price: float,
    end_price: float,
) -> None:
    with pytest.raises(ValueError):
        log_displacement(start_price, end_price)
