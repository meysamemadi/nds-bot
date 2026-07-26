import csv
from pathlib import Path

import pytest

from nds_bot.backtest.account import AccountPolicy
from nds_bot.backtest.walk_forward import (
    WalkForwardValidationConfig,
    run_walk_forward_validation,
)
from nds_bot.data.csv_loader import load_candles_csv
from nds_bot.data.walk_forward_csv import write_walk_forward_csv
from nds_bot.pipeline import ScanConfig


def build_result():
    candles = load_candles_csv(Path("data/samples/documented_bull_cycle_execution.csv"))

    return run_walk_forward_validation(
        candles,
        validation_config=WalkForwardValidationConfig(
            initial_train_candles=9,
            test_candles=3,
        ),
        config=ScanConfig(extrema_window=1),
        account_policy=AccountPolicy(),
    )


def test_writes_fold_rows_and_summary(
    tmp_path: Path,
) -> None:
    output_path = write_walk_forward_csv(
        build_result(),
        tmp_path / "walk_forward.csv",
    )

    with output_path.open(
        encoding="utf-8",
        newline="",
    ) as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert len(rows) == 3
    assert rows[0]["row_type"] == "FOLD"
    assert rows[1]["row_type"] == "FOLD"
    assert rows[2]["row_type"] == "SUMMARY"

    assert rows[0]["test_start_index"] == "9"
    assert rows[1]["test_start_index"] == "12"
    assert rows[1]["test_trade_count"] == "1"

    assert rows[2]["summary_fold_count"] == "2"
    assert rows[2]["summary_test_trade_count"] == "1"
    assert float(rows[2]["summary_test_total_r"]) == pytest.approx(2.0)


def test_summary_exports_account_statistics(
    tmp_path: Path,
) -> None:
    output_path = write_walk_forward_csv(
        build_result(),
        tmp_path / "walk_forward.csv",
    )

    with output_path.open(
        encoding="utf-8",
        newline="",
    ) as csv_file:
        rows = list(csv.DictReader(csv_file))

    summary = rows[-1]

    assert summary["account_enabled"] == "True"
    assert float(summary["mean_test_return_fraction"]) == pytest.approx(0.01)
    assert float(summary["total_test_net_profit"]) == pytest.approx(200.0)
