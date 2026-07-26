import csv
from pathlib import Path

import pytest

from nds_bot.data.csv_loader import load_candles_csv
from nds_bot.data.paper_csv import (
    write_paper_equity_csv,
    write_paper_orders_csv,
    write_paper_trades_csv,
)
from nds_bot.paper.runner import run_paper_trading
from nds_bot.pipeline import ScanConfig

SAMPLE_PATH = Path("data/samples/documented_bull_cycle_execution.csv")


def test_writes_paper_session_csv_files(
    tmp_path: Path,
) -> None:
    candles = load_candles_csv(SAMPLE_PATH)
    result = run_paper_trading(
        candles,
        symbol="EURUSD",
        config=ScanConfig(extrema_window=1),
    )

    orders_path = write_paper_orders_csv(
        result.orders,
        tmp_path / "orders.csv",
    )
    trades_path = write_paper_trades_csv(
        result.closed_trades,
        tmp_path / "trades.csv",
    )
    equity_path = write_paper_equity_csv(
        result.equity_curve,
        tmp_path / "equity.csv",
    )

    with orders_path.open(encoding="utf-8", newline="") as file:
        orders = list(csv.DictReader(file))

    with trades_path.open(encoding="utf-8", newline="") as file:
        trades = list(csv.DictReader(file))

    with equity_path.open(encoding="utf-8", newline="") as file:
        equity = list(csv.DictReader(file))

    assert len(orders) == 1
    assert orders[0]["status"] == "CLOSED"
    assert len(trades) == 1
    assert trades[0]["symbol"] == "EURUSD"
    assert float(trades[0]["net_r_multiple"]) == pytest.approx(2.0)
    assert len(equity) == 2


def test_empty_paper_exports_contain_headers(
    tmp_path: Path,
) -> None:
    paths = (
        write_paper_orders_csv([], tmp_path / "orders.csv"),
        write_paper_trades_csv([], tmp_path / "trades.csv"),
        write_paper_equity_csv([], tmp_path / "equity.csv"),
    )

    for path in paths:
        assert len(path.read_text(encoding="utf-8").splitlines()) == 1
