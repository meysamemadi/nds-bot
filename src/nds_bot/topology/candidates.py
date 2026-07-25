from collections.abc import Sequence

from nds_bot.models import Node, NodeType


def build_alternating_nodes(nodes: Sequence[Node]) -> list[Node]:
    """
    Convert raw extrema into an alternating sequence of peaks and troughs.

    For consecutive peaks, the higher peak is retained.
    For consecutive troughs, the lower trough is retained.
    When prices are equal, the newer node is retained.
    """
    if not nodes:
        return []

    _validate_node_order(nodes)

    alternating_nodes: list[Node] = [nodes[0]]

    for candidate in nodes[1:]:
        current = alternating_nodes[-1]

        if candidate.node_type is not current.node_type:
            alternating_nodes.append(candidate)
            continue

        if _is_stronger(candidate, current):
            alternating_nodes[-1] = candidate

    return alternating_nodes


def _is_stronger(candidate: Node, current: Node) -> bool:
    """
    Determine whether a same-type candidate should replace the current node.
    """
    if candidate.node_type is NodeType.PEAK:
        return candidate.price >= current.price

    return candidate.price <= current.price


def _validate_node_order(nodes: Sequence[Node]) -> None:
    """
    Ensure that nodes are ordered by increasing candle index.
    """
    previous_index = nodes[0].index

    for node in nodes[1:]:
        if node.index <= previous_index:
            raise ValueError("Nodes must be ordered by increasing index.")

        previous_index = node.index
