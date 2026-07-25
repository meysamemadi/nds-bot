from datetime import UTC, datetime, timedelta

import pytest

from nds_bot.models import CycleDirection, Node, NodeLabel, NodeType
from nds_bot.topology.sequences import detect_nds_cycles

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


def make_bull_nodes(start_index: int = 0) -> list[Node]:
    return [
        make_node(start_index, 1.08000, NodeType.TROUGH),
        make_node(start_index + 1, 1.08650, NodeType.PEAK),
        make_node(start_index + 2, 1.08230, NodeType.TROUGH),
        make_node(start_index + 3, 1.09100, NodeType.PEAK),
        make_node(start_index + 4, 1.08600, NodeType.TROUGH),
        make_node(start_index + 5, 1.09480, NodeType.PEAK),
    ]


def make_bear_nodes(start_index: int = 0) -> list[Node]:
    return [
        make_node(start_index, 1.10000, NodeType.PEAK),
        make_node(start_index + 1, 1.09350, NodeType.TROUGH),
        make_node(start_index + 2, 1.09770, NodeType.PEAK),
        make_node(start_index + 3, 1.08900, NodeType.TROUGH),
        make_node(start_index + 4, 1.09400, NodeType.PEAK),
        make_node(start_index + 5, 1.08520, NodeType.TROUGH),
    ]


def test_detects_documented_bull_cycle() -> None:
    nodes = make_bull_nodes()

    cycles = detect_nds_cycles(nodes)

    assert len(cycles) == 1

    cycle = cycles[0]

    assert cycle.direction is CycleDirection.BULL
    assert cycle.z.price == 1.08000
    assert cycle.n1.price == 1.08650
    assert cycle.s1.price == 1.08230
    assert cycle.n2.price == 1.09100
    assert cycle.s2.price == 1.08600
    assert cycle.n3.price == 1.09480


def test_assigns_correct_node_labels() -> None:
    cycle = detect_nds_cycles(make_bull_nodes())[0]

    labels = tuple(node.label for node in cycle.nodes)

    assert labels == (
        NodeLabel.Z,
        NodeLabel.N1,
        NodeLabel.S1,
        NodeLabel.N2,
        NodeLabel.S2,
        NodeLabel.N3,
    )


def test_detects_bear_cycle() -> None:
    cycles = detect_nds_cycles(make_bear_nodes())

    assert len(cycles) == 1
    assert cycles[0].direction is CycleDirection.BEAR


def test_rejects_invalid_bull_price_structure() -> None:
    nodes = make_bull_nodes()

    nodes[3] = make_node(
        index=3,
        price=1.08500,
        node_type=NodeType.PEAK,
    )

    cycles = detect_nds_cycles(nodes)

    assert cycles == []


def test_rejects_wrong_node_type_order() -> None:
    nodes = make_bull_nodes()

    nodes[5] = make_node(
        index=5,
        price=1.09480,
        node_type=NodeType.TROUGH,
    )

    cycles = detect_nds_cycles(nodes)

    assert cycles == []


def test_fewer_than_six_nodes_returns_no_cycles() -> None:
    nodes = make_bull_nodes()[:5]

    cycles = detect_nds_cycles(nodes)

    assert cycles == []


def test_finds_cycle_after_invalid_leading_node() -> None:
    leading_node = make_node(
        index=0,
        price=1.07000,
        node_type=NodeType.PEAK,
    )

    nodes = [
        leading_node,
        *make_bull_nodes(start_index=1),
    ]

    cycles = detect_nds_cycles(nodes)

    assert len(cycles) == 1
    assert cycles[0].z.index == 1
    assert cycles[0].n3.index == 6


def test_input_nodes_are_not_modified() -> None:
    nodes = make_bull_nodes()

    detect_nds_cycles(nodes)

    assert all(node.label is None for node in nodes)


def test_unordered_nodes_are_rejected() -> None:
    nodes = make_bull_nodes()

    nodes[2] = make_node(
        index=0,
        price=1.08230,
        node_type=NodeType.TROUGH,
    )

    with pytest.raises(
        ValueError,
        match="Nodes must be ordered by increasing index",
    ):
        detect_nds_cycles(nodes)
