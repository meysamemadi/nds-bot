import csv
from pathlib import Path

import pytest

from nds_bot.cli import main


def test_cli_default_zero_costs_preserve_previous_account_result(
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
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert trade_output.is_file()
    assert "Spread fraction: 0.000000" in captured.out
    assert "Slippage fraction: 0.000000" in captured.out
    assert "Commission fraction: 0.000000" in captured.out
    assert "Total trading cost: 0.00" in captured.out
    assert "Ending balance: 10200.00" in captured.out
    assert captured.err == ""


def test_cli_applies_and_reports_custom_trading_costs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    trade_output = tmp_path / "trades.csv"
    equity_output = tmp_path / "equity.csv"

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
            "--spread-fraction",
            "0.0002",
            "--slippage-fraction",
            "0.00005",
            "--commission-fraction",
            "0.0001",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert trade_output.is_file()
    assert equity_output.is_file()

    assert "Spread fraction: 0.000200" in captured.out
    assert "Slippage fraction: 0.000050" in captured.out
    assert "Commission fraction: 0.000100" in captured.out
    assert "Adverse fill fraction: 0.000150" in captured.out
    assert "Gross filled PnL: 167.35" in captured.out
    assert "Spread/slippage cost: 7.50" in captured.out
    assert "Commission: 5.00" in captured.out
    assert "Total trading cost: 12.51" in captured.out
    assert "Ending balance: 10162.35" in captured.out
    assert "Net profit: 162.35" in captured.out
    assert "Account return: 1.62%" in captured.out
    assert captured.err == ""

    with trade_output.open(
        encoding="utf-8",
        newline="",
    ) as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert len(rows) == 1
    assert rows[0]["exit_reason"] == "TAKE_PROFIT"

    assert float(rows[0]["net_monetary_pnl"]) == pytest.approx(162.34858382)


def test_cli_rejects_invalid_trading_cost_policy(
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
            "--spread-fraction",
            "-0.1",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 1
    assert not trade_output.exists()
    assert captured.out == ""
    assert "Spread fraction cannot be negative" in captured.err
