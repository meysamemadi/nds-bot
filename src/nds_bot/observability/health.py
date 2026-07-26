import platform
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from importlib.metadata import (
    PackageNotFoundError,
    version,
)
from pathlib import Path
from uuid import uuid4

from nds_bot.data.csv_loader import (
    CandleCsvError,
    load_candles_csv,
)
from nds_bot.settings import (
    ConfigurationError,
    load_scan_config,
)

MINIMUM_PYTHON_VERSION = (3, 11)


class HealthStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    SKIP = "SKIP"


@dataclass(frozen=True)
class HealthCheck:
    """One deterministic runtime health check."""

    name: str
    status: HealthStatus
    message: str
    details: dict[str, object]


@dataclass(frozen=True)
class HealthReport:
    """Runtime diagnostic report produced by the doctor command."""

    generated_at: datetime
    checks: tuple[HealthCheck, ...]
    python_version: str
    platform: str
    package_version: str | None

    @property
    def overall_status(self) -> HealthStatus:
        statuses = {check.status for check in self.checks}

        if HealthStatus.FAIL in statuses:
            return HealthStatus.FAIL

        if HealthStatus.WARN in statuses:
            return HealthStatus.WARN

        return HealthStatus.PASS

    @property
    def is_healthy(self) -> bool:
        return self.overall_status is not HealthStatus.FAIL

    def to_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "overall_status": self.overall_status.value,
            "python_version": self.python_version,
            "platform": self.platform,
            "package_version": self.package_version,
            "checks": [
                {
                    "name": check.name,
                    "status": check.status.value,
                    "message": check.message,
                    "details": check.details,
                }
                for check in self.checks
            ],
        }


def run_health_checks(
    *,
    config_path: Path = Path("config/default.yaml"),
    csv_path: Path | None = None,
    output_dir: Path = Path("results"),
) -> HealthReport:
    """Run environment, configuration, data, and filesystem checks."""
    package_version, package_check = _check_package_version()

    checks = (
        _check_python_version(),
        package_check,
        _check_configuration(config_path),
        _check_candle_csv(csv_path),
        _check_output_directory(output_dir),
    )

    return HealthReport(
        generated_at=datetime.now(UTC),
        checks=checks,
        python_version=platform.python_version(),
        platform=platform.platform(),
        package_version=package_version,
    )


def _check_python_version() -> HealthCheck:
    current = sys.version_info[:3]
    minimum = MINIMUM_PYTHON_VERSION
    passed = current >= minimum

    return HealthCheck(
        name="python-version",
        status=(HealthStatus.PASS if passed else HealthStatus.FAIL),
        message=("Python version is supported." if passed else "Python 3.11 or newer is required."),
        details={
            "current": ".".join(map(str, current)),
            "minimum": ".".join(map(str, minimum)),
        },
    )


def _check_package_version() -> tuple[str | None, HealthCheck]:
    try:
        package_version = version("nds-bot")
    except PackageNotFoundError:
        return None, HealthCheck(
            name="package-metadata",
            status=HealthStatus.WARN,
            message=("Package metadata is unavailable. Install the project in editable mode."),
            details={
                "recommended_command": ('python -m pip install -e ".[dev]"'),
            },
        )

    return package_version, HealthCheck(
        name="package-metadata",
        status=HealthStatus.PASS,
        message="Package metadata is available.",
        details={"version": package_version},
    )


def _check_configuration(config_path: Path) -> HealthCheck:
    try:
        config = load_scan_config(config_path)
    except (ConfigurationError, ValueError) as error:
        return HealthCheck(
            name="configuration",
            status=HealthStatus.FAIL,
            message=str(error),
            details={"path": str(config_path)},
        )

    return HealthCheck(
        name="configuration",
        status=HealthStatus.PASS,
        message="Configuration loaded successfully.",
        details={
            "path": str(config_path),
            "extrema_window": config.extrema_window,
        },
    )


def _check_candle_csv(csv_path: Path | None) -> HealthCheck:
    if csv_path is None:
        return HealthCheck(
            name="candle-csv",
            status=HealthStatus.SKIP,
            message="No candle CSV was requested for validation.",
            details={},
        )

    try:
        candles = load_candles_csv(csv_path)
    except (CandleCsvError, ValueError) as error:
        return HealthCheck(
            name="candle-csv",
            status=HealthStatus.FAIL,
            message=str(error),
            details={"path": str(csv_path)},
        )

    return HealthCheck(
        name="candle-csv",
        status=HealthStatus.PASS,
        message="Candle CSV loaded successfully.",
        details={
            "path": str(csv_path),
            "candle_count": len(candles),
            "first_time": candles[0].time.isoformat(),
            "last_time": candles[-1].time.isoformat(),
        },
    )


def _check_output_directory(output_dir: Path) -> HealthCheck:
    probe_path = output_dir / (f".nds_bot_health_{uuid4().hex}.tmp")

    try:
        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        if not output_dir.is_dir():
            raise OSError("Output path exists but is not a directory.")

        probe_path.write_text(
            "health-check",
            encoding="utf-8",
        )
        probe_path.unlink()

    except OSError as error:
        if probe_path.exists():
            probe_path.unlink(missing_ok=True)

        return HealthCheck(
            name="output-directory",
            status=HealthStatus.FAIL,
            message=f"Output directory is not writable: {error}",
            details={"path": str(output_dir)},
        )

    return HealthCheck(
        name="output-directory",
        status=HealthStatus.PASS,
        message="Output directory is writable.",
        details={"path": str(output_dir)},
    )
