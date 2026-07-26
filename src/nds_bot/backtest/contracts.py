from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal
from enum import Enum
from math import isfinite


class BelowMinimumLotPolicy(str, Enum):
    """Resolution when the risk budget cannot fund one minimum lot."""

    SKIP = "SKIP"
    RAISE = "RAISE"


@dataclass(frozen=True)
class ContractSpecification:
    """
    Broker or exchange volume constraints for one instrument.

    contract_size:
        Number of underlying units represented by one lot.

    minimum_lot:
        Smallest accepted order volume in lots.

    maximum_lot:
        Largest accepted order volume in lots.

    lot_step:
        Allowed lot-volume increment.

    below_minimum_policy:
        Resolution when conservative rounding produces a volume
        below the broker minimum.
    """

    contract_size: float = 100_000.0
    minimum_lot: float = 0.01
    maximum_lot: float = 100.0
    lot_step: float = 0.01
    below_minimum_policy: BelowMinimumLotPolicy = BelowMinimumLotPolicy.SKIP

    def __post_init__(self) -> None:
        values = (
            ("Contract size", self.contract_size),
            ("Minimum lot", self.minimum_lot),
            ("Maximum lot", self.maximum_lot),
            ("Lot step", self.lot_step),
        )

        for name, value in values:
            if not isfinite(value):
                raise ValueError(f"{name} must be finite.")

            if value <= 0:
                raise ValueError(f"{name} must be positive.")

        if self.maximum_lot < self.minimum_lot:
            raise ValueError("Maximum lot cannot be below minimum lot.")

        if self.maximum_grid_lot < self.minimum_lot:
            raise ValueError(
                "Maximum lot and lot step do not provide "
                "a valid broker volume at or above minimum lot."
            )

    @property
    def maximum_grid_lot(self) -> float:
        """Return the largest step-aligned lot not above maximum."""
        return _floor_to_step(
            self.maximum_lot,
            self.lot_step,
        )


@dataclass(frozen=True)
class PositionSize:
    """One broker-constrained position-size calculation."""

    specification: ContractSpecification

    requested_risk_amount: float
    risk_per_unit: float

    raw_quantity: float
    raw_lots: float

    lots: float
    quantity: float
    actual_risk_amount: float

    capped_at_maximum: bool

    def __post_init__(self) -> None:
        positive_values = (
            self.requested_risk_amount,
            self.risk_per_unit,
            self.raw_quantity,
            self.raw_lots,
            self.lots,
            self.quantity,
            self.actual_risk_amount,
        )

        if any(not isfinite(value) or value <= 0 for value in positive_values):
            raise ValueError("Position-size values must be finite and positive.")

        if self.lots < self.specification.minimum_lot:
            raise ValueError("Position lots cannot be below minimum lot.")

        if self.lots > self.specification.maximum_lot:
            raise ValueError("Position lots cannot exceed maximum lot.")

        tolerance = max(
            1e-12,
            self.requested_risk_amount * 1e-12,
        )

        if self.actual_risk_amount > self.requested_risk_amount + tolerance:
            raise ValueError(
                "Conservative position sizing cannot exceed the requested risk amount."
            )

    @property
    def risk_utilization_fraction(self) -> float:
        """Return the fraction of requested risk actually used."""
        return self.actual_risk_amount / self.requested_risk_amount


def calculate_position_size(
    *,
    risk_amount: float,
    risk_per_unit: float,
    specification: ContractSpecification,
) -> PositionSize | None:
    """
    Convert a monetary risk budget into broker-valid lots.

    Volume is always rounded down to the lot step so the resulting
    position does not exceed the requested risk budget.

    A raw position above maximum lot is safely capped. A raw position
    below minimum lot is skipped or rejected according to policy.
    """
    _validate_sizing_input(
        name="Risk amount",
        value=risk_amount,
    )

    _validate_sizing_input(
        name="Risk per unit",
        value=risk_per_unit,
    )

    raw_quantity = risk_amount / risk_per_unit
    raw_lots = raw_quantity / specification.contract_size

    lots = min(
        _floor_to_step(
            raw_lots,
            specification.lot_step,
        ),
        specification.maximum_grid_lot,
    )

    if lots < specification.minimum_lot:
        if specification.below_minimum_policy is BelowMinimumLotPolicy.RAISE:
            raise ValueError("Calculated position is below minimum lot.")

        return None

    quantity = lots * specification.contract_size
    actual_risk_amount = quantity * risk_per_unit

    return PositionSize(
        specification=specification,
        requested_risk_amount=risk_amount,
        risk_per_unit=risk_per_unit,
        raw_quantity=raw_quantity,
        raw_lots=raw_lots,
        lots=lots,
        quantity=quantity,
        actual_risk_amount=actual_risk_amount,
        capped_at_maximum=(raw_lots > specification.maximum_grid_lot),
    )


def _validate_sizing_input(
    *,
    name: str,
    value: float,
) -> None:
    if not isfinite(value):
        raise ValueError(f"{name} must be finite.")

    if value <= 0:
        raise ValueError(f"{name} must be positive.")


def _floor_to_step(
    value: float,
    step: float,
) -> float:
    """Round a positive decimal value down to a decimal step."""
    decimal_value = Decimal(str(value))
    decimal_step = Decimal(str(step))

    step_count = (decimal_value / decimal_step).to_integral_value(rounding=ROUND_FLOOR)

    return float(step_count * decimal_step)
