from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from nds_bot.backtest.costs import CostAdjustedTrade
from nds_bot.backtest.execution import ExecutedTrade
from nds_bot.backtest.margin import MarginCheck
from nds_bot.models import TradeSide
from nds_bot.signals import TradeSignal


class PaperOrderStatus(str, Enum):
    """Lifecycle state of a paper-market order."""

    PENDING = "PENDING"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class PaperOrderReason(str, Enum):
    """Machine-readable reason attached to a final order state."""

    OVERLAPPING_POSITION = "OVERLAPPING_POSITION"
    BELOW_MINIMUM_LOT = "BELOW_MINIMUM_LOT"
    INSUFFICIENT_MARGIN = "INSUFFICIENT_MARGIN"
    NO_ENTRY_CANDLE = "NO_ENTRY_CANDLE"


@dataclass(frozen=True)
class PaperOrderRequest:
    """One signal-derived market order scheduled for the next candle."""

    symbol: str
    signal: TradeSignal

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("Paper order symbol cannot be empty.")

    @property
    def scheduled_entry_index(self) -> int:
        return self.signal.generated_at_index + 1


@dataclass(frozen=True)
class PaperOrder:
    """Current paper-order state stored by a broker adapter."""

    order_id: str
    request: PaperOrderRequest
    status: PaperOrderStatus
    created_index: int
    created_time: datetime
    status_reason: str | None = None
    filled_index: int | None = None
    filled_time: datetime | None = None
    closed_index: int | None = None
    closed_time: datetime | None = None

    def __post_init__(self) -> None:
        if not self.order_id.strip():
            raise ValueError("Paper order id cannot be empty.")

        if self.created_index < 0:
            raise ValueError("Paper order creation index cannot be negative.")

    @property
    def side(self) -> TradeSide:
        return self.request.signal.side

    @property
    def signal(self) -> TradeSignal:
        return self.request.signal

    @property
    def symbol(self) -> str:
        return self.request.symbol

    @property
    def scheduled_entry_index(self) -> int:
        return self.request.scheduled_entry_index


@dataclass(frozen=True)
class PaperPosition:
    """One currently open position inside a paper broker."""

    position_id: str
    order_id: str
    symbol: str
    signal: TradeSignal

    side: TradeSide
    entry_index: int
    entry_time: datetime
    raw_entry_price: float
    effective_entry_price: float

    stop_loss: float
    take_profit: float

    requested_risk_amount: float
    actual_risk_amount: float
    quantity: float
    lots: float | None

    margin_check: MarginCheck | None

    def __post_init__(self) -> None:
        if not self.position_id.strip():
            raise ValueError("Paper position id cannot be empty.")

        if self.entry_index < 0:
            raise ValueError("Paper position entry index cannot be negative.")

        positive_values = (
            self.raw_entry_price,
            self.effective_entry_price,
            self.stop_loss,
            self.take_profit,
            self.requested_risk_amount,
            self.actual_risk_amount,
            self.quantity,
        )

        if any(value <= 0 for value in positive_values):
            raise ValueError("Paper position values must be positive.")

        if self.lots is not None and self.lots <= 0:
            raise ValueError("Paper position lots must be positive.")


@dataclass(frozen=True)
class PaperClosedTrade:
    """One paper position closed by a completed raw execution."""

    trade_id: str
    position: PaperPosition
    raw_trade: ExecutedTrade
    cost_adjustment: CostAdjustedTrade

    balance_before: float
    gross_monetary_pnl: float
    spread_slippage_cost: float
    commission_amount: float
    total_cost_amount: float
    net_monetary_pnl: float
    balance_after: float

    def __post_init__(self) -> None:
        if not self.trade_id.strip():
            raise ValueError("Paper trade id cannot be empty.")

        if self.balance_before <= 0 or self.balance_after <= 0:
            raise ValueError("Paper trade balances must be positive.")

        if (
            min(
                self.spread_slippage_cost,
                self.commission_amount,
                self.total_cost_amount,
            )
            < 0
        ):
            raise ValueError("Paper trading costs cannot be negative.")

    @property
    def order_id(self) -> str:
        return self.position.order_id

    @property
    def symbol(self) -> str:
        return self.position.symbol

    @property
    def side(self) -> TradeSide:
        return self.position.side

    @property
    def net_r_multiple(self) -> float:
        return self.net_monetary_pnl / self.position.actual_risk_amount

    @property
    def is_winner(self) -> bool:
        return self.net_monetary_pnl > 0


@dataclass(frozen=True)
class PaperEquityPoint:
    """One closed-trade point on a paper account equity curve."""

    event_number: int
    time: datetime | None
    balance: float
    peak_balance: float
    drawdown_amount: float
    drawdown_fraction: float

    def __post_init__(self) -> None:
        if self.event_number < 0:
            raise ValueError("Paper equity event number cannot be negative.")

        if self.balance <= 0:
            raise ValueError("Paper equity balance must be positive.")

        if self.peak_balance < self.balance:
            raise ValueError("Paper equity peak cannot be below balance.")

        if self.drawdown_amount < 0:
            raise ValueError("Paper drawdown amount cannot be negative.")

        if not 0 <= self.drawdown_fraction < 1:
            raise ValueError("Paper drawdown fraction must be between 0 and 1.")
