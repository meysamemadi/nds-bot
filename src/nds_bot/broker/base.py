from typing import Protocol

from nds_bot.backtest.execution import ExecutedTrade
from nds_bot.broker.models import (
    PaperClosedTrade,
    PaperEquityPoint,
    PaperOrder,
    PaperOrderRequest,
    PaperPosition,
)


class BrokerAdapter(Protocol):
    """Minimal adapter contract used by the paper-trading runner."""

    @property
    def initial_balance(self) -> float:
        """Return the account balance before the first paper order."""
        ...

    @property
    def balance(self) -> float:
        """Return current closed-trade account balance."""
        ...

    @property
    def orders(self) -> tuple[PaperOrder, ...]:
        """Return all submitted orders."""
        ...

    @property
    def open_positions(self) -> tuple[PaperPosition, ...]:
        """Return currently open positions."""
        ...

    @property
    def closed_trades(self) -> tuple[PaperClosedTrade, ...]:
        """Return closed paper trades."""
        ...

    @property
    def equity_curve(self) -> tuple[PaperEquityPoint, ...]:
        """Return closed-trade paper equity points."""
        ...

    def submit_order(
        self,
        request: PaperOrderRequest,
    ) -> PaperOrder:
        """Submit one market order scheduled for a future candle."""
        ...

    def open_position(
        self,
        *,
        order_id: str,
        raw_trade: ExecutedTrade,
    ) -> PaperPosition | None:
        """Fill a pending order and create an open position."""
        ...

    def close_position(
        self,
        *,
        position_id: str,
        raw_trade: ExecutedTrade,
    ) -> PaperClosedTrade:
        """Close an open position from a completed execution."""
        ...

    def cancel_pending_orders(self) -> None:
        """Cancel orders whose next-candle entry never arrived."""
        ...
