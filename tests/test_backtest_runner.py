from datetime import UTC, datetime, timedelta

import pytest

from nds_bot.backtest.execution import ExitReason
from nds_bot.backtest.runner import run_backtest
from nds_bot.models import Candle
from nds_bot.pipeline import ScanConfig

BASE_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def make_candle(
    index: int,
    *,
    open_price: float,
    high: float,
    low: float,
    close: float,
) -> Candle:
    return Candle(
        time=BASE_TIME + timedelta(hours=index),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=1_000.0,
    )


def make_flat_candle(
    index: int,
    price: float,
) -> Candle:
    return make_candle(
        index,
        open_price=price,
        high=price,
        low=price,
        close=price,
    )


def make_execution_candles() -> list[Candle]:
    prices = [
        1.08100,
        1.08000,
        1.08300,
        1.08650,
        1.08400,
        1.08230,
        1.08600,
        1.09100,
        1.08800,
        1.08600,
        1.09000,
        1.09480,
        1.09200,
    ]

    candles = [make_flat_candle(index, price) for index, price in enumerate(prices)]

    candles.extend(
        [
            make_candle(
                13,
                open_price=1.09100,
                high=1.09300,
                low=1.08800,
                close=1.08900,
            ),
            make_candle(
                14,
                open_price=1.08900,
                high=1.09000,
                low=1.08200,
                close=1.08400,
            ),
        ]
    )

    return candles


def test_runner_builds_complete_winning_backtest() -> None:
    candles = make_execution_candles()

    result = run_backtest(
        candles,
        config=ScanConfig(extrema_window=1),
    )

    assert len(result.replay.events) == 1
    assert len(result.signals) == 1
    assert len(result.execution.trades) == 1
    assert result.execution.unfilled_signals == ()

    trade = result.execution.trades[0]

    assert trade.exit_reason is ExitReason.TAKE_PROFIT
    assert trade.r_multiple == pytest.approx(2.0)

    assert result.metrics.trade_count == 1
    assert result.metrics.winner_count == 1
    assert result.metrics.loser_count == 0
    assert result.metrics.win_rate == pytest.approx(1.0)
    assert result.metrics.total_r == pytest.approx(2.0)
    assert result.metrics.maximum_drawdown_r == pytest.approx(0.0)


def test_runner_preserves_unfilled_signal() -> None:
    candles = make_execution_candles()[:13]

    result = run_backtest(
        candles,
        config=ScanConfig(extrema_window=1),
    )

    assert len(result.signals) == 1
    assert result.execution.trades == ()
    assert len(result.execution.unfilled_signals) == 1
    assert result.metrics.trade_count == 0
