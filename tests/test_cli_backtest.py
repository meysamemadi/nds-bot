import csv
from pathlib import Path

import pytest

from nds_bot.cli import main


def test_cli_runs_backtest_and_exports_trades(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "results" / "trades.csv"

    exit_code = main(
        [
            "backtest",
            "--csv",
            ("data/samples/documented_bull_cycle_execution.csv"),
            "--config",
            "config/default.yaml",
            "--extrema-window",
            "1",
            "--output",
            str(output_path),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert output_path.is_file()
    assert "NDS backtest completed" in captured.out
    assert "Executed trades: 1" in captured.out
    assert "Winners: 1" in captured.out
    assert "Win rate: 100.00%" in captured.out
    assert "Total R: 2.0000" in captured.out
    assert captured.err == ""

    with output_path.open(
        encoding="utf-8",
        newline="",
    ) as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert len(rows) == 1
    assert rows[0]["exit_reason"] == "TAKE_PROFIT"


def test_cli_backtest_reports_missing_csv(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "trades.csv"

    exit_code = main(
        [
            "backtest",
            "--csv",
            str(tmp_path / "missing.csv"),
            "--config",
            "config/default.yaml",
            "--output",
            str(output_path),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 1
    assert not output_path.exists()
    assert captured.out == ""
    assert "CSV file does not exist" in captured.err
