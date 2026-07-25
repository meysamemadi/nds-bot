from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from itertools import pairwise


class NodeType(str, Enum):
    PEAK = "PEAK"
    TROUGH = "TROUGH"


class NodeLabel(str, Enum):
    Z = "Z"
    N1 = "N1"
    S1 = "S1"
    N2 = "N2"
    S2 = "S2"
    N3 = "N3"


class TradeSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class CycleDirection(str, Enum):
    BULL = "BULL"
    BEAR = "BEAR"


@dataclass(frozen=True)
class Candle:
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self) -> None:
        if min(self.open, self.high, self.low, self.close) <= 0:
            raise ValueError("Candle prices must be positive.")

        if self.high < max(self.open, self.close, self.low):
            raise ValueError("High price is invalid.")

        if self.low > min(self.open, self.close, self.high):
            raise ValueError("Low price is invalid.")

        if self.volume < 0:
            raise ValueError("Volume cannot be negative.")


@dataclass(frozen=True)
class Node:
    index: int
    time: datetime
    price: float
    node_type: NodeType
    label: NodeLabel | None = None

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError("Node index cannot be negative.")

        if self.price <= 0:
            raise ValueError("Node price must be positive.")


@dataclass(frozen=True)
class NDSCycle:
    direction: CycleDirection
    z: Node
    n1: Node
    s1: Node
    n2: Node
    s2: Node
    n3: Node

    @property
    def nodes(self) -> tuple[Node, Node, Node, Node, Node, Node]:
        return (
            self.z,
            self.n1,
            self.s1,
            self.n2,
            self.s2,
            self.n3,
        )

    def __post_init__(self) -> None:
        expected_labels = (
            NodeLabel.Z,
            NodeLabel.N1,
            NodeLabel.S1,
            NodeLabel.N2,
            NodeLabel.S2,
            NodeLabel.N3,
        )

        actual_labels = tuple(node.label for node in self.nodes)

        if actual_labels != expected_labels:
            raise ValueError("Cycle nodes must have the correct NDS labels.")

        indexes = tuple(node.index for node in self.nodes)

        if any(current_index >= next_index for current_index, next_index in pairwise(indexes)):
            raise ValueError("Cycle nodes must be ordered by increasing index.")
