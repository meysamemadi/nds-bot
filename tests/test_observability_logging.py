import json
import logging
from pathlib import Path

import pytest

from nds_bot.observability.logging import (
    JsonLineFormatter,
    LoggingConfig,
    configure_logging,
)


def test_logging_config_normalizes_level() -> None:
    config = LoggingConfig(level="info")

    assert config.level == "INFO"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"level": "TRACE"}, "Log level must be one of"),
        ({"output_format": "xml"}, "Log format must be text or json"),
    ],
)
def test_invalid_logging_config_is_rejected(
    kwargs: dict[str, str],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        LoggingConfig(**kwargs)


def test_json_formatter_includes_structured_context() -> None:
    formatter = JsonLineFormatter()
    record = logging.LogRecord(
        name="nds_bot.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="paper order submitted",
        args=(),
        exc_info=None,
    )
    record.symbol = "EURUSD"
    record.order_id = "order-1"

    payload = json.loads(formatter.format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "nds_bot.test"
    assert payload["message"] == "paper order submitted"
    assert payload["symbol"] == "EURUSD"
    assert payload["order_id"] == "order-1"


def test_configure_logging_writes_utf8_file(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "logs" / "nds-bot.jsonl"

    configure_logging(
        LoggingConfig(
            level="INFO",
            output_format="json",
            file_path=log_path,
        )
    )

    logger = logging.getLogger("nds_bot.test")
    logger.info(
        "سلام",
        extra={"command": "doctor"},
    )

    for handler in logging.getLogger().handlers:
        handler.flush()

    lines = log_path.read_text(encoding="utf-8").splitlines()

    assert len(lines) == 1

    payload = json.loads(lines[0])

    assert payload["message"] == "سلام"
    assert payload["command"] == "doctor"
