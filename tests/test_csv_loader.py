from datetime import UTC
from pathlib import Path

import pytest

from nds_bot.data.csv_loader import (
    CandleCsvError,
    load_candles_csv,
)


def write_csv(
    path: Path,
    content: str,
) -> Path:
    path.write_text(
        content,
        encoding="utf-8",
    )

    return path


def test_loads_valid_candles(tmp_path: Path) -> None:
    csv_path = write_csv(
        tmp_path / "candles.csv",
        """
time,open,high,low,close,volume
2026-01-01T00:00:00Z,100,110,95,105,1000
2026-01-01T01:00:00Z,105,112,101,108,1200
""".strip(),
    )

    candles = load_candles_csv(csv_path)

    assert len(candles) == 2

    first = candles[0]

    assert first.time.tzinfo is UTC
    assert first.open == pytest.approx(100)
    assert first.high == pytest.approx(110)
    assert first.low == pytest.approx(95)
    assert first.close == pytest.approx(105)
    assert first.volume == pytest.approx(1000)


def test_column_names_are_normalized(
    tmp_path: Path,
) -> None:
    csv_path = write_csv(
        tmp_path / "candles.csv",
        """
 Time , Open , High , Low , Close , Volume
2026-01-01T00:00:00Z,100,110,95,105,1000
""".strip(),
    )

    candles = load_candles_csv(csv_path)

    assert len(candles) == 1


def test_missing_columns_are_rejected(
    tmp_path: Path,
) -> None:
    csv_path = write_csv(
        tmp_path / "candles.csv",
        """
time,open,high,low,close
2026-01-01T00:00:00Z,100,110,95,105
""".strip(),
    )

    with pytest.raises(
        CandleCsvError,
        match="CSV is missing required columns: volume",
    ):
        load_candles_csv(csv_path)


def test_empty_csv_is_rejected(
    tmp_path: Path,
) -> None:
    csv_path = write_csv(
        tmp_path / "candles.csv",
        "time,open,high,low,close,volume",
    )

    with pytest.raises(
        CandleCsvError,
        match="CSV contains no candle rows",
    ):
        load_candles_csv(csv_path)


def test_duplicate_timestamps_are_rejected(
    tmp_path: Path,
) -> None:
    csv_path = write_csv(
        tmp_path / "candles.csv",
        """
time,open,high,low,close,volume
2026-01-01T00:00:00Z,100,110,95,105,1000
2026-01-01T00:00:00Z,105,112,101,108,1200
""".strip(),
    )

    with pytest.raises(
        CandleCsvError,
        match="CSV contains duplicate timestamps",
    ):
        load_candles_csv(csv_path)


def test_unordered_timestamps_are_rejected(
    tmp_path: Path,
) -> None:
    csv_path = write_csv(
        tmp_path / "candles.csv",
        """
time,open,high,low,close,volume
2026-01-01T01:00:00Z,105,112,101,108,1200
2026-01-01T00:00:00Z,100,110,95,105,1000
""".strip(),
    )

    with pytest.raises(
        CandleCsvError,
        match="CSV candles must be ordered by increasing time",
    ):
        load_candles_csv(csv_path)


def test_invalid_numeric_value_is_rejected(
    tmp_path: Path,
) -> None:
    csv_path = write_csv(
        tmp_path / "candles.csv",
        """
time,open,high,low,close,volume
2026-01-01T00:00:00Z,100,INVALID,95,105,1000
""".strip(),
    )

    with pytest.raises(
        CandleCsvError,
        match="invalid timestamp or numeric value",
    ):
        load_candles_csv(csv_path)


def test_invalid_candle_structure_is_rejected(
    tmp_path: Path,
) -> None:
    csv_path = write_csv(
        tmp_path / "candles.csv",
        """
time,open,high,low,close,volume
2026-01-01T00:00:00Z,100,101,95,105,1000
""".strip(),
    )

    with pytest.raises(
        CandleCsvError,
        match="Invalid candle data on CSV row 2",
    ):
        load_candles_csv(csv_path)


def test_missing_csv_file_is_rejected(
    tmp_path: Path,
) -> None:
    missing_path = tmp_path / "missing.csv"

    with pytest.raises(
        CandleCsvError,
        match="CSV file does not exist",
    ):
        load_candles_csv(missing_path)
