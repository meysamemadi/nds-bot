from dataclasses import dataclass

from nds_bot.backtest.execution import ExecutedTrade
from nds_bot.models import TradeSide


@dataclass(frozen=True)
class TradingCostPolicy:
    """
    Engineering choices for simulated trading costs.

    spread_fraction:
        Full bid-ask spread as a fraction of reference price.
        Half of the spread is applied to each execution.

    slippage_fraction:
        Adverse execution slippage applied to each fill.

    commission_fraction:
        Commission charged on notional value for each side.
    """

    spread_fraction: float = 0.0
    slippage_fraction: float = 0.0
    commission_fraction: float = 0.0

    def __post_init__(self) -> None:
        values = (
            (
                "Spread fraction",
                self.spread_fraction,
            ),
            (
                "Slippage fraction",
                self.slippage_fraction,
            ),
            (
                "Commission fraction",
                self.commission_fraction,
            ),
        )

        for name, value in values:
            if value < 0:
                raise ValueError(f"{name} cannot be negative.")

            if value >= 1:
                raise ValueError(f"{name} must be less than 1.")

        if self.adverse_fill_fraction >= 1:
            raise ValueError("Combined spread and slippage must be less than 1.")

    @property
    def adverse_fill_fraction(self) -> float:
        """
        Return the adverse fractional adjustment per fill.

        Half of the full spread plus one slippage allowance
        is applied on both entry and exit.
        """
        return self.spread_fraction / 2 + self.slippage_fraction


@dataclass(frozen=True)
class CostAdjustedTrade:
    """
    One ExecutedTrade adjusted for trading friction.

    All PnL and cost fields are expressed per unit of quantity.
    Account-level monetary values are calculated later.
    """

    trade: ExecutedTrade
    policy: TradingCostPolicy

    effective_entry_price: float
    effective_exit_price: float
    effective_stop_price: float

    gross_pnl_per_unit: float
    spread_slippage_cost_per_unit: float

    entry_commission_per_unit: float
    exit_commission_per_unit: float
    stop_commission_per_unit: float

    net_pnl_per_unit: float
    risk_per_unit: float

    def __post_init__(self) -> None:
        if (
            min(
                self.effective_entry_price,
                self.effective_exit_price,
                self.effective_stop_price,
            )
            <= 0
        ):
            raise ValueError("Cost-adjusted prices must be positive.")

        if self.spread_slippage_cost_per_unit < 0:
            raise ValueError("Spread and slippage cost cannot be negative.")

        if (
            min(
                self.entry_commission_per_unit,
                self.exit_commission_per_unit,
                self.stop_commission_per_unit,
            )
            < 0
        ):
            raise ValueError("Commission values cannot be negative.")

        if self.risk_per_unit <= 0:
            raise ValueError("Cost-adjusted risk per unit must be positive.")

    @property
    def total_commission_per_unit(self) -> float:
        """Return actual entry and exit commission."""
        return self.entry_commission_per_unit + self.exit_commission_per_unit

    @property
    def total_cost_per_unit(self) -> float:
        """Return total realized trading friction."""
        return self.spread_slippage_cost_per_unit + self.total_commission_per_unit

    @property
    def net_r_multiple(self) -> float:
        """
        Return actual net R after costs.

        Risk is based on the cost-adjusted stop scenario.
        """
        return self.net_pnl_per_unit / self.risk_per_unit


def apply_trading_costs(
    trade: ExecutedTrade,
    *,
    policy: TradingCostPolicy | None = None,
) -> CostAdjustedTrade:
    """
    Apply adverse spread, slippage, and commission.

    BUY:
        Entry executes higher.
        Exit and Stop execute lower.

    SELL:
        Entry executes lower.
        Exit and Stop execute higher.
    """
    active_policy = policy or TradingCostPolicy()
    adverse_fraction = active_policy.adverse_fill_fraction

    if trade.side is TradeSide.BUY:
        effective_entry_price = trade.entry_price * (1 + adverse_fraction)

        effective_exit_price = trade.exit_price * (1 - adverse_fraction)

        effective_stop_price = trade.stop_loss * (1 - adverse_fraction)

    else:
        effective_entry_price = trade.entry_price * (1 - adverse_fraction)

        effective_exit_price = trade.exit_price * (1 + adverse_fraction)

        effective_stop_price = trade.stop_loss * (1 + adverse_fraction)

    gross_pnl_per_unit = _directional_pnl(
        side=trade.side,
        entry_price=effective_entry_price,
        exit_price=effective_exit_price,
    )

    raw_pnl_per_unit = trade.price_pnl

    spread_slippage_cost_per_unit = max(
        0.0,
        raw_pnl_per_unit - gross_pnl_per_unit,
    )

    entry_commission_per_unit = effective_entry_price * active_policy.commission_fraction

    exit_commission_per_unit = effective_exit_price * active_policy.commission_fraction

    stop_commission_per_unit = effective_stop_price * active_policy.commission_fraction

    net_pnl_per_unit = gross_pnl_per_unit - entry_commission_per_unit - exit_commission_per_unit

    stop_gross_pnl_per_unit = _directional_pnl(
        side=trade.side,
        entry_price=effective_entry_price,
        exit_price=effective_stop_price,
    )

    stop_net_pnl_per_unit = (
        stop_gross_pnl_per_unit - entry_commission_per_unit - stop_commission_per_unit
    )

    risk_per_unit = -stop_net_pnl_per_unit

    if risk_per_unit <= 0:
        raise ValueError("Trading costs produced an invalid stop-risk distance.")

    return CostAdjustedTrade(
        trade=trade,
        policy=active_policy,
        effective_entry_price=effective_entry_price,
        effective_exit_price=effective_exit_price,
        effective_stop_price=effective_stop_price,
        gross_pnl_per_unit=gross_pnl_per_unit,
        spread_slippage_cost_per_unit=(spread_slippage_cost_per_unit),
        entry_commission_per_unit=(entry_commission_per_unit),
        exit_commission_per_unit=(exit_commission_per_unit),
        stop_commission_per_unit=(stop_commission_per_unit),
        net_pnl_per_unit=net_pnl_per_unit,
        risk_per_unit=risk_per_unit,
    )


def _directional_pnl(
    *,
    side: TradeSide,
    entry_price: float,
    exit_price: float,
) -> float:
    """Calculate directional price PnL per unit."""
    if side is TradeSide.BUY:
        return exit_price - entry_price

    return entry_price - exit_price
