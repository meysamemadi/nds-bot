import csv
from pathlib import Path

import pytest

from nds_bot.backtest.account import AccountPolicy
from nds_bot.backtest.runner import run_backtest
from nds_bot.data.csv_loader import load_candles_csv
from nds_bot.data.trade_csv import write_sized_trades_csv
from nds_bot.pipeline import ScanConfig

SAMPLE_PATH = Path("data/samples/documented_bull_cycle_execution.csv")


def _write_gap_sample(tmp_path: Path) -> Path:
    with SAMPLE_PATH.open(
        encoding="utf-8",
        newline="",
    ) as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)
        fieldnames = reader.fieldnames

    assert fieldnames is not None

    rows[-1].update(
        {
            "open": "1.08200",
            "high": "1.08300",
            "low": "1.08100",
            "close": "1.08250",
        }
    )

    output_path = tmp_path / "gap.csv"

    with output_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(rows)

    return output_path


def _read_single_row(path: Path) -> dict[str, str]:
    with path.open(
        encoding="utf-8",
        newline="",
    ) as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert len(rows) == 1
    return rows[0]


def test_gap_execution_fields_are_exported(
    tmp_path: Path,
) -> None:
    candles = load_candles_csv(_write_gap_sample(tmp_path))

    result = run_backtest(
        candles,
        config=ScanConfig(extrema_window=1),
        account_policy=AccountPolicy(),
    )

    assert result.account is not None

    output_path = write_sized_trades_csv(
        result.account.trades,
        tmp_path / "trades.csv",
    )

    row = _read_single_row(output_path)

    assert row["exit_reason"] == "TAKE_PROFIT"
    assert row["exit_fill_type"] == "GAP_OPEN"
    assert row["is_gap_exit"] == "True"
    assert float(row["exit_price"]) == pytest.approx(1.08200)
    assert float(row["theoretical_exit_price"]) == pytest.approx(1.08340)
    assert float(row["gap_distance"]) == pytest.approx(0.00140)


def test_regular_level_exit_exports_zero_gap_distance(
    tmp_path: Path,
) -> None:
    candles = load_candles_csv(SAMPLE_PATH)

    result = run_backtest(
        candles,
        config=ScanConfig(extrema_window=1),
        account_policy=AccountPolicy(),
    )

    assert result.account is not None

    output_path = write_sized_trades_csv(
        result.account.trades,
        tmp_path / "trades.csv",
    )

    row = _read_single_row(output_path)

    assert row["exit_fill_type"] == "LEVEL"
    assert row["is_gap_exit"] == "False"
    assert float(row["theoretical_exit_price"]) == pytest.approx(1.08340)
    assert float(row["gap_distance"]) == pytest.approx(0.0)
