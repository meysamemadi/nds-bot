import csv
from pathlib import Path

import pytest

from nds_bot.cli import main


def test_cli_runs_offline_paper_session(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    orders_path = tmp_path / "paper_orders.csv"
    trades_path = tmp_path / "paper_trades.csv"
    equity_path = tmp_path / "paper_equity.csv"

    exit_code = main(
        [
            "paper",
            "--csv",
            "data/samples/documented_bull_cycle_execution.csv",
            "--config",
            "config/default.yaml",
            "--extrema-window",
            "1",
            "--symbol",
            "EURUSD",
            "--orders-output",
            str(orders_path),
            "--trades-output",
            str(trades_path),
            "--equity-output",
            str(equity_path),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert orders_path.is_file()
    assert trades_path.is_file()
    assert equity_path.is_file()
    assert "NDS paper trading completed" in captured.out
    assert "Closed trades: 1" in captured.out
    assert "Open positions: 0" in captured.out
    assert captured.err == ""

    with trades_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert len(rows) == 1
    assert rows[0]["symbol"] == "EURUSD"


def test_cli_paper_reports_missing_csv(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        [
            "paper",
            "--csv",
            str(tmp_path / "missing.csv"),
            "--orders-output",
            str(tmp_path / "orders.csv"),
            "--trades-output",
            str(tmp_path / "trades.csv"),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "CSV file does not exist" in captured.err
