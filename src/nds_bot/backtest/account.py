from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from itertools import pairwise

from nds_bot.backtest.costs import (
    CostAdjustedTrade,
    TradingCostPolicy,
    apply_trading_costs,
)
from nds_bot.backtest.execution import ExecutedTrade


class OverlapPolicy(str, Enum):
    """
    Define how account simulation handles overlapping trades.

    SKIP:
        Ignore a new trade while a previous accepted trade
        is still open.

    RAISE:
        Stop simulation with an error when overlap is detected.
    """

    SKIP = "SKIP"
    RAISE = "RAISE"


@dataclass(frozen=True)
class AccountPolicy:
    """
    Account-level engineering choices.

    initial_balance:
        Starting account balance in account-currency units.

    risk_fraction:
        Fraction of current balance risked on each trade.

    overlap_policy:
        Resolution rule for overlapping trades.
    """

    initial_balance: float = 10_000.0
    risk_fraction: float = 0.01
    overlap_policy: OverlapPolicy = OverlapPolicy.SKIP

    def __post_init__(self) -> None:
        if self.initial_balance <= 0:
            raise ValueError("Initial balance must be positive.")

        if not 0 < self.risk_fraction < 1:
            raise ValueError("Risk fraction must be greater than 0 and less than 1.")


@dataclass(frozen=True)
class SizedTrade:
    """
    One account-sized trade after trading costs.

    monetary_pnl is net of spread, slippage, and commission.
    """

    trade: ExecutedTrade
    cost_adjustment: CostAdjustedTrade

    balance_before: float
    risk_amount: float
    quantity: float

    gross_monetary_pnl: float
    spread_slippage_cost: float
    commission_amount: float
    total_cost_amount: float

    monetary_pnl: float
    balance_after: float

    def __post_init__(self) -> None:
        if self.balance_before <= 0:
            raise ValueError("Balance before trade must be positive.")

        if self.risk_amount <= 0:
            raise ValueError("Trade risk amount must be positive.")

        if self.quantity <= 0:
            raise ValueError("Trade quantity must be positive.")

        if (
            min(
                self.spread_slippage_cost,
                self.commission_amount,
                self.total_cost_amount,
            )
            < 0
        ):
            raise ValueError("Trading costs cannot be negative.")

        if self.balance_after <= 0:
            raise ValueError("Balance after trade must be positive.")

    @property
    def r_multiple(self) -> float:
        """Return realized net R after all costs."""
        return self.monetary_pnl / self.risk_amount

    @property
    def gross_r_multiple(self) -> float:
        """Return gross R before realized costs."""
        return self.gross_monetary_pnl / self.risk_amount

    @property
    def is_winner(self) -> bool:
        return self.monetary_pnl > 0

    @property
    def monetary_return_fraction(self) -> float:
        return self.monetary_pnl / self.balance_before


@dataclass(frozen=True)
class EquityPoint:
    """
    One point on the closed-trade equity curve.

    The first point represents initial account balance.
    """

    trade_number: int
    exit_index: int | None
    exit_time: datetime | None

    balance: float
    peak_balance: float
    drawdown_amount: float
    drawdown_fraction: float

    def __post_init__(self) -> None:
        if self.trade_number < 0:
            raise ValueError("Trade number cannot be negative.")

        if self.balance <= 0:
            raise ValueError("Equity balance must be positive.")

        if self.peak_balance < self.balance:
            raise ValueError("Peak balance cannot be below current balance.")

        if self.drawdown_amount < 0:
            raise ValueError("Drawdown amount cannot be negative.")

        if not 0 <= self.drawdown_fraction < 1:
            raise ValueError("Drawdown fraction must be between 0 and 1.")


@dataclass(frozen=True)
class AccountMetrics:
    """Summary of account-level performance."""

    accepted_trade_count: int
    skipped_overlap_count: int

    initial_balance: float
    ending_balance: float

    total_gross_pnl: float
    total_spread_slippage_cost: float
    total_commission: float
    total_cost: float

    net_profit: float
    return_fraction: float

    maximum_drawdown_amount: float
    maximum_drawdown_fraction: float


@dataclass(frozen=True)
class AccountResult:
    """Complete account and position-size simulation."""

    policy: AccountPolicy
    cost_policy: TradingCostPolicy

    trades: tuple[SizedTrade, ...]
    skipped_overlapping_trades: tuple[ExecutedTrade, ...]

    equity_curve: tuple[EquityPoint, ...]
    metrics: AccountMetrics


