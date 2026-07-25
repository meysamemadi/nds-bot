from pathlib import Path

import pytest

from nds_bot.cli import main


def write_config(
    path: Path,
    *,
    extrema_window: int,
) -> Path:
    path.write_text(
        f"""
topology:
  extrema_window: {extrema_window}

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


def write_monotonic_csv(path: Path) -> Path:
    path.write_text(
        """
time,open,high,low,close,volume
2026-01-01T00:00:00Z,100,100,100,100,1000
2026-01-01T01:00:00Z,101,101,101,101,1000
2026-01-01T02:00:00Z,102,102,102,102,1000
2026-01-01T03:00:00Z,103,103,103,103,1000
2026-01-01T04:00:00Z,104,104,104,104,1000
""".strip(),
        encoding="utf-8",
    )

    return path


def test_cli_scans_and_reports_valid_cycle(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = write_config(
        tmp_path / "settings.yaml",
        extrema_window=1,
    )

    csv_path = write_cycle_csv(tmp_path / "candles.csv")

    exit_code = main(
        [
            "scan",
            "--csv",
            str(csv_path),
            "--config",
            str(config_path),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "NDS scan completed" in captured.out
    assert "Cycles: 1" in captured.out
    assert "Valid cycles: 1" in captured.out
    assert "Cycle 1: BULL | VALID" in captured.out
    assert "Hook1=" in captured.out
    assert "NSI=" in captured.out
    assert captured.err == ""


def test_cli_extrema_window_override(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = write_config(
        tmp_path / "settings.yaml",
        extrema_window=6,
    )

    csv_path = write_cycle_csv(tmp_path / "candles.csv")

    exit_code = main(
        [
            "scan",
            "--csv",
            str(csv_path),
            "--config",
            str(config_path),
            "--extrema-window",
            "1",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Extrema window: 1" in captured.out
    assert "Valid cycles: 1" in captured.out


def test_cli_reports_missing_csv(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = write_config(
        tmp_path / "settings.yaml",
        extrema_window=1,
    )

    missing_csv = tmp_path / "missing.csv"

    exit_code = main(
        [
            "scan",
            "--csv",
            str(missing_csv),
            "--config",
            str(config_path),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "CSV file does not exist" in captured.err


def test_cli_reports_missing_configuration(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    csv_path = write_cycle_csv(tmp_path / "candles.csv")

    missing_config = tmp_path / "missing.yaml"

    exit_code = main(
        [
            "scan",
            "--csv",
            str(csv_path),
            "--config",
            str(missing_config),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Configuration file does not exist" in captured.err


def test_cli_succeeds_when_no_cycles_are_detected(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = write_config(
        tmp_path / "settings.yaml",
        extrema_window=1,
    )

    csv_path = write_monotonic_csv(tmp_path / "candles.csv")

    exit_code = main(
        [
            "scan",
            "--csv",
            str(csv_path),
            "--config",
            str(config_path),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Cycles: 0" in captured.out
    assert "No NDS cycles were detected." in captured.out
    assert captured.err == ""
