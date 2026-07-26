from pathlib import Path

import pytest

from nds_bot.backtest.account import AccountPolicy
from nds_bot.backtest.portfolio import (
    PortfolioDataset,
    run_portfolio_backtest,
)
from nds_bot.data.csv_loader import load_candles_csv
from nds_bot.pipeline import ScanConfig

SAMPLE_PATH = Path("data/samples/documented_bull_cycle_execution.csv")


def build_dataset(
    dataset_id: str,
    *,
    weight: float = 1.0,
    symbol: str = "EURUSD",
    timeframe: str = "H1",
) -> PortfolioDataset:
    candles = load_candles_csv(SAMPLE_PATH)

    return PortfolioDataset(
        dataset_id=dataset_id,
        symbol=symbol,
        timeframe=timeframe,
        candles=tuple(candles),
        config=ScanConfig(extrema_window=1),
        allocation_weight=weight,
        source_path=SAMPLE_PATH,
    )


def test_portfolio_splits_initial_balance_by_weight() -> None:
    result = run_portfolio_backtest(
        [
            build_dataset("eurusd-h1", weight=3.0),
            build_dataset(
                "gbpusd-h1",
                weight=1.0,
                symbol="GBPUSD",
            ),
        ],
        account_policy=AccountPolicy(
            initial_balance=10_000.0,
            risk_fraction=0.01,
        ),
    )

    first, second = result.datasets

    assert first.allocated_balance == pytest.approx(7_500.0)
    assert second.allocated_balance == pytest.approx(2_500.0)
    assert first.normalized_weight == pytest.approx(0.75)
    assert second.normalized_weight == pytest.approx(0.25)

    assert first.ending_balance == pytest.approx(7_650.0)
    assert second.ending_balance == pytest.approx(2_550.0)

    assert result.metrics.initial_balance == pytest.approx(10_000.0)
    assert result.metrics.ending_balance == pytest.approx(10_200.0)
    assert result.metrics.net_profit == pytest.approx(200.0)
    assert result.metrics.return_fraction == pytest.approx(0.02)


def test_portfolio_groups_simultaneous_equity_events() -> None:
    result = run_portfolio_backtest(
        [
            build_dataset("eurusd-h1"),
            build_dataset(
                "eurusd-h4",
                timeframe="H4",
            ),
        ],
        account_policy=AccountPolicy(),
    )

    assert len(result.equity_curve) == 2
    assert result.equity_curve[0].time is None
    assert result.equity_curve[0].balance == pytest.approx(10_000.0)
    assert result.equity_curve[1].balance == pytest.approx(10_200.0)
    assert result.metrics.maximum_drawdown_fraction == pytest.approx(0.0)


def test_duplicate_portfolio_dataset_ids_are_rejected() -> None:
    dataset = build_dataset("duplicate")

    with pytest.raises(
        ValueError,
        match="dataset ids must be unique",
    ):
        run_portfolio_backtest(
            [dataset, dataset],
            account_policy=AccountPolicy(),
        )
