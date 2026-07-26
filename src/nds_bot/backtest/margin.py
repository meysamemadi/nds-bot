from dataclasses import dataclass
from enum import Enum
from math import isfinite


class InsufficientMarginPolicy(str, Enum):
    """Resolution when a position cannot be funded by account equity."""

    SKIP = "SKIP"
    RAISE = "RAISE"


@dataclass(frozen=True)
class MarginPolicy:
    """
    Engineering choices for leveraged margin simulation.

    leverage:
        Notional exposure divided by required margin. A leverage of
        100 means one currency unit of margin controls 100 units of
        notional exposure.

    insufficient_margin_policy:
        Resolution when required margin exceeds account equity.

    Assumption:
        Instrument notional is expressed in account-currency units as
        quantity multiplied by the cost-adjusted entry price. Currency
        conversion and cross-currency margin are not modeled yet.
    """

    leverage: float = 100.0
    insufficient_margin_policy: InsufficientMarginPolicy = InsufficientMarginPolicy.SKIP

    def __post_init__(self) -> None:
        if not isfinite(self.leverage):
            raise ValueError("Leverage must be finite.")

        if self.leverage < 1:
            raise ValueError("Leverage must be at least 1.")


@dataclass(frozen=True)
class MarginCheck:
    """One entry-time margin calculation for a proposed position."""

    policy: MarginPolicy

    equity_before: float
    quantity: float
    entry_price: float

    notional_value: float
    margin_required: float
    free_margin_after_entry: float
    margin_utilization_fraction: float
    margin_level_fraction: float
    is_sufficient: bool

    def __post_init__(self) -> None:
        positive_values = (
            self.equity_before,
            self.quantity,
            self.entry_price,
            self.notional_value,
            self.margin_required,
            self.margin_utilization_fraction,
            self.margin_level_fraction,
        )

        if any(not isfinite(value) or value <= 0 for value in positive_values):
            raise ValueError("Margin values must be finite and positive.")

        if not isfinite(self.free_margin_after_entry):
            raise ValueError("Free margin must be finite.")

        tolerance = max(
            1e-12,
            self.equity_before * 1e-12,
        )

        expected_sufficient = self.margin_required <= self.equity_before + tolerance

        if self.is_sufficient != expected_sufficient:
            raise ValueError("Margin sufficiency is inconsistent with equity and required margin.")

    @property
    def used_margin(self) -> float:
        """Return margin reserved by the accepted position."""
        return self.margin_required


def calculate_margin(
    *,
    equity: float,
    quantity: float,
    entry_price: float,
    policy: MarginPolicy,
) -> MarginCheck:
    """
    Calculate entry-time notional, margin, and free margin.

    Required margin equals notional value divided by leverage.
    The calculation is account-currency correct only when quantity
    times entry price is already denominated in the account currency.
    """
    _validate_positive_input(
        name="Equity",
        value=equity,
    )
    _validate_positive_input(
        name="Quantity",
        value=quantity,
    )
    _validate_positive_input(
        name="Entry price",
        value=entry_price,
    )

    notional_value = quantity * entry_price
    margin_required = notional_value / policy.leverage
    free_margin_after_entry = equity - margin_required

    margin_utilization_fraction = margin_required / equity
    margin_level_fraction = equity / margin_required

    tolerance = max(
        1e-12,
        equity * 1e-12,
    )

    return MarginCheck(
        policy=policy,
        equity_before=equity,
        quantity=quantity,
        entry_price=entry_price,
        notional_value=notional_value,
        margin_required=margin_required,
        free_margin_after_entry=free_margin_after_entry,
        margin_utilization_fraction=(margin_utilization_fraction),
        margin_level_fraction=margin_level_fraction,
        is_sufficient=(margin_required <= equity + tolerance),
    )


def _validate_positive_input(
    *,
    name: str,
    value: float,
) -> None:
    if not isfinite(value):
        raise ValueError(f"{name} must be finite.")

    if value <= 0:
        raise ValueError(f"{name} must be positive.")
