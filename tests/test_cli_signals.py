import csv
from pathlib import Path

import pytest

from nds_bot.cli import main


def write_config(path: Path) -> Path:
    path.write_text(
        """
topology:
  extrema_window: 1

quality:
  hook_ideal: 0.86
  hook_minimum: 0.25
  hook_maximum: 0.92
  maximum_nsi: 0.60
""".strip(),
        encoding="utf-8",
    )

    return path


def write_cycle_csv(path: Path) -> Path:
    path.write_text(
        """
time,open,high,low,close,volume
2026-01-01T00:00:00Z,1.08100,1.08100,1.08100,1.08100,1000
2026-01-01T01:00:00Z,1.08000,1.08000,1.08000,1.08000,1000
2026-01-01T02:00:00Z,1.08300,1.08300,1.08300,1.08300,1000
2026-01-01T03:00:00Z,1.08650,1.08650,1.08650,1.08650,1000
2026-01-01T04:00:00Z,1.08400,1.08400,1.08400,1.08400,1000
2026-01-01T05:00:00Z,1.08230,1.08230,1.08230,1.08230,1000
2026-01-01T06:00:00Z,1.08600,1.08600,1.08600,1.08600,1000
2026-01-01T07:00:00Z,1.09100,1.09100,1.09100,1.09100,1000
2026-01-01T08:00:00Z,1.08800,1.08800,1.08800,1.08800,1000
2026-01-01T09:00:00Z,1.08600,1.08600,1.08600,1.08600,1000
2026-01-01T10:00:00Z,1.09000,1.09000,1.09000,1.09000,1000
2026-01-01T11:00:00Z,1.09480,1.09480,1.09480,1.09480,1000
2026-01-01T12:00:00Z,1.09200,1.09200,1.09200,1.09200,1000
""".strip(),
        encoding="utf-8",
    )

    return path


def test_cli_exports_signal_csv(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = write_config(tmp_path / "settings.yaml")

    candle_path = write_cycle_csv(tmp_path / "candles.csv")

    output_path = tmp_path / "results" / "signals.csv"

    exit_code = main(
        [
            "signals",
            "--csv",
            str(candle_path),
            "--config",
            str(config_path),
            "--output",
            str(output_path),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert output_path.is_file()
    assert "NDS signal export completed" in captured.out
    assert "Signals: 1" in captured.out
    assert captured.err == ""

    with output_path.open(
        encoding="utf-8",
        newline="",
    ) as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert len(rows) == 1
    assert rows[0]["side"] == "SELL"
    assert rows[0]["cycle_direction"] == "BULL"
    assert rows[0]["generated_at_index"] == "12"
    assert float(rows[0]["reference_price"]) == pytest.approx(1.09200)


def test_cli_signals_reports_missing_csv(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = write_config(tmp_path / "settings.yaml")

    output_path = tmp_path / "signals.csv"

    exit_code = main(
        [
            "signals",
            "--csv",
            str(tmp_path / "missing.csv"),
            "--config",
            str(config_path),
            "--output",
            str(output_path),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 1
    assert not output_path.exists()
    assert captured.out == ""
    assert "CSV file does not exist" in captured.err
