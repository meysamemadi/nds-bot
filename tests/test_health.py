from datetime import UTC, datetime
from pathlib import Path

from nds_bot.observability.health import (
    HealthCheck,
    HealthReport,
    HealthStatus,
    run_health_checks,
)


def test_health_report_passes_valid_project_inputs(
    tmp_path: Path,
) -> None:
    report = run_health_checks(
        config_path=Path("config/default.yaml"),
        csv_path=Path("data/samples/documented_bull_cycle_execution.csv"),
        output_dir=tmp_path / "results",
    )

    assert report.is_healthy is True
    assert report.overall_status in {
        HealthStatus.PASS,
        HealthStatus.WARN,
    }

    checks = {check.name: check for check in report.checks}

    assert checks["python-version"].status is HealthStatus.PASS
    assert checks["configuration"].status is HealthStatus.PASS
    assert checks["candle-csv"].status is HealthStatus.PASS
    assert checks["output-directory"].status is HealthStatus.PASS


def test_missing_configuration_fails_health_report(
    tmp_path: Path,
) -> None:
    report = run_health_checks(
        config_path=tmp_path / "missing.yaml",
        output_dir=tmp_path / "results",
    )

    assert report.overall_status is HealthStatus.FAIL

    configuration_check = next(check for check in report.checks if check.name == "configuration")

    assert configuration_check.status is HealthStatus.FAIL


def test_missing_candle_csv_fails_health_report(
    tmp_path: Path,
) -> None:
    report = run_health_checks(
        config_path=Path("config/default.yaml"),
        csv_path=tmp_path / "missing.csv",
        output_dir=tmp_path / "results",
    )

    csv_check = next(check for check in report.checks if check.name == "candle-csv")

    assert csv_check.status is HealthStatus.FAIL
    assert report.overall_status is HealthStatus.FAIL


def test_candle_check_is_skipped_when_not_requested(
    tmp_path: Path,
) -> None:
    report = run_health_checks(
        config_path=Path("config/default.yaml"),
        output_dir=tmp_path / "results",
    )

    csv_check = next(check for check in report.checks if check.name == "candle-csv")

    assert csv_check.status is HealthStatus.SKIP


def test_file_cannot_be_used_as_output_directory(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "not-a-directory"
    output_path.write_text("file", encoding="utf-8")

    report = run_health_checks(
        config_path=Path("config/default.yaml"),
        output_dir=output_path,
    )

    output_check = next(check for check in report.checks if check.name == "output-directory")

    assert output_check.status is HealthStatus.FAIL
    assert report.overall_status is HealthStatus.FAIL


def test_health_status_precedence() -> None:
    report = HealthReport(
        generated_at=datetime.now(UTC),
        checks=(
            HealthCheck(
                name="warn",
                status=HealthStatus.WARN,
                message="warning",
                details={},
            ),
            HealthCheck(
                name="fail",
                status=HealthStatus.FAIL,
                message="failure",
                details={},
            ),
        ),
        python_version="3.11.9",
        platform="test",
        package_version="1.0.0",
    )

    assert report.overall_status is HealthStatus.FAIL
    assert report.is_healthy is False
