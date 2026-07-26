import csv
from pathlib import Path

import pytest

from nds_bot.backtest.account import AccountPolicy
from nds_bot.backtest.portfolio import (
    PortfolioDataset,
    run_portfolio_backtest,
)
from nds_bot.data.csv_loader import load_candles_csv
from nds_bot.data.portfolio_csv import (
    write_portfolio_equity_csv,
    write_portfolio_summary_csv,
)
from nds_bot.pipeline import ScanConfig


def build_result():
    path = Path("data/samples/documented_bull_cycle_execution.csv")
    candles = tuple(load_candles_csv(path))

    datasets = (
        PortfolioDataset(
            dataset_id="eurusd-h1",
            symbol="EURUSD",
            timeframe="H1",
            candles=candles,
            config=ScanConfig(extrema_window=1),
        ),
        PortfolioDataset(
            dataset_id="gbpusd-h1",
            symbol="GBPUSD",
            timeframe="H1",
            candles=candles,
            config=ScanConfig(extrema_window=1),
        ),
    )

    return run_portfolio_backtest(
        datasets,
        account_policy=AccountPolicy(),
    )


def test_writes_portfolio_summary_csv(tmp_path: Path) -> None:
    output_path = write_portfolio_summary_csv(
        build_result(),
        tmp_path / "portfolio_summary.csv",
    )

    with output_path.open(
        encoding="utf-8",
        newline="",
    ) as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert len(rows) == 3
    assert rows[0]["record_type"] == "DATASET"
    assert rows[0]["dataset_id"] == "eurusd-h1"
    assert rows[-1]["record_type"] == "SUMMARY"
    assert float(rows[-1]["ending_balance"]) == pytest.approx(10_200.0)


def test_writes_combined_portfolio_equity_csv(
    tmp_path: Path,
) -> None:
    output_path = write_portfolio_equity_csv(
        build_result(),
        tmp_path / "portfolio_equity.csv",
    )

    with output_path.open(
        encoding="utf-8",
        newline="",
    ) as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert len(rows) == 2
    assert rows[0]["event_number"] == "0"
    assert rows[0]["time"] == ""
    assert float(rows[-1]["balance"]) == pytest.approx(10_200.0)
