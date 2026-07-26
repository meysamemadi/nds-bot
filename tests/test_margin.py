from pathlib import Path

import pytest

from nds_bot.backtest.account import (
    AccountPolicy,
    simulate_account,
)
from nds_bot.backtest.contracts import ContractSpecification
from nds_bot.backtest.costs import TradingCostPolicy
from nds_bot.backtest.execution import ExecutedTrade
from nds_bot.backtest.margin import (
    InsufficientMarginPolicy,
    MarginPolicy,
    calculate_margin,
)
from nds_bot.backtest.runner import run_backtest
from nds_bot.data.csv_loader import load_candles_csv
from nds_bot.pipeline import ScanConfig

SAMPLE_PATH = Path("data/samples/documented_bull_cycle_execution.csv")


def build_sell_trade() -> ExecutedTrade:
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


def test_margin_policy_defaults() -> None:
    policy = MarginPolicy()

    assert policy.leverage == pytest.approx(100.0)
    assert policy.insufficient_margin_policy is InsufficientMarginPolicy.SKIP


def test_calculates_margin_values() -> None:
    check = calculate_margin(
        equity=10_000.0,
        quantity=23_000.0,
        entry_price=1.09083635,
        policy=MarginPolicy(leverage=100.0),
    )

    assert check.notional_value == pytest.approx(25_089.23605)
    assert check.margin_required == pytest.approx(250.8923605)
    assert check.used_margin == pytest.approx(250.8923605)
    assert check.free_margin_after_entry == pytest.approx(9_749.1076395)
    assert check.margin_utilization_fraction == pytest.approx(0.02508923605)
    assert check.margin_level_fraction == pytest.approx(39.857730144)
    assert check.is_sufficient is True


def test_exact_equity_is_sufficient() -> None:
    check = calculate_margin(
        equity=1_000.0,
        quantity=100.0,
        entry_price=10.0,
        policy=MarginPolicy(leverage=1.0),
    )

    assert check.margin_required == pytest.approx(1_000.0)
    assert check.free_margin_after_entry == pytest.approx(0.0)
    assert check.margin_utilization_fraction == pytest.approx(1.0)
    assert check.margin_level_fraction == pytest.approx(1.0)
    assert check.is_sufficient is True


def test_account_records_margin_values() -> None:
    trade = build_sell_trade()

    result = simulate_account(
        [trade],
        policy=AccountPolicy(),
        cost_policy=build_cost_policy(),
        contract_specification=ContractSpecification(),
        margin_policy=MarginPolicy(leverage=100.0),
    )

    sized_trade = result.trades[0]

    assert sized_trade.margin_required == pytest.approx(250.8923605)
    assert sized_trade.free_margin_after_entry == pytest.approx(9_749.1076395)
    assert sized_trade.margin_utilization_fraction == pytest.approx(0.02508923605)
    assert sized_trade.margin_level_fraction == pytest.approx(39.857730144)
    assert sized_trade.balance_after == pytest.approx(10_162.297202622002)

    metrics = result.metrics

    assert metrics.skipped_insufficient_margin_count == 0
    assert metrics.maximum_margin_required == pytest.approx(250.8923605)
    assert metrics.maximum_margin_utilization == pytest.approx(0.02508923605)
    assert metrics.minimum_free_margin_after_entry == pytest.approx(9_749.1076395)


def test_insufficient_margin_is_skipped_by_default() -> None:
    trade = build_sell_trade()

    result = simulate_account(
        [trade],
        policy=AccountPolicy(),
        cost_policy=build_cost_policy(),
        contract_specification=ContractSpecification(),
        margin_policy=MarginPolicy(leverage=1.0),
    )

    assert result.trades == ()
    assert result.skipped_insufficient_margin_trades == (trade,)
    assert result.metrics.accepted_trade_count == 0
    assert result.metrics.skipped_insufficient_margin_count == 1
    assert result.metrics.ending_balance == pytest.approx(10_000.0)
    assert result.metrics.maximum_margin_required == pytest.approx(0.0)
    assert result.metrics.minimum_free_margin_after_entry is None


def test_insufficient_margin_policy_can_raise() -> None:
    trade = build_sell_trade()

    policy = MarginPolicy(
        leverage=1.0,
        insufficient_margin_policy=(InsufficientMarginPolicy.RAISE),
    )

    with pytest.raises(
        ValueError,
        match="Insufficient margin for trade",
    ):
        simulate_account(
            [trade],
            policy=AccountPolicy(),
            cost_policy=build_cost_policy(),
            contract_specification=ContractSpecification(),
            margin_policy=policy,
        )


def test_margin_disabled_preserves_previous_behavior() -> None:
    trade = build_sell_trade()

    result = simulate_account(
        [trade],
        policy=AccountPolicy(),
        cost_policy=build_cost_policy(),
        contract_specification=ContractSpecification(),
    )

    sized_trade = result.trades[0]

    assert result.margin_policy is None
    assert sized_trade.margin_check is None
    assert sized_trade.margin_required is None
    assert sized_trade.free_margin_after_entry is None
    assert result.metrics.maximum_margin_required == pytest.approx(0.0)
    assert result.metrics.maximum_margin_utilization == pytest.approx(0.0)
    assert result.metrics.minimum_free_margin_after_entry is None
    assert result.metrics.ending_balance == pytest.approx(10_162.297202622002)


def test_runner_passes_margin_policy_to_account() -> None:
    candles = load_candles_csv(SAMPLE_PATH)

    result = run_backtest(
        candles,
        config=ScanConfig(extrema_window=1),
        account_policy=AccountPolicy(),
        cost_policy=build_cost_policy(),
        contract_specification=ContractSpecification(),
        margin_policy=MarginPolicy(leverage=100.0),
    )

    assert result.account is not None
    assert result.account.margin_policy is not None
    assert result.account.margin_policy.leverage == pytest.approx(100.0)
    assert result.account.trades[0].margin_required == pytest.approx(250.8923605)


def test_margin_policy_requires_account_simulation() -> None:
    candles = load_candles_csv(SAMPLE_PATH)

    with pytest.raises(
        ValueError,
        match="Margin policy requires account simulation",
    ):
        run_backtest(
            candles,
            config=ScanConfig(extrema_window=1),
            margin_policy=MarginPolicy(),
        )


@pytest.mark.parametrize(
    "leverage",
    [0.0, 0.5, float("inf")],
)
def test_invalid_margin_policy_is_rejected(
    leverage: float,
) -> None:
    with pytest.raises(ValueError):
        MarginPolicy(leverage=leverage)


@pytest.mark.parametrize(
    "kwargs",
    [
        {
            "equity": 0.0,
            "quantity": 1.0,
            "entry_price": 1.0,
        },
        {
            "equity": 1.0,
            "quantity": 0.0,
            "entry_price": 1.0,
        },
        {
            "equity": 1.0,
            "quantity": 1.0,
            "entry_price": 0.0,
        },
    ],
)
def test_invalid_margin_inputs_are_rejected(
    kwargs: dict[str, float],
) -> None:
    with pytest.raises(ValueError):
        calculate_margin(
            **kwargs,
            policy=MarginPolicy(),
        )
