import csv
from pathlib import Path

import pytest

from nds_bot.data.portfolio_manifest import (
    PortfolioManifestError,
    load_portfolio_datasets,
    load_portfolio_manifest,
)

SAMPLE_PATH = Path("data/samples/documented_bull_cycle_execution.csv").resolve()
CONFIG_PATH = Path("config/default.yaml").resolve()


def write_manifest(
    path: Path,
    rows: list[dict[str, object]],
    *,
    columns: tuple[str, ...] = (
        "dataset_id",
        "symbol",
        "timeframe",
        "csv_path",
        "config_path",
        "extrema_window",
        "allocation_weight",
    ),
) -> None:
    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def test_loads_and_materializes_portfolio_manifest(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "portfolio.csv"

    write_manifest(
        manifest_path,
        [
            {
                "dataset_id": "eurusd-h1",
                "symbol": "EURUSD",
                "timeframe": "H1",
                "csv_path": SAMPLE_PATH,
                "config_path": CONFIG_PATH,
                "extrema_window": 1,
                "allocation_weight": 2,
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
        ],
    )

    entries = load_portfolio_manifest(manifest_path)
    datasets = load_portfolio_datasets(manifest_path)

    assert len(entries) == 2
    assert entries[0].allocation_weight == pytest.approx(2.0)
    assert entries[0].csv_path == SAMPLE_PATH

    assert len(datasets) == 2
    assert datasets[0].dataset_id == "eurusd-h1"
    assert datasets[0].config.extrema_window == 1
    assert len(datasets[0].candles) == 15


def test_duplicate_manifest_dataset_ids_are_rejected(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "portfolio.csv"
    row = {
        "dataset_id": "duplicate",
        "symbol": "EURUSD",
        "timeframe": "H1",
        "csv_path": SAMPLE_PATH,
        "config_path": CONFIG_PATH,
        "extrema_window": 1,
        "allocation_weight": 1,
    }

    write_manifest(manifest_path, [row, row])

    with pytest.raises(
        PortfolioManifestError,
        match="dataset ids must be unique",
    ):
        load_portfolio_manifest(manifest_path)


def test_missing_manifest_column_is_rejected(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "portfolio.csv"

    write_manifest(
        manifest_path,
        [
            {
                "dataset_id": "eurusd-h1",
                "symbol": "EURUSD",
                "timeframe": "H1",
                "csv_path": SAMPLE_PATH,
            }
        ],
        columns=(
            "dataset_id",
            "symbol",
            "timeframe",
            "csv_path",
        ),
    )

    with pytest.raises(
        PortfolioManifestError,
        match="missing required columns",
    ):
        load_portfolio_manifest(manifest_path)
