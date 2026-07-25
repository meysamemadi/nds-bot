import pytest

from nds_bot.backtest.performance import (
    calculate_backtest_metrics,
    calculate_maximum_drawdown_r,
)


def test_empty_metrics_are_zero() -> None:
    metrics = calculate_backtest_metrics([])

    assert metrics.trade_count == 0
    assert metrics.winner_count == 0
    assert metrics.loser_count == 0
    assert metrics.breakeven_count == 0
    assert metrics.win_rate == pytest.approx(0.0)
    assert metrics.total_r == pytest.approx(0.0)
    assert metrics.maximum_drawdown_r == pytest.approx(0.0)


def test_all_winning_results_have_no_drawdown() -> None:
    drawdown = calculate_maximum_drawdown_r([2.0, 1.0, 0.5])

    assert drawdown == pytest.approx(0.0)


def test_maximum_drawdown_uses_peak_to_trough() -> None:
    drawdown = calculate_maximum_drawdown_r([2.0, -1.0, -1.0, 2.0])

    assert drawdown == pytest.approx(2.0)


def test_initial_losses_create_drawdown_from_zero() -> None:
    drawdown = calculate_maximum_drawdown_r([-1.0, -1.0, 2.0])

    assert drawdown == pytest.approx(2.0)
