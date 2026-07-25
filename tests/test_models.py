from datetime import UTC, datetime

import pytest

from nds_bot.models import Candle, Node, NodeType


def test_valid_candle() -> None:
    candle = Candle(
        time=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
        open=100.0,
        high=110.0,
        low=95.0,
        close=105.0,
        volume=1_000.0,
    )

    assert candle.high == 110.0
    assert candle.low == 95.0


def test_invalid_candle_high() -> None:
    with pytest.raises(ValueError, match="High price is invalid"):
        Candle(
            time=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
            open=100.0,
            high=101.0,
            low=95.0,
            close=105.0,
            volume=1_000.0,
        )


def test_valid_node() -> None:
    node = Node(
        index=10,
        time=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
        price=105.0,
        node_type=NodeType.PEAK,
    )

    assert node.node_type is NodeType.PEAK
    assert node.index == 10
