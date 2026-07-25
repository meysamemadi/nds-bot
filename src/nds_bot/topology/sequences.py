from collections.abc import Sequence
from dataclasses import replace
from itertools import pairwise

from nds_bot.models import CycleDirection, NDSCycle, Node, NodeLabel, NodeType

CYCLE_SIZE = 6

NODE_LABELS = (
    NodeLabel.Z,
    NodeLabel.N1,
    NodeLabel.S1,
    NodeLabel.N2,
    NodeLabel.S2,
    NodeLabel.N3,
)

BULL_NODE_TYPES = (
    NodeType.TROUGH,
    NodeType.PEAK,
    NodeType.TROUGH,
    NodeType.PEAK,
    NodeType.TROUGH,
    NodeType.PEAK,
)

BEAR_NODE_TYPES = (
    NodeType.PEAK,
    NodeType.TROUGH,
    NodeType.PEAK,
    NodeType.TROUGH,
    NodeType.PEAK,
    NodeType.TROUGH,
)


def detect_nds_cycles(nodes: Sequence[Node]) -> list[NDSCycle]:
    """
    Detect valid six-node bull and bear NDS cycles.

    Every consecutive six-node window is checked independently.
    Invalid windows are ignored.
    """
    if len(nodes) < CYCLE_SIZE:
        return []

    _validate_node_order(nodes)

    cycles: list[NDSCycle] = []

    for start_index in range(len(nodes) - CYCLE_SIZE + 1):
        window = nodes[start_index : start_index + CYCLE_SIZE]

        direction = _detect_cycle_direction(window)

        if direction is None:
            continue

        labeled_nodes = [
            replace(node, label=label)
            for node, label in zip(
                window,
                NODE_LABELS,
                strict=True,
            )
        ]

        z, n1, s1, n2, s2, n3 = labeled_nodes

        cycles.append(
            NDSCycle(
                direction=direction,
                z=z,
                n1=n1,
                s1=s1,
                n2=n2,
                s2=s2,
                n3=n3,
            )
        )

    return cycles


def _detect_cycle_direction(
    nodes: Sequence[Node],
) -> CycleDirection | None:
    node_types = tuple(node.node_type for node in nodes)

    if node_types == BULL_NODE_TYPES and _has_bull_structure(nodes):
        return CycleDirection.BULL

    if node_types == BEAR_NODE_TYPES and _has_bear_structure(nodes):
        return CycleDirection.BEAR

    return None


def _has_bull_structure(nodes: Sequence[Node]) -> bool:
    z, n1, s1, n2, s2, n3 = nodes

    return (
        n1.price > z.price
        and z.price < s1.price < n1.price
        and n2.price > n1.price
        and s1.price < s2.price < n2.price
        and n3.price > n2.price
    )


def _has_bear_structure(nodes: Sequence[Node]) -> bool:
    z, n1, s1, n2, s2, n3 = nodes

    return (
        n1.price < z.price
        and z.price > s1.price > n1.price
        and n2.price < n1.price
        and s1.price > s2.price > n2.price
        and n3.price < n2.price
    )


def _validate_node_order(nodes: Sequence[Node]) -> None:
    for current, next_node in pairwise(nodes):
        if current.index >= next_node.index:
            raise ValueError("Nodes must be ordered by increasing index.")
