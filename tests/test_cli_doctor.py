import json
from pathlib import Path

import pytest

from nds_bot.cli import main


def test_cli_doctor_reports_healthy_runtime(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        [
            "doctor",
            "--config",
            "config/default.yaml",
            "--csv",
            ("data/samples/documented_bull_cycle_execution.csv"),
            "--output-dir",
            str(tmp_path / "results"),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "NDS runtime health report" in captured.out
    assert "configuration" in captured.out
    assert "candle-csv" in captured.out
    assert captured.err == ""


def test_cli_doctor_json_reports_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        [
            "doctor",
            "--config",
            str(tmp_path / "missing.yaml"),
            "--output-dir",
            str(tmp_path / "results"),
            "--format",
            "json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 1
    assert payload["overall_status"] == "FAIL"
    assert captured.err == ""


def test_cli_can_write_structured_runtime_log(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    log_path = tmp_path / "logs" / "runtime.jsonl"

    exit_code = main(
        [
            "--log-level",
            "DEBUG",
            "--log-format",
            "json",
            "--log-file",
            str(log_path),
            "doctor",
            "--config",
            "config/default.yaml",
            "--output-dir",
            str(tmp_path / "results"),
        ]
    )

    capsys.readouterr()

    assert exit_code == 0
    assert log_path.is_file()

    payloads = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]

    assert any(payload.get("command") == "doctor" for payload in payloads)