def simulate_account(
    trades: Sequence[ExecutedTrade],
    *,
    policy: AccountPolicy | None = None,
    cost_policy: TradingCostPolicy | None = None,
) -> AccountResult:
    """
    Apply dynamic position sizing and trading costs.

    Position size is based on all-in stop risk, including
    spread, slippage, and entry/stop commission.
    """
    active_policy = policy or AccountPolicy()
    active_cost_policy = cost_policy or TradingCostPolicy()

    _validate_trade_order(trades)

    balance = active_policy.initial_balance
    peak_balance = balance
    active_until_index: int | None = None

    sized_trades: list[SizedTrade] = []
    skipped_trades: list[ExecutedTrade] = []

    equity_curve: list[EquityPoint] = [
        EquityPoint(
            trade_number=0,
            exit_index=None,
            exit_time=None,
            balance=balance,
            peak_balance=peak_balance,
            drawdown_amount=0.0,
            drawdown_fraction=0.0,
        )
    ]

    for trade in trades:
        overlaps = active_until_index is not None and trade.entry_index <= active_until_index

        if overlaps:
            if active_policy.overlap_policy is OverlapPolicy.RAISE:
                raise ValueError(f"Overlapping trade detected at entry index {trade.entry_index}.")

            skipped_trades.append(trade)
            continue

        cost_adjustment = apply_trading_costs(
            trade,
            policy=active_cost_policy,
        )

        risk_amount = balance * active_policy.risk_fraction

        quantity = risk_amount / cost_adjustment.risk_per_unit

        gross_monetary_pnl = cost_adjustment.gross_pnl_per_unit * quantity

        spread_slippage_cost = cost_adjustment.spread_slippage_cost_per_unit * quantity

        commission_amount = cost_adjustment.total_commission_per_unit * quantity

        total_cost_amount = spread_slippage_cost + commission_amount

        monetary_pnl = cost_adjustment.net_pnl_per_unit * quantity

        balance_after = balance + monetary_pnl

        if balance_after <= 0:
            raise ValueError("Trade result would reduce account balance to zero or below.")

        sized_trade = SizedTrade(
            trade=trade,
            cost_adjustment=cost_adjustment,
            balance_before=balance,
            risk_amount=risk_amount,
            quantity=quantity,
            gross_monetary_pnl=gross_monetary_pnl,
            spread_slippage_cost=(spread_slippage_cost),
            commission_amount=commission_amount,
            total_cost_amount=total_cost_amount,
            monetary_pnl=monetary_pnl,
            balance_after=balance_after,
        )

        sized_trades.append(sized_trade)

        balance = balance_after
        active_until_index = trade.exit_index

        peak_balance = max(
            peak_balance,
            balance,
        )

        drawdown_amount = peak_balance - balance

        drawdown_fraction = drawdown_amount / peak_balance

        equity_curve.append(
            EquityPoint(
                trade_number=len(sized_trades),
                exit_index=trade.exit_index,
                exit_time=trade.exit_time,
                balance=balance,
                peak_balance=peak_balance,
                drawdown_amount=drawdown_amount,
                drawdown_fraction=drawdown_fraction,
            )
        )

    maximum_drawdown_amount = max(point.drawdown_amount for point in equity_curve)

    maximum_drawdown_fraction = max(point.drawdown_fraction for point in equity_curve)

    total_gross_pnl = sum(trade.gross_monetary_pnl for trade in sized_trades)

    total_spread_slippage_cost = sum(trade.spread_slippage_cost for trade in sized_trades)

    total_commission = sum(trade.commission_amount for trade in sized_trades)

    total_cost = sum(trade.total_cost_amount for trade in sized_trades)

    metrics = AccountMetrics(
        accepted_trade_count=len(sized_trades),
        skipped_overlap_count=len(skipped_trades),
        initial_balance=active_policy.initial_balance,
        ending_balance=balance,
        total_gross_pnl=total_gross_pnl,
        total_spread_slippage_cost=(total_spread_slippage_cost),
        total_commission=total_commission,
        total_cost=total_cost,
        net_profit=(balance - active_policy.initial_balance),
        return_fraction=(balance / active_policy.initial_balance - 1),
        maximum_drawdown_amount=(maximum_drawdown_amount),
        maximum_drawdown_fraction=(maximum_drawdown_fraction),
    )

    return AccountResult(
        policy=active_policy,
        cost_policy=active_cost_policy,
        trades=tuple(sized_trades),
        skipped_overlapping_trades=tuple(skipped_trades),
        equity_curve=tuple(equity_curve),
        metrics=metrics,
    )


def _validate_trade_order(
    trades: Sequence[ExecutedTrade],
) -> None:
    for current, next_trade in pairwise(trades):
        if current.entry_index > next_trade.entry_index:
            raise ValueError("Trades must be ordered by increasing entry index.")
