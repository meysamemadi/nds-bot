import csv
from pathlib import Path

import pytest

from nds_bot.cli import main

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


def _run_cli(
    tmp_path: Path,
    *,
    gap_fill_mode: str | None = None,
) -> tuple[int, Path]:
    trade_output = tmp_path / "trades.csv"

    arguments = [
        "backtest",
        "--csv",
        str(_write_gap_sample(tmp_path)),
        "--config",
        "config/default.yaml",
        "--extrema-window",
        "1",
        "--output",
        str(trade_output),
    ]

    if gap_fill_mode is not None:
        arguments.extend(
            [
                "--gap-fill-mode",
                gap_fill_mode,
            ]
        )

    return main(arguments), trade_output


def _read_single_row(path: Path) -> dict[str, str]:
    with path.open(
        encoding="utf-8",
        newline="",
    ) as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert len(rows) == 1
    return rows[0]


def test_cli_uses_open_price_for_gap_by_default(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code, trade_output = _run_cli(tmp_path)
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Gap fill mode: OPEN_PRICE" in captured.out
    assert captured.err == ""

    row = _read_single_row(trade_output)

    assert row["exit_fill_type"] == "GAP_OPEN"
    assert row["is_gap_exit"] == "True"
    assert float(row["exit_price"]) == pytest.approx(1.082)


def test_cli_can_preserve_theoretical_level_fill(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code, trade_output = _run_cli(
        tmp_path,
        gap_fill_mode="LEVEL_PRICE",
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Gap fill mode: LEVEL_PRICE" in captured.out
    assert captured.err == ""

    row = _read_single_row(trade_output)

    assert row["exit_fill_type"] == "LEVEL"
    assert row["is_gap_exit"] == "False"
    assert float(row["exit_price"]) == pytest.approx(1.0834)
    assert float(row["gap_distance"]) == pytest.approx(0.0)


def test_cli_rejects_unknown_gap_fill_mode(
    tmp_path: Path,
) -> None:
    with pytest.raises(SystemExit) as error:
        main(
            [
                "backtest",
                "--csv",
                str(_write_gap_sample(tmp_path)),
                "--output",
                str(tmp_path / "trades.csv"),
                "--gap-fill-mode",
                "UNKNOWN",
            ]
        )

    assert error.value.code == 2
