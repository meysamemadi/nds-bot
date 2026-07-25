from pathlib import Path

import pandas as pd
from pandas.errors import EmptyDataError, ParserError

from nds_bot.models import Candle

REQUIRED_COLUMNS = (
    "time",
    "open",
    "high",
    "low",
    "close",
    "volume",
)


class CandleCsvError(ValueError):
    """Raised when a candle CSV file is missing or invalid."""


def load_candles_csv(path: str | Path) -> list[Candle]:
    """Read, validate, and convert a candle CSV file."""
    csv_path = Path(path)

    if not csv_path.is_file():
        raise CandleCsvError(f"CSV file does not exist: {csv_path}")

    try:
        frame = pd.read_csv(csv_path)
    except (OSError, EmptyDataError, ParserError) as error:
        raise CandleCsvError(f"Could not read CSV file: {csv_path}") from error

    frame.columns = [str(column).strip().lower() for column in frame.columns]

    if frame.columns.duplicated().any():
        raise CandleCsvError("CSV contains duplicate column names.")

    missing_columns = [column for column in REQUIRED_COLUMNS if column not in frame.columns]

    if missing_columns:
        missing = ", ".join(missing_columns)

        raise CandleCsvError(f"CSV is missing required columns: {missing}")

    frame = frame.loc[:, list(REQUIRED_COLUMNS)].copy()

    if frame.empty:
        raise CandleCsvError("CSV contains no candle rows.")

    try:
        frame["time"] = pd.to_datetime(
            frame["time"],
            utc=True,
            errors="raise",
        )

        for column in REQUIRED_COLUMNS[1:]:
            frame[column] = pd.to_numeric(
                frame[column],
                errors="raise",
            )
    except (TypeError, ValueError) as error:
        raise CandleCsvError("CSV contains an invalid timestamp or numeric value.") from error

    if frame.isna().any().any():
        raise CandleCsvError("CSV contains missing values.")

    if frame["time"].duplicated().any():
        raise CandleCsvError("CSV contains duplicate timestamps.")

    if not frame["time"].is_monotonic_increasing:
        raise CandleCsvError("CSV candles must be ordered by increasing time.")

    candles: list[Candle] = []

    for row_number, row in enumerate(
        frame.itertuples(index=False),
        start=2,
    ):
        try:
            candle = Candle(
                time=row.time.to_pydatetime(),
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=float(row.volume),
            )
        except ValueError as error:
            raise CandleCsvError(f"Invalid candle data on CSV row {row_number}: {error}") from error

        candles.append(candle)

    return candles
