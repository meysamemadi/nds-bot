from dataclasses import replace
from pathlib import Path

import pytest

from nds_bot.backtest.account import (
    AccountPolicy,
    simulate_account,
)
from nds_bot.backtest.costs import (
    TradingCostPolicy,
    apply_trading_costs,
)
from nds_bot.backtest.execution import ExecutedTrade
from nds_bot.backtest.runner import run_backtest
from nds_bot.data.csv_loader import load_candles_csv
from nds_bot.models import TradeSide
from nds_bot.pipeline import ScanConfig


def build_sell_trade() -> ExecutedTrade:
    candles = load_candles_csv(Path("data/samples/documented_bull_cycle_execution.csv"))

    result = run_backtest(
        candles,
        config=ScanConfig(extrema_window=1),
    )

    return result.execution.trades[0]


def build_buy_trade() -> ExecutedTrade:
    sell_trade = build_sell_trade()

    buy_signal = replace(
        sell_trade.signal,
        side=TradeSide.BUY,
    )

    return replace(
        sell_trade,
        signal=buy_signal,
        entry_price=100.0,
        stop_loss=95.0,
        take_profit=110.0,
        exit_price=110.0,
    )


def test_zero_costs_preserve_raw_trade_values() -> None:
    trade = build_sell_trade()

    adjusted = apply_trading_costs(trade)

    assert adjusted.effective_entry_price == pytest.approx(trade.entry_price)

    assert adjusted.effective_exit_price == pytest.approx(trade.exit_price)

    assert adjusted.gross_pnl_per_unit == pytest.approx(trade.price_pnl)

    assert adjusted.net_pnl_per_unit == pytest.approx(trade.price_pnl)

    assert adjusted.risk_per_unit == pytest.approx(trade.risk_per_unit)

    assert adjusted.total_cost_per_unit == pytest.approx(0.0)


def test_sell_trade_receives_adverse_fills() -> None:
    trade = build_sell_trade()

    policy = TradingCostPolicy(
        spread_fraction=0.0002,
        slippage_fraction=0.00005,
    )

    adjusted = apply_trading_costs(
        trade,
        policy=policy,
    )

    assert adjusted.effective_entry_price == pytest.approx(1.09083635)

    assert adjusted.effective_exit_price == pytest.approx(1.08356251)

    assert adjusted.effective_stop_price == pytest.approx(1.09496422)

    assert adjusted.gross_pnl_per_unit < trade.price_pnl


def test_buy_trade_receives_adverse_fills() -> None:
    trade = build_buy_trade()

    policy = TradingCostPolicy(
        spread_fraction=0.02,
        slippage_fraction=0.01,
    )

    adjusted = apply_trading_costs(
        trade,
        policy=policy,
    )

    assert adjusted.effective_entry_price == pytest.approx(102.0)

    assert adjusted.effective_exit_price == pytest.approx(107.8)

    assert adjusted.effective_stop_price == pytest.approx(93.1)

    assert adjusted.gross_pnl_per_unit == pytest.approx(5.8)

    assert adjusted.risk_per_unit == pytest.approx(8.9)


def test_commission_reduces_net_pnl() -> None:
    trade = build_sell_trade()

    policy = TradingCostPolicy(
        commission_fraction=0.001,
    )

    adjusted = apply_trading_costs(
        trade,
        policy=policy,
    )

    assert adjusted.total_commission_per_unit > 0

    assert adjusted.net_pnl_per_unit < (adjusted.gross_pnl_per_unit)

    assert adjusted.risk_per_unit > trade.risk_per_unit


@pytest.mark.parametrize(
    "kwargs",
    [
        {"spread_fraction": -0.1},
        {"slippage_fraction": -0.1},
        {"commission_fraction": -0.1},
        {"spread_fraction": 1.0},
        {"slippage_fraction": 1.0},
        {"commission_fraction": 1.0},
    ],
)
def test_invalid_cost_policy_is_rejected(
    kwargs: dict[str, float],
) -> None:
    with pytest.raises(ValueError):
        TradingCostPolicy(**kwargs)


def test_account_sizes_using_all_in_stop_risk() -> None:
    trade = build_sell_trade()

    cost_policy = TradingCostPolicy(
        spread_fraction=0.0002,
        slippage_fraction=0.00005,
        commission_fraction=0.0001,
    )

    result = simulate_account(
        [trade],
        policy=AccountPolicy(
            initial_balance=10_000.0,
            risk_fraction=0.01,
        ),
        cost_policy=cost_policy,
    )

    sized_trade = result.trades[0]

    assert sized_trade.risk_amount == pytest.approx(100.0)

    assert sized_trade.cost_adjustment.risk_per_unit == pytest.approx(0.004346450057)

    assert sized_trade.quantity == pytest.approx(23_007.28150297)

    assert sized_trade.monetary_pnl == pytest.approx(162.34858382)

    assert sized_trade.balance_after == pytest.approx(10_162.34858382)


def test_zero_cost_account_preserves_previous_result() -> None:
    trade = build_sell_trade()

    result = simulate_account(
        [trade],
        policy=AccountPolicy(
            initial_balance=10_000.0,
            risk_fraction=0.01,
        ),
    )

    assert result.metrics.ending_balance == pytest.approx(10_200.0)

    assert result.metrics.total_cost == pytest.approx(0.0)


def test_account_metrics_expose_trading_costs() -> None:
    trade = build_sell_trade()

    cost_policy = TradingCostPolicy(
        spread_fraction=0.0002,
        slippage_fraction=0.00005,
        commission_fraction=0.0001,
    )

    result = simulate_account(
        [trade],
        policy=AccountPolicy(),
        cost_policy=cost_policy,
    )

    metrics = result.metrics

    assert metrics.total_spread_slippage_cost == pytest.approx(7.504054935)

    assert metrics.total_commission == pytest.approx(5.002700667)

    assert metrics.total_cost == pytest.approx(12.506755602)

    assert metrics.net_profit == pytest.approx(162.34858382)


def test_runner_passes_cost_policy_to_account() -> None:
    candles = load_candles_csv(Path("data/samples/documented_bull_cycle_execution.csv"))

    result = run_backtest(
        candles,
        config=ScanConfig(extrema_window=1),
        account_policy=AccountPolicy(),
        cost_policy=TradingCostPolicy(
            spread_fraction=0.0002,
            slippage_fraction=0.00005,
            commission_fraction=0.0001,
        ),
    )

    assert result.account is not None

    assert result.account.metrics.ending_balance == pytest.approx(10_162.34858382)


def test_cost_policy_requires_account_simulation() -> None:
    candles = load_candles_csv(Path("data/samples/documented_bull_cycle_execution.csv"))

    with pytest.raises(
        ValueError,
        match="Trading costs require account simulation",
    ):
        run_backtest(
            candles,
            config=ScanConfig(extrema_window=1),
            cost_policy=TradingCostPolicy(
                spread_fraction=0.0002,
            ),
        )
