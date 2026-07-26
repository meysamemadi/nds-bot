import csv
from pathlib import Path

import pytest

from nds_bot.cli import main

SAMPLE_CSV = "data/samples/documented_bull_cycle_execution.csv"


def test_cli_enables_contract_sizing_and_exports_lots(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    trade_output = tmp_path / "trades.csv"

    exit_code = main(
        [
            "backtest",
            "--csv",
            SAMPLE_CSV,
            "--config",
            "config/default.yaml",
            "--extrema-window",
            "1",
            "--output",
            str(trade_output),
            "--spread-fraction",
            "0.0002",
            "--slippage-fraction",
            "0.00005",
            "--commission-fraction",
            "0.0001",
            "--contract-size",
            "100000",
            "--minimum-lot",
            "0.01",
            "--maximum-lot",
            "100",
            "--lot-step",
            "0.01",
            "--below-minimum-lot-policy",
            "SKIP",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Contract sizing: enabled" in captured.out
    assert "Contract size: 100000.00000000" in captured.out
    assert "Skipped minimum-lot trades: 0" in captured.out
    assert "Mean risk utilization: 99.97%" in captured.out
    assert captured.err == ""

    with trade_output.open(
        encoding="utf-8",
        newline="",
    ) as csv_file:
        row = next(csv.DictReader(csv_file))

    assert float(row["lots"]) == pytest.approx(0.23)
    assert float(row["quantity"]) == pytest.approx(23_000.0)


def test_cli_preserves_unconstrained_sizing_by_default(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    trade_output = tmp_path / "trades.csv"

    exit_code = main(
        [
            "backtest",
            "--csv",
            SAMPLE_CSV,
            "--config",
            "config/default.yaml",
            "--extrema-window",
            "1",
            "--output",
            str(trade_output),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Contract sizing: disabled" in captured.out
    assert captured.err == ""

    with trade_output.open(
        encoding="utf-8",
        newline="",
    ) as csv_file:
        row = next(csv.DictReader(csv_file))

    assert row["lots"] == ""
    assert row["contract_size"] == ""


def test_cli_requires_contract_size_for_contract_options(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    trade_output = tmp_path / "trades.csv"

    exit_code = main(
        [
            "backtest",
            "--csv",
            SAMPLE_CSV,
            "--config",
            "config/default.yaml",
            "--extrema-window",
            "1",
            "--output",
            str(trade_output),
            "--minimum-lot",
            "0.01",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 1
    assert not trade_output.exists()
    assert captured.out == ""
    assert "Contract size is required" in captured.err


def test_cli_reports_minimum_lot_skip(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    trade_output = tmp_path / "trades.csv"

    exit_code = main(
        [
            "backtest",
            "--csv",
            SAMPLE_CSV,
            "--config",
            "config/default.yaml",
            "--extrema-window",
            "1",
            "--output",
            str(trade_output),
            "--contract-size",
            "100000",
            "--minimum-lot",
            "1",
            "--maximum-lot",
            "100",
            "--lot-step",
            "0.01",
            "--below-minimum-lot-policy",
            "SKIP",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Accepted trades: 0" in captured.out
    assert "Skipped minimum-lot trades: 1" in captured.out
    assert captured.err == ""

    with trade_output.open(
        encoding="utf-8",
        newline="",
    ) as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert rows == []
