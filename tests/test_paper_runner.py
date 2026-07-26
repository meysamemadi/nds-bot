from pathlib import Path

import pytest

from nds_bot.backtest.account import AccountPolicy
from nds_bot.backtest.costs import TradingCostPolicy
from nds_bot.broker.models import PaperOrderStatus
from nds_bot.data.csv_loader import load_candles_csv
from nds_bot.paper.runner import run_paper_trading
from nds_bot.pipeline import ScanConfig

SAMPLE_PATH = Path("data/samples/documented_bull_cycle_execution.csv")


def test_paper_runner_closes_documented_trade() -> None:
    candles = load_candles_csv(SAMPLE_PATH)

    result = run_paper_trading(
        candles,
        symbol="EURUSD",
        config=ScanConfig(extrema_window=1),
        account_policy=AccountPolicy(
            initial_balance=10_000.0,
            risk_fraction=0.01,
        ),
    )

    assert len(result.signals) == 1
    assert len(result.orders) == 1
    assert result.orders[0].status is PaperOrderStatus.CLOSED
    assert result.open_positions == ()
    assert len(result.closed_trades) == 1
    assert result.metrics.ending_balance == pytest.approx(10_200.0)
    assert result.metrics.win_rate == pytest.approx(1.0)


def test_paper_runner_preserves_open_position_at_end() -> None:
    candles = load_candles_csv(SAMPLE_PATH)[:14]

    result = run_paper_trading(
        candles,
        symbol="EURUSD",
        config=ScanConfig(extrema_window=1),
    )

    assert len(result.orders) == 1
    assert result.orders[0].status is PaperOrderStatus.OPEN
    assert len(result.open_positions) == 1
    assert result.closed_trades == ()
    assert result.metrics.ending_balance == pytest.approx(10_000.0)


def test_paper_runner_cancels_order_without_entry_candle() -> None:
    candles = load_candles_csv(SAMPLE_PATH)[:13]

    result = run_paper_trading(
        candles,
        symbol="EURUSD",
        config=ScanConfig(extrema_window=1),
    )

    assert len(result.orders) == 1
    assert result.orders[0].status is PaperOrderStatus.CANCELLED
    assert result.open_positions == ()
    assert result.closed_trades == ()


def test_paper_runner_applies_trading_costs() -> None:
    candles = load_candles_csv(SAMPLE_PATH)

    result = run_paper_trading(
        candles,
        symbol="EURUSD",
        config=ScanConfig(extrema_window=1),
        cost_policy=TradingCostPolicy(
            spread_fraction=0.0002,
            slippage_fraction=0.00005,
            commission_fraction=0.0001,
        ),
    )

    trade = result.closed_trades[0]

    assert trade.total_cost_amount > 0
    assert trade.net_monetary_pnl < 200.0
    assert result.metrics.ending_balance < 10_200.0
