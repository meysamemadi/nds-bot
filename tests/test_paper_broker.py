from pathlib import Path

import pytest

from nds_bot.backtest.runner import run_backtest
from nds_bot.broker.models import (
    PaperOrderRequest,
    PaperOrderStatus,
)
from nds_bot.broker.paper import PaperBroker
from nds_bot.data.csv_loader import load_candles_csv
from nds_bot.pipeline import ScanConfig

SAMPLE_PATH = Path("data/samples/documented_bull_cycle_execution.csv")


def build_raw_trade():
    candles = load_candles_csv(SAMPLE_PATH)
    result = run_backtest(
        candles,
        config=ScanConfig(extrema_window=1),
    )
    return result.execution.trades[0]


def test_paper_broker_opens_and_closes_order() -> None:
    raw_trade = build_raw_trade()
    broker = PaperBroker()

    order = broker.submit_order(
        PaperOrderRequest(
            symbol="EURUSD",
            signal=raw_trade.signal,
        )
    )

    position = broker.open_position(
        order_id=order.order_id,
        raw_trade=raw_trade,
    )

    assert position is not None
    assert broker.orders[0].status is PaperOrderStatus.OPEN
    assert len(broker.open_positions) == 1

    closed_trade = broker.close_position(
        position_id=position.position_id,
        raw_trade=raw_trade,
    )

    assert broker.orders[0].status is PaperOrderStatus.CLOSED
    assert broker.open_positions == ()
    assert len(broker.closed_trades) == 1
    assert closed_trade.net_r_multiple == pytest.approx(2.0)
    assert broker.balance == pytest.approx(10_200.0)


def test_paper_broker_cancels_unfilled_order() -> None:
    raw_trade = build_raw_trade()
    broker = PaperBroker()

    broker.submit_order(
        PaperOrderRequest(
            symbol="EURUSD",
            signal=raw_trade.signal,
        )
    )
    broker.cancel_pending_orders()

    order = broker.orders[0]
    assert order.status is PaperOrderStatus.CANCELLED
    assert order.status_reason == "NO_ENTRY_CANDLE"
