from collections.abc import Sequence

from nds_bot.models import Candle, Node, NodeType


def detect_local_extrema(
    candles: Sequence[Candle],
    *,
    window: int,
) -> list[Node]:
    """
    Detect local peaks and troughs using a symmetric candle window.

    Peak:
        The current high is greater than or equal to all neighboring highs.

    Trough:
        The current low is less than or equal to all neighboring lows.
    """
    if window < 1:
        raise ValueError("Window must be at least 1.")

    required_candles = (2 * window) + 1

    if len(candles) < required_candles:
        return []

    nodes: list[Node] = []

    for index in range(window, len(candles) - window):
        current = candles[index]

        left_neighbors = candles[index - window : index]
        right_neighbors = candles[index + 1 : index + window + 1]
        neighbors = [*left_neighbors, *right_neighbors]

        is_peak = all(current.high >= candle.high for candle in neighbors) and any(
            current.high > candle.high for candle in neighbors
        )

        is_trough = all(current.low <= candle.low for candle in neighbors) and any(
            current.low < candle.low for candle in neighbors
        )

        # A very large outside candle can satisfy both conditions.
        # Such an ambiguous candle is ignored in this first implementation.
        if is_peak and is_trough:
            continue

        if is_peak:
            nodes.append(
                Node(
                    index=index,
                    time=current.time,
                    price=current.high,
                    node_type=NodeType.PEAK,
                )
            )

        elif is_trough:
            nodes.append(
                Node(
                    index=index,
                    time=current.time,
                    price=current.low,
                    node_type=NodeType.TROUGH,
                )
            )

    return nodes
