import csv
from pathlib import Path

import pytest

from nds_bot.backtest.runner import run_backtest
from nds_bot.data.csv_loader import load_candles_csv
from nds_bot.data.trade_csv import write_trades_csv
from nds_bot.pipeline import ScanConfig


def test_writes_executed_trade_csv(
    tmp_path: Path,
) -> None:
    candle_path = Path("data/samples/documented_bull_cycle_execution.csv")

    candles = load_candles_csv(candle_path)

    result = run_backtest(
        candles,
        config=ScanConfig(extrema_window=1),
    )

    output_path = write_trades_csv(
        result.execution.trades,
        tmp_path / "results" / "trades.csv",
    )

    assert output_path.is_file()

    with output_path.open(
        encoding="utf-8",
        newline="",
    ) as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert len(rows) == 1

    row = rows[0]

    assert row["side"] == "SELL"
    assert row["cycle_direction"] == "BULL"
    assert row["entry_index"] == "13"
    assert row["exit_index"] == "14"
    assert row["exit_reason"] == "TAKE_PROFIT"

    assert float(row["r_multiple"]) == pytest.approx(2.0)


def test_empty_trade_export_contains_header(
    tmp_path: Path,
) -> None:
    output_path = write_trades_csv(
        [],
        tmp_path / "empty.csv",
    )

    lines = output_path.read_text(encoding="utf-8").splitlines()

    assert len(lines) == 1
    assert lines[0].startswith("side,signal_index")
