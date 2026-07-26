import csv
from dataclasses import dataclass, replace
from pathlib import Path

from nds_bot.backtest.portfolio import PortfolioDataset
from nds_bot.data.csv_loader import load_candles_csv
from nds_bot.settings import load_scan_config

REQUIRED_COLUMNS = (
    "dataset_id",
    "symbol",
    "timeframe",
    "csv_path",
    "config_path",
)


@dataclass(frozen=True)
class PortfolioManifestEntry:
    """One row from a portfolio manifest CSV."""

    dataset_id: str
    symbol: str
    timeframe: str
    csv_path: Path
    config_path: Path
    extrema_window: int | None
    allocation_weight: float


class PortfolioManifestError(ValueError):
    """Raised when a portfolio manifest cannot be loaded."""


def load_portfolio_manifest(
    path: str | Path,
) -> tuple[PortfolioManifestEntry, ...]:
    """Load and validate a multi-dataset portfolio manifest."""
    manifest_path = Path(path)

    if not manifest_path.is_file():
        raise PortfolioManifestError(f"Portfolio manifest does not exist: {manifest_path}")

    try:
        with manifest_path.open(
            encoding="utf-8-sig",
            newline="",
        ) as csv_file:
            reader = csv.DictReader(csv_file)
            fieldnames = tuple(reader.fieldnames or ())

            missing_columns = tuple(
                column for column in REQUIRED_COLUMNS if column not in fieldnames
            )

            if missing_columns:
                raise PortfolioManifestError(
                    "Portfolio manifest is missing required columns: " + ", ".join(missing_columns)
                )

            entries = tuple(
                _parse_entry(
                    row,
                    row_number=row_number,
                    manifest_path=manifest_path,
                )
                for row_number, row in enumerate(
                    reader,
                    start=2,
                )
            )

    except OSError as error:
        raise PortfolioManifestError(
            f"Could not read portfolio manifest: {manifest_path}"
        ) from error

    if not entries:
        raise PortfolioManifestError("Portfolio manifest cannot be empty.")

    dataset_ids = [entry.dataset_id for entry in entries]

    if len(dataset_ids) != len(set(dataset_ids)):
        raise PortfolioManifestError("Portfolio manifest dataset ids must be unique.")

    return entries


def load_portfolio_datasets(
    path: str | Path,
) -> tuple[PortfolioDataset, ...]:
    """Load manifest entries, candle CSVs, and scan configurations."""
    entries = load_portfolio_manifest(path)
    datasets: list[PortfolioDataset] = []

    for entry in entries:
        config = load_scan_config(entry.config_path)

        if entry.extrema_window is not None:
            config = replace(
                config,
                extrema_window=entry.extrema_window,
            )

        candles = load_candles_csv(entry.csv_path)

        datasets.append(
            PortfolioDataset(
                dataset_id=entry.dataset_id,
                symbol=entry.symbol,
                timeframe=entry.timeframe,
                candles=tuple(candles),
                config=config,
                allocation_weight=entry.allocation_weight,
                source_path=entry.csv_path,
            )
        )

    return tuple(datasets)


def _parse_entry(
    row: dict[str, str | None],
    *,
    row_number: int,
    manifest_path: Path,
) -> PortfolioManifestEntry:
    dataset_id = _required_text(
        row,
        "dataset_id",
        row_number=row_number,
    )
    symbol = _required_text(
        row,
        "symbol",
        row_number=row_number,
    )
    timeframe = _required_text(
        row,
        "timeframe",
        row_number=row_number,
    )

    csv_path = _resolve_path(
        _required_text(
            row,
            "csv_path",
            row_number=row_number,
        ),
        manifest_path=manifest_path,
    )
    config_path = _resolve_path(
        _required_text(
            row,
            "config_path",
            row_number=row_number,
        ),
        manifest_path=manifest_path,
    )

    if not csv_path.is_file():
        raise PortfolioManifestError(
            f"Portfolio candle CSV does not exist at row {row_number}: {csv_path}"
        )

    if not config_path.is_file():
        raise PortfolioManifestError(
            f"Portfolio configuration does not exist at row {row_number}: {config_path}"
        )

    extrema_window = _optional_positive_int(
        row.get("extrema_window"),
        field_name="extrema_window",
        row_number=row_number,
    )
    allocation_weight = _optional_positive_float(
        row.get("allocation_weight"),
        default=1.0,
        field_name="allocation_weight",
        row_number=row_number,
    )

    return PortfolioManifestEntry(
        dataset_id=dataset_id,
        symbol=symbol,
        timeframe=timeframe,
        csv_path=csv_path,
        config_path=config_path,
        extrema_window=extrema_window,
        allocation_weight=allocation_weight,
    )


def _required_text(
    row: dict[str, str | None],
    field_name: str,
    *,
    row_number: int,
) -> str:
    value = (row.get(field_name) or "").strip()

    if not value:
        raise PortfolioManifestError(
            f"Portfolio manifest field '{field_name}' is empty at row {row_number}."
        )

    return value


def _resolve_path(
    value: str,
    *,
    manifest_path: Path,
) -> Path:
    candidate = Path(value)

    if not candidate.is_absolute():
        candidate = manifest_path.parent / candidate

    return candidate.resolve()


def _optional_positive_int(
    value: str | None,
    *,
    field_name: str,
    row_number: int,
) -> int | None:
    text = (value or "").strip()

    if not text:
        return None

    try:
        parsed = int(text)
    except ValueError as error:
        raise PortfolioManifestError(
            f"Portfolio manifest field '{field_name}' must be an integer at row {row_number}."
        ) from error

    if parsed <= 0:
        raise PortfolioManifestError(
            f"Portfolio manifest field '{field_name}' must be positive at row {row_number}."
        )

    return parsed


def _optional_positive_float(
    value: str | None,
    *,
    default: float,
    field_name: str,
    row_number: int,
) -> float:
    text = (value or "").strip()

    if not text:
        return default

    try:
        parsed = float(text)
    except ValueError as error:
        raise PortfolioManifestError(
            f"Portfolio manifest field '{field_name}' must be numeric at row {row_number}."
        ) from error

    if parsed <= 0:
        raise PortfolioManifestError(
            f"Portfolio manifest field '{field_name}' must be positive at row {row_number}."
        )

    return parsed
