import csv
from pathlib import Path

import pytest

from nds_bot.backtest.account import AccountPolicy
from nds_bot.backtest.runner import run_backtest
from nds_bot.data.csv_loader import load_candles_csv
from nds_bot.data.equity_csv import write_equity_csv
from nds_bot.pipeline import ScanConfig


def test_writes_equity_curve_csv(
    tmp_path: Path,
) -> None:
    candles = load_candles_csv(Path("data/samples/documented_bull_cycle_execution.csv"))

    result = run_backtest(
        candles,
        config=ScanConfig(extrema_window=1),
        account_policy=AccountPolicy(
            initial_balance=10_000.0,
            risk_fraction=0.01,
        ),
    )

    assert result.account is not None

    output_path = write_equity_csv(
        result.account.equity_curve,
        tmp_path / "results" / "equity.csv",
    )

    assert output_path.is_file()

    with output_path.open(
        encoding="utf-8",
        newline="",
    ) as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert len(rows) == 2

    initial_row = rows[0]
    final_row = rows[1]

    assert initial_row["trade_number"] == "0"
    assert initial_row["exit_index"] == ""
    assert initial_row["exit_time"] == ""

    assert float(initial_row["balance"]) == pytest.approx(10_000.0)

    assert final_row["trade_number"] == "1"
    assert final_row["exit_index"] == "14"

    assert float(final_row["balance"]) == pytest.approx(10_200.0)

    assert float(final_row["peak_balance"]) == pytest.approx(10_200.0)

    assert float(final_row["drawdown_amount"]) == pytest.approx(0.0)


def test_empty_equity_export_contains_header(
    tmp_path: Path,
) -> None:
    output_path = write_equity_csv(
        [],
        tmp_path / "equity.csv",
    )

    lines = output_path.read_text(encoding="utf-8").splitlines()

    assert len(lines) == 1

    assert lines[0].startswith("trade_number,exit_index,exit_time")
