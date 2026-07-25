from datetime import UTC, datetime, timedelta

import pytest

from nds_bot.models import Candle, NodeType
from nds_bot.topology.extrema import detect_local_extrema

BASE_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def make_candle(index: int, close: float) -> Candle:
    return Candle(
        time=BASE_TIME + timedelta(hours=index),
        open=close,
        high=close + 0.5,
        low=close - 0.5,
        close=close,
        volume=1_000.0,
    )


def test_detects_peak_and_trough() -> None:
    prices = [
        100.0,
        103.0,
        106.0,
        104.0,
        101.0,
        98.0,
        101.0,
        105.0,
    ]

    candles = [make_candle(index, price) for index, price in enumerate(prices)]

    nodes = detect_local_extrema(candles, window=2)

    result = [(node.index, node.node_type, node.price) for node in nodes]

    assert result == [
        (2, NodeType.PEAK, 106.5),
        (5, NodeType.TROUGH, 97.5),
    ]


def test_edge_candles_are_ignored() -> None:
    prices = [105.0, 104.0, 103.0, 102.0, 101.0]

    candles = [make_candle(index, price) for index, price in enumerate(prices)]

    nodes = detect_local_extrema(candles, window=1)

    assert nodes == []


def test_short_series_returns_no_nodes() -> None:
    candles = [
        make_candle(index, price) for index, price in enumerate([100.0, 101.0, 102.0, 103.0])
    ]

    nodes = detect_local_extrema(candles, window=2)

    assert nodes == []


@pytest.mark.parametrize("window", [0, -1])
def test_invalid_window_is_rejected(window: int) -> None:
    candles = [make_candle(index, price) for index, price in enumerate([100.0, 101.0, 102.0])]

    with pytest.raises(ValueError, match="Window must be at least 1"):
        detect_local_extrema(candles, window=window)


def test_flat_market_does_not_create_nodes() -> None:
    candles = [make_candle(index, 100.0) for index in range(3)]

    nodes = detect_local_extrema(candles, window=1)

    assert nodes == []


def test_ambiguous_outside_candle_is_ignored() -> None:
    candles = [
        Candle(
            time=BASE_TIME,
            open=100.0,
            high=105.0,
            low=95.0,
            close=100.0,
            volume=1_000.0,
        ),
        Candle(
            time=BASE_TIME + timedelta(hours=1),
            open=100.0,
            high=110.0,
            low=90.0,
            close=100.0,
            volume=1_000.0,
        ),
        Candle(
            time=BASE_TIME + timedelta(hours=2),
            open=100.0,
            high=104.0,
            low=96.0,
            close=100.0,
            volume=1_000.0,
        ),
    ]

    nodes = detect_local_extrema(candles, window=1)

    assert nodes == []
