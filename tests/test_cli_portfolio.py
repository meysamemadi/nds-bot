import csv
from pathlib import Path

import pytest

from nds_bot.cli import main

SAMPLE_PATH = Path("data/samples/documented_bull_cycle_execution.csv").resolve()
CONFIG_PATH = Path("config/default.yaml").resolve()


def write_manifest(path: Path) -> None:
    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=(
                "dataset_id",
                "symbol",
                "timeframe",
                "csv_path",
                "config_path",
                "extrema_window",
                "allocation_weight",
            ),
        )
        writer.writeheader()
        writer.writerows(
            [
                {
                    "dataset_id": "eurusd-h1",
                    "symbol": "EURUSD",
                    "timeframe": "H1",
                    "csv_path": SAMPLE_PATH,
                    "config_path": CONFIG_PATH,
                    "extrema_window": 1,
                    "allocation_weight": 1,
                },
                {
                    "dataset_id": "gbpusd-h1",
                    "symbol": "GBPUSD",
                    "timeframe": "H1",
                    "csv_path": SAMPLE_PATH,
                    "config_path": CONFIG_PATH,
                    "extrema_window": 1,
                    "allocation_weight": 1,
                },
            ]
        )


def test_cli_runs_portfolio_and_exports_results(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    manifest_path = tmp_path / "manifest.csv"
    summary_path = tmp_path / "results" / "portfolio.csv"
    equity_path = tmp_path / "results" / "equity.csv"
    write_manifest(manifest_path)

    exit_code = main(
        [
            "portfolio",
            "--manifest",
            str(manifest_path),
            "--output",
            str(summary_path),
            "--equity-output",
            str(equity_path),
            "--initial-balance",
            "10000",
            "--risk-fraction",
            "0.01",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert summary_path.is_file()
    assert equity_path.is_file()
    assert "NDS portfolio backtest completed" in captured.out
    assert "Datasets: 2" in captured.out
    assert "Ending balance: 10200.00" in captured.out
    assert "Portfolio return: 2.00%" in captured.out
    assert captured.err == ""


def test_cli_reports_missing_portfolio_manifest(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "portfolio.csv"

    exit_code = main(
        [
            "portfolio",
            "--manifest",
            str(tmp_path / "missing.csv"),
            "--output",
            str(output_path),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 1
    assert not output_path.exists()
    assert captured.out == ""
    assert "Portfolio manifest does not exist" in captured.err
