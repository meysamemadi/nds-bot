import csv
from pathlib import Path

import pytest

from nds_bot.cli import main

SAMPLE_CSV = "data/samples/documented_bull_cycle_execution.csv"


def test_cli_runs_holdout_validation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "holdout.csv"

    exit_code = main(
        [
            "validate",
            "--mode",
            "HOLDOUT",
            "--csv",
            SAMPLE_CSV,
            "--config",
            "config/default.yaml",
            "--extrema-window",
            "1",
            "--train-fraction",
            "0.8",
            "--output",
            str(output_path),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert output_path.is_file()
    assert "NDS holdout validation completed" in captured.out
    assert "Split index: 12" in captured.out
    assert "TEST segment" in captured.out
    assert captured.err == ""

    with output_path.open(
        encoding="utf-8",
        newline="",
    ) as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert len(rows) == 2
    assert rows[1]["segment"] == "TEST"
    assert rows[1]["trade_count"] == "1"


def test_cli_runs_walk_forward_validation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "walk_forward.csv"

    exit_code = main(
        [
            "validate",
            "--mode",
            "WALK_FORWARD",
            "--csv",
            SAMPLE_CSV,
            "--config",
            "config/default.yaml",
            "--extrema-window",
            "1",
            "--initial-train-candles",
            "9",
            "--test-candles",
            "3",
            "--output",
            str(output_path),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert output_path.is_file()
    assert "NDS walk-forward validation completed" in captured.out
    assert "Folds: 2" in captured.out
    assert "Combined test trades: 1" in captured.out
    assert "Combined test total R: 2.0000" in captured.out
    assert captured.err == ""

    with output_path.open(
        encoding="utf-8",
        newline="",
    ) as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert len(rows) == 3
    assert rows[-1]["row_type"] == "SUMMARY"
    assert rows[-1]["summary_fold_count"] == "2"


def test_cli_requires_initial_train_for_walk_forward(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "walk_forward.csv"

    exit_code = main(
        [
            "validate",
            "--mode",
            "WALK_FORWARD",
            "--csv",
            SAMPLE_CSV,
            "--config",
            "config/default.yaml",
            "--test-candles",
            "3",
            "--output",
            str(output_path),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 1
    assert not output_path.exists()
    assert captured.out == ""
    assert "Initial train candles are required" in captured.err


def test_cli_rejects_overlapping_test_folds(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "walk_forward.csv"

    exit_code = main(
        [
            "validate",
            "--mode",
            "WALK_FORWARD",
            "--csv",
            SAMPLE_CSV,
            "--config",
            "config/default.yaml",
            "--initial-train-candles",
            "9",
            "--test-candles",
            "3",
            "--step-candles",
            "2",
            "--output",
            str(output_path),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 1
    assert not output_path.exists()
    assert captured.out == ""
    assert "overlapping test folds" in captured.err
