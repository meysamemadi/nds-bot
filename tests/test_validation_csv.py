import csv
from pathlib import Path

import pytest

from nds_bot.backtest.account import AccountPolicy
from nds_bot.backtest.validation import (
    HoldoutValidationConfig,
    run_holdout_validation,
)
from nds_bot.data.csv_loader import load_candles_csv
from nds_bot.data.validation_csv import write_validation_csv
from nds_bot.pipeline import ScanConfig


def test_writes_train_and_test_summary_rows(
    tmp_path: Path,
) -> None:
    candles = load_candles_csv(Path("data/samples/documented_bull_cycle_execution.csv"))

    result = run_holdout_validation(
        candles,
        validation_config=HoldoutValidationConfig(
            train_fraction=0.80,
        ),
        config=ScanConfig(extrema_window=1),
        account_policy=AccountPolicy(),
    )

    output_path = write_validation_csv(
        result,
        tmp_path / "validation.csv",
    )

    with output_path.open(
        encoding="utf-8",
        newline="",
    ) as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert len(rows) == 2
    assert rows[0]["segment"] == "TRAIN"
    assert rows[1]["segment"] == "TEST"
    assert rows[0]["trade_count"] == "0"
    assert rows[1]["trade_count"] == "1"
    assert rows[1]["account_enabled"] == "True"
    assert float(rows[1]["ending_balance"]) == pytest.approx(10_200.0)


def test_validation_csv_contains_split_metadata(
    tmp_path: Path,
) -> None:
    candles = load_candles_csv(Path("data/samples/documented_bull_cycle_execution.csv"))

    result = run_holdout_validation(
        candles,
        validation_config=HoldoutValidationConfig(
            train_fraction=14 / 15,
        ),
        config=ScanConfig(extrema_window=1),
    )

    output_path = write_validation_csv(
        result,
        tmp_path / "validation.csv",
    )

    with output_path.open(
        encoding="utf-8",
        newline="",
    ) as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert rows[0]["split_index"] == "14"
    assert rows[0]["boundary_trade_policy"] == "EXCLUDE"
    assert rows[0]["boundary_trade_count"] == "1"
    assert rows[0]["excluded_boundary_trade_count"] == "1"
