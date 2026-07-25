from dataclasses import dataclass
from datetime import datetime
from enum import Enum


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