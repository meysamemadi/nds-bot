import csv
from pathlib import Path

import pytest

from nds_bot.cli import main


def test_cli_backtest_exports_default_equity_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    trade_output = tmp_path / "results" / "trades.csv"

    equity_output = trade_output.parent / "equity.csv"

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
            str(trade_output),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert trade_output.is_file()
    assert equity_output.is_file()

    assert "Account simulation" in captured.out

    assert "Initial balance: 10000.00" in captured.out

    assert "Risk fraction: 1.00%" in captured.out

    assert "Ending balance: 10200.00" in captured.out

    assert "Net profit: 200.00" in captured.out
    assert "Account return: 2.00%" in captured.out

    assert "Maximum monetary drawdown: 0.00" in captured.out

    assert captured.err == ""


def test_cli_accepts_custom_account_settings(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    trade_output = tmp_path / "trades.csv"
    equity_output = tmp_path / "custom_equity.csv"

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
            str(trade_output),
            "--equity-output",
            str(equity_output),
            "--initial-balance",
            "20000",
            "--risk-fraction",
            "0.02",
            "--overlap-policy",
            "SKIP",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert trade_output.is_file()
    assert equity_output.is_file()

    assert "Initial balance: 20000.00" in captured.out

    assert "Risk fraction: 2.00%" in captured.out

    assert "Ending balance: 20800.00" in captured.out

    assert "Net profit: 800.00" in captured.out
    assert "Account return: 4.00%" in captured.out

    with equity_output.open(
        encoding="utf-8",
        newline="",
    ) as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert len(rows) == 2

    assert float(rows[-1]["balance"]) == pytest.approx(20_800.0)


def test_cli_rejects_invalid_account_policy(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    trade_output = tmp_path / "trades.csv"

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
            str(trade_output),
            "--risk-fraction",
            "0",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 1
    assert not trade_output.exists()

    assert captured.out == ""

    assert "Risk fraction must be greater than 0" in captured.err
