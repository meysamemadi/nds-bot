import csv
from pathlib import Path

import pytest

from nds_bot.cli import main

SAMPLE_CSV = "data/samples/documented_bull_cycle_execution.csv"


def base_arguments(trade_output: Path) -> list[str]:
    return [
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
    ]


def test_cli_enables_margin_and_exports_values(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    trade_output = tmp_path / "trades.csv"

    exit_code = main(
        [
            *base_arguments(trade_output),
            "--leverage",
            "100",
            "--insufficient-margin-policy",
            "SKIP",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Margin checking: enabled" in captured.out
    assert "Leverage: 100.0000" in captured.out
    assert "Insufficient margin policy: SKIP" in captured.out
    assert "Skipped insufficient-margin trades: 0" in captured.out
    assert "Maximum margin required: 250.89" in captured.out
    assert "Maximum margin utilization: 2.51%" in captured.out
    assert "Minimum free margin after entry: 9749.11" in captured.out
    assert captured.err == ""

    with trade_output.open(
        encoding="utf-8",
        newline="",
    ) as csv_file:
        row = next(csv.DictReader(csv_file))

    assert float(row["leverage"]) == pytest.approx(100.0)
    assert float(row["margin_required"]) == pytest.approx(250.8923605)


def test_cli_preserves_disabled_margin_by_default(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    trade_output = tmp_path / "trades.csv"

    exit_code = main(base_arguments(trade_output))

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Margin checking: disabled" in captured.out
    assert "Maximum margin required: 0.00" in captured.out
    assert "Minimum free margin after entry: N/A" in captured.out
    assert captured.err == ""

    with trade_output.open(
        encoding="utf-8",
        newline="",
    ) as csv_file:
        row = next(csv.DictReader(csv_file))

    assert row["margin_enabled"] == "False"
    assert row["margin_required"] == ""


def test_cli_requires_leverage_for_margin_options(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    trade_output = tmp_path / "trades.csv"

    exit_code = main(
        [
            *base_arguments(trade_output),
            "--insufficient-margin-policy",
            "SKIP",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 1
    assert not trade_output.exists()
    assert captured.out == ""
    assert "Leverage is required" in captured.err


def test_cli_reports_insufficient_margin_skip(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    trade_output = tmp_path / "trades.csv"

    exit_code = main(
        [
            *base_arguments(trade_output),
            "--leverage",
            "1",
            "--insufficient-margin-policy",
            "SKIP",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Margin checking: enabled" in captured.out
    assert "Accepted trades: 0" in captured.out
    assert "Skipped insufficient-margin trades: 1" in captured.out
    assert captured.err == ""

    with trade_output.open(
        encoding="utf-8",
        newline="",
    ) as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert rows == []
