from datetime import UTC, datetime, timedelta

import pytest

from nds_bot.models import NDSCycle, Node, NodeType
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


@pytest.fixture
def bull_cycle() -> NDSCycle:
    nodes = [
        make_node(0, 1.08000, NodeType.TROUGH),
        make_node(1, 1.08650, NodeType.PEAK),
        make_node(2, 1.08230, NodeType.TROUGH),
        make_node(3, 1.09100, NodeType.PEAK),
        make_node(4, 1.08600, NodeType.TROUGH),
        make_node(5, 1.09480, NodeType.PEAK),
    ]

    return detect_nds_cycles(nodes)[0]


@pytest.fixture
def bear_cycle() -> NDSCycle:
    nodes = [
        make_node(0, 1.10000, NodeType.PEAK),
        make_node(1, 1.09350, NodeType.TROUGH),
        make_node(2, 1.09770, NodeType.PEAK),
        make_node(3, 1.08900, NodeType.TROUGH),
        make_node(4, 1.09400, NodeType.PEAK),
        make_node(5, 1.08520, NodeType.TROUGH),
    ]

    return detect_nds_cycles(nodes)[0]
