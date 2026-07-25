from datetime import UTC, datetime, timedelta

import pytest

from nds_bot.models import Node, NodeType
from nds_bot.topology.candidates import build_alternating_nodes
from nds_bot.models import Candle
from nds_bot.topology.extrema import detect_local_extrema

BASE_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def make_node(
    index: int,
    price: float,
    node_type: NodeType,
) -> Node:
    return Node(
        index=index,
        time=BASE_TIME + timedelta(hours=index),
        price=price,
        node_type=node_type,
    )


def test_empty_input_returns_empty_list() -> None:
    result = build_alternating_nodes([])

    assert result == []


def test_alternating_nodes_are_preserved() -> None:
    nodes = [
        make_node(1, 100.0, NodeType.TROUGH),
        make_node(2, 110.0, NodeType.PEAK),
        make_node(3, 105.0, NodeType.TROUGH),
    ]

    result = build_alternating_nodes(nodes)

    assert result == nodes


def test_higher_consecutive_peak_is_retained() -> None:
    nodes = [
        make_node(1, 105.0, NodeType.PEAK),
        make_node(2, 110.0, NodeType.PEAK),
        make_node(3, 100.0, NodeType.TROUGH),
    ]

    result = build_alternating_nodes(nodes)

    assert result == [
        nodes[1],
        nodes[2],
    ]


def test_lower_consecutive_trough_is_retained() -> None:
    nodes = [
        make_node(1, 100.0, NodeType.TROUGH),
        make_node(2, 95.0, NodeType.TROUGH),
        make_node(3, 110.0, NodeType.PEAK),
    ]

    result = build_alternating_nodes(nodes)

    assert result == [
        nodes[1],
        nodes[2],
    ]


def test_multiple_same_type_nodes_are_reduced_to_strongest() -> None:
    nodes = [
        make_node(1, 105.0, NodeType.PEAK),
        make_node(2, 108.0, NodeType.PEAK),
        make_node(3, 106.0, NodeType.PEAK),
        make_node(4, 98.0, NodeType.TROUGH),
    ]

    result = build_alternating_nodes(nodes)

    assert result == [
        nodes[1],
        nodes[3],
    ]


def test_newer_node_is_retained_when_prices_are_equal() -> None:
    nodes = [
        make_node(1, 110.0, NodeType.PEAK),
        make_node(2, 110.0, NodeType.PEAK),
        make_node(3, 100.0, NodeType.TROUGH),
    ]

    result = build_alternating_nodes(nodes)

    assert result == [
        nodes[1],
        nodes[2],
    ]


def test_unordered_nodes_are_rejected() -> None:
    nodes = [
        make_node(2, 110.0, NodeType.PEAK),
        make_node(1, 100.0, NodeType.TROUGH),
    ]

    with pytest.raises(
        ValueError,
        match="Nodes must be ordered by increasing index",
    ):
        build_alternating_nodes(nodes)


def test_extrema_output_can_be_normalized() -> None:
    prices = [
        100.0,
        104.0,
        108.0,
        106.0,
        109.0,
        103.0,
        98.0,
        101.0,
    ]

    candles = [
        Candle(
            time=BASE_TIME + timedelta(hours=index),
            open=price,
            high=price + 0.5,
            low=price - 0.5,
            close=price,
            volume=1_000.0,
        )
        for index, price in enumerate(prices)
    ]

    raw_nodes = detect_local_extrema(candles, window=1)
    normalized_nodes = build_alternating_nodes(raw_nodes)

    assert all(
        current.node_type is not next_node.node_type
        for current, next_node in zip(
            normalized_nodes,
            normalized_nodes[1:],
            strict=False,
        )
    )
