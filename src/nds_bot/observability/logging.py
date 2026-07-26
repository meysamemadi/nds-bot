import json
import logging
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

LOG_LEVELS = (
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
    "CRITICAL",
)

LOG_FORMATS = (
    "text",
    "json",
)

_RESERVED_RECORD_FIELDS = frozenset(
    logging.LogRecord(
        name="",
        level=0,
        pathname="",
        lineno=0,
        msg="",
        args=(),
        exc_info=None,
    ).__dict__
)


@dataclass(frozen=True)
class LoggingConfig:
    """Configuration for console and optional file logging."""

    level: str = "WARNING"
    output_format: str = "text"
    file_path: Path | None = None

    def __post_init__(self) -> None:
        normalized_level = self.level.upper()

        if normalized_level not in LOG_LEVELS:
            raise ValueError("Log level must be one of: " + ", ".join(LOG_LEVELS) + ".")

        if self.output_format not in LOG_FORMATS:
            raise ValueError("Log format must be text or json.")

        object.__setattr__(
            self,
            "level",
            normalized_level,
        )


class JsonLineFormatter(logging.Formatter):
    """Render one structured JSON object per log record."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key in _RESERVED_RECORD_FIELDS or key.startswith("_"):
                continue

            payload[key] = _json_safe(value)

        if record.exc_info is not None:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
        )


def configure_logging(
    config: LoggingConfig | None = None,
) -> logging.Logger:
    """Configure deterministic root logging without duplicate handlers."""
    active_config = config or LoggingConfig()
    root_logger = logging.getLogger()
    root_logger.setLevel(active_config.level)

    for handler in tuple(root_logger.handlers):
        root_logger.removeHandler(handler)
        handler.close()

    formatter = _build_formatter(active_config.output_format)

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(active_config.level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    if active_config.file_path is not None:
        active_config.file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        file_handler = logging.FileHandler(
            active_config.file_path,
            encoding="utf-8",
        )
        file_handler.setLevel(active_config.level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    return root_logger


def _build_formatter(output_format: str) -> logging.Formatter:
    if output_format == "json":
        return JsonLineFormatter()

    return logging.Formatter(
        fmt=("%(asctime)s %(levelname)s %(name)s %(message)s"),
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )


def _json_safe(value: object) -> object:
    if isinstance(value, Path):
        return str(value)

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]

    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}

    return str(value)
