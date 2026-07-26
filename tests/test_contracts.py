from pathlib import Path

import pytest

from nds_bot.backtest.account import (
    AccountPolicy,
    simulate_account,
)
from nds_bot.backtest.contracts import (
    BelowMinimumLotPolicy,
    ContractSpecification,
    calculate_position_size,
)
from nds_bot.backtest.costs import TradingCostPolicy
from nds_bot.backtest.runner import run_backtest
from nds_bot.data.csv_loader import load_candles_csv
from nds_bot.pipeline import ScanConfig

SAMPLE_PATH = Path("data/samples/documented_bull_cycle_execution.csv")


def build_sell_trade():
    candles = load_candles_csv(SAMPLE_PATH)

    result = run_backtest(
        candles,
        config=ScanConfig(extrema_window=1),
    )

    return result.execution.trades[0]


def build_cost_policy() -> TradingCostPolicy:
    return TradingCostPolicy(
        spread_fraction=0.0002,
        slippage_fraction=0.00005,
        commission_fraction=0.0001,
    )


def test_contract_specification_defaults() -> None:
    specification = ContractSpecification()

    assert specification.contract_size == pytest.approx(100_000.0)
    assert specification.minimum_lot == pytest.approx(0.01)
    assert specification.maximum_lot == pytest.approx(100.0)
    assert specification.lot_step == pytest.approx(0.01)
    assert specification.maximum_grid_lot == pytest.approx(100.0)


def test_position_size_rounds_down_to_lot_step() -> None:
    specification = ContractSpecification()

    position = calculate_position_size(
        risk_amount=100.0,
        risk_per_unit=0.004346450057,
        specification=specification,
    )

    assert position is not None
    assert position.raw_quantity == pytest.approx(23_007.28150297)
    assert position.raw_lots == pytest.approx(0.2300728150297)
    assert position.lots == pytest.approx(0.23)
    assert position.quantity == pytest.approx(23_000.0)
    assert position.actual_risk_amount == pytest.approx(99.968351311)
    assert position.risk_utilization_fraction == pytest.approx(0.99968351311)
    assert position.capped_at_maximum is False


def test_position_size_caps_at_maximum_lot() -> None:
    specification = ContractSpecification(
        maximum_lot=0.50,
    )

    position = calculate_position_size(
        risk_amount=10_000.0,
        risk_per_unit=0.01,
        specification=specification,
    )

    assert position is not None
    assert position.raw_lots == pytest.approx(10.0)
    assert position.lots == pytest.approx(0.50)
    assert position.quantity == pytest.approx(50_000.0)
    assert position.actual_risk_amount == pytest.approx(500.0)
    assert position.capped_at_maximum is True


def test_below_minimum_lot_is_skipped_by_default() -> None:
    position = calculate_position_size(
        risk_amount=1.0,
        risk_per_unit=0.01,
        specification=ContractSpecification(),
    )

    assert position is None


def test_below_minimum_policy_can_raise() -> None:
    specification = ContractSpecification(
        below_minimum_policy=(BelowMinimumLotPolicy.RAISE),
    )

    with pytest.raises(
        ValueError,
        match="below minimum lot",
    ):
        calculate_position_size(
            risk_amount=1.0,
            risk_per_unit=0.01,
            specification=specification,
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"contract_size": 0.0},
        {"minimum_lot": 0.0},
        {"maximum_lot": 0.005},
        {"lot_step": 0.0},
        {
            "minimum_lot": 0.015,
            "maximum_lot": 0.019,
            "lot_step": 0.01,
        },
    ],
)
def test_invalid_contract_specification_is_rejected(
    kwargs: dict[str, float],
) -> None:
    with pytest.raises(ValueError):
        ContractSpecification(**kwargs)


@pytest.mark.parametrize(
    ("risk_amount", "risk_per_unit"),
    [
        (0.0, 0.01),
        (100.0, 0.0),
    ],
)
def test_invalid_position_size_inputs_are_rejected(
    risk_amount: float,
    risk_per_unit: float,
) -> None:
    with pytest.raises(ValueError):
        calculate_position_size(
            risk_amount=risk_amount,
            risk_per_unit=risk_per_unit,
            specification=ContractSpecification(),
        )


def test_account_uses_broker_lot_size() -> None:
    trade = build_sell_trade()

    result = simulate_account(
        [trade],
        policy=AccountPolicy(
            initial_balance=10_000.0,
            risk_fraction=0.01,
        ),
        cost_policy=build_cost_policy(),
        contract_specification=ContractSpecification(),
    )

    sized_trade = result.trades[0]

    assert sized_trade.risk_amount == pytest.approx(100.0)
    assert sized_trade.actual_risk_amount == pytest.approx(99.96835131100076)
    assert sized_trade.raw_quantity == pytest.approx(23_007.28150297)
    assert sized_trade.lots == pytest.approx(0.23)
    assert sized_trade.quantity == pytest.approx(23_000.0)
    assert sized_trade.risk_utilization_fraction == pytest.approx(0.99968351311)
    assert sized_trade.monetary_pnl == pytest.approx(162.297202622002)
    assert sized_trade.balance_after == pytest.approx(10_162.297202622002)
    assert sized_trade.r_multiple == pytest.approx(1.6234858382)

    metrics = result.metrics

    assert metrics.total_requested_risk == pytest.approx(100.0)
    assert metrics.total_actual_risk == pytest.approx(99.96835131100076)
    assert metrics.mean_risk_utilization == pytest.approx(0.99968351311)


def test_account_preserves_exact_quantity_without_contract_spec() -> None:
    trade = build_sell_trade()

    result = simulate_account(
        [trade],
        policy=AccountPolicy(),
        cost_policy=build_cost_policy(),
    )

    sized_trade = result.trades[0]

    assert sized_trade.position_size is None
    assert sized_trade.lots is None
    assert sized_trade.quantity == pytest.approx(23_007.28150297)
    assert sized_trade.actual_risk_amount == pytest.approx(100.0)
    assert result.metrics.ending_balance == pytest.approx(10_162.34858382)


def test_account_skips_trade_below_minimum_lot() -> None:
    trade = build_sell_trade()

    result = simulate_account(
        [trade],
        policy=AccountPolicy(
            initial_balance=10_000.0,
            risk_fraction=0.000001,
        ),
        contract_specification=ContractSpecification(),
    )

    assert result.trades == ()
    assert result.skipped_minimum_lot_trades == (trade,)
    assert result.metrics.accepted_trade_count == 0
    assert result.metrics.skipped_minimum_lot_count == 1
    assert result.metrics.ending_balance == pytest.approx(10_000.0)


def test_runner_passes_contract_specification_to_account() -> None:
    candles = load_candles_csv(SAMPLE_PATH)

    result = run_backtest(
        candles,
        config=ScanConfig(extrema_window=1),
        account_policy=AccountPolicy(),
        cost_policy=build_cost_policy(),
        contract_specification=ContractSpecification(),
    )

    assert result.account is not None
    assert result.account.contract_specification is not None
    assert result.account.trades[0].lots == pytest.approx(0.23)


def test_contract_specification_requires_account_simulation() -> None:
    candles = load_candles_csv(SAMPLE_PATH)

    with pytest.raises(
        ValueError,
        match="Contract specification requires account simulation",
    ):
        run_backtest(
            candles,
            config=ScanConfig(extrema_window=1),
            contract_specification=ContractSpecification(),
        )
