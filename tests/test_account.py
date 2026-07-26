from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from nds_bot.backtest.account import (
    AccountPolicy,
    OverlapPolicy,
    simulate_account,
)
from nds_bot.backtest.execution import (
    ExecutedTrade,
    ExitReason,
)
from nds_bot.backtest.runner import run_backtest
from nds_bot.data.csv_loader import load_candles_csv
from nds_bot.pipeline import ScanConfig


def build_winning_trade() -> ExecutedTrade:
    candles = load_candles_csv(Path("data/samples/documented_bull_cycle_execution.csv"))

    result = run_backtest(
        candles,
        config=ScanConfig(extrema_window=1),
    )

    return result.execution.trades[0]


def move_trade(
    trade: ExecutedTrade,
    *,
    entry_index: int,
    exit_index: int,
    exit_price: float | None = None,
    exit_reason: ExitReason | None = None,
) -> ExecutedTrade:
    entry_offset = entry_index - trade.entry_index

    exit_offset = exit_index - trade.exit_index

    return replace(
        trade,
        entry_index=entry_index,
        entry_time=(trade.entry_time + timedelta(hours=entry_offset)),
        exit_index=exit_index,
        exit_time=(trade.exit_time + timedelta(hours=exit_offset)),
        exit_price=(trade.exit_price if exit_price is None else exit_price),
        exit_reason=(trade.exit_reason if exit_reason is None else exit_reason),
    )


def make_losing_trade(
    trade: ExecutedTrade,
    *,
    entry_index: int,
    exit_index: int,
) -> ExecutedTrade:
    return move_trade(
        trade,
        entry_index=entry_index,
        exit_index=exit_index,
        exit_price=trade.stop_loss,
        exit_reason=ExitReason.STOP_LOSS,
    )


def test_single_winner_uses_one_percent_risk() -> None:
    trade = build_winning_trade()

    result = simulate_account(
        [trade],
        policy=AccountPolicy(
            initial_balance=10_000.0,
            risk_fraction=0.01,
        ),
    )

    sized_trade = result.trades[0]

    assert sized_trade.balance_before == pytest.approx(10_000.0)

    assert sized_trade.risk_amount == pytest.approx(100.0)

    assert sized_trade.quantity == pytest.approx(100.0 / trade.risk_per_unit)

    assert sized_trade.monetary_pnl == pytest.approx(200.0)

    assert sized_trade.balance_after == pytest.approx(10_200.0)

    assert result.metrics.ending_balance == pytest.approx(10_200.0)

    assert result.metrics.net_profit == pytest.approx(200.0)

    assert result.metrics.return_fraction == pytest.approx(0.02)


def test_position_size_compounds_with_current_balance() -> None:
    first_trade = build_winning_trade()

    second_trade = move_trade(
        first_trade,
        entry_index=15,
        exit_index=16,
    )

    result = simulate_account(
        [first_trade, second_trade],
        policy=AccountPolicy(
            initial_balance=10_000.0,
            risk_fraction=0.01,
        ),
    )

    assert result.trades[0].risk_amount == pytest.approx(100.0)

    assert result.trades[1].balance_before == pytest.approx(10_200.0)

    assert result.trades[1].risk_amount == pytest.approx(102.0)

    assert result.trades[1].monetary_pnl == pytest.approx(204.0)

    assert result.metrics.ending_balance == pytest.approx(10_404.0)


def test_one_r_loss_reduces_balance_by_risk_amount() -> None:
    winning_trade = build_winning_trade()

    losing_trade = make_losing_trade(
        winning_trade,
        entry_index=13,
        exit_index=14,
    )

    result = simulate_account(
        [losing_trade],
        policy=AccountPolicy(
            initial_balance=10_000.0,
            risk_fraction=0.01,
        ),
    )

    sized_trade = result.trades[0]

    assert losing_trade.r_multiple == pytest.approx(-1.0)
    assert sized_trade.risk_amount == pytest.approx(100.0)
    assert sized_trade.monetary_pnl == pytest.approx(-100.0)
    assert sized_trade.balance_after == pytest.approx(9_900.0)


def test_overlapping_trade_is_skipped_by_default() -> None:
    first_trade = build_winning_trade()

    overlapping_trade = move_trade(
        first_trade,
        entry_index=14,
        exit_index=15,
    )

    result = simulate_account(
        [first_trade, overlapping_trade],
    )

    assert len(result.trades) == 1

    assert result.skipped_overlapping_trades == (overlapping_trade,)

    assert result.metrics.accepted_trade_count == 1
    assert result.metrics.skipped_overlap_count == 1


def test_overlap_policy_can_raise_error() -> None:
    first_trade = build_winning_trade()

    overlapping_trade = move_trade(
        first_trade,
        entry_index=14,
        exit_index=15,
    )

    policy = AccountPolicy(
        overlap_policy=OverlapPolicy.RAISE,
    )

    with pytest.raises(
        ValueError,
        match="Overlapping trade detected",
    ):
        simulate_account(
            [first_trade, overlapping_trade],
            policy=policy,
        )


def test_equity_curve_calculates_monetary_drawdown() -> None:
    first_trade = build_winning_trade()

    second_trade = make_losing_trade(
        first_trade,
        entry_index=15,
        exit_index=15,
    )

    third_trade = make_losing_trade(
        first_trade,
        entry_index=16,
        exit_index=16,
    )

    result = simulate_account(
        [
            first_trade,
            second_trade,
            third_trade,
        ],
        policy=AccountPolicy(
            initial_balance=10_000.0,
            risk_fraction=0.01,
        ),
    )

    assert len(result.equity_curve) == 4

    assert result.equity_curve[0].balance == pytest.approx(10_000.0)

    assert result.equity_curve[1].balance == pytest.approx(10_200.0)

    assert result.equity_curve[2].balance == pytest.approx(10_098.0)

    assert result.equity_curve[3].balance == pytest.approx(9_997.02)

    assert result.metrics.maximum_drawdown_amount == pytest.approx(202.98)

    assert result.metrics.maximum_drawdown_fraction == pytest.approx(0.0199)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"initial_balance": 0.0},
        {"initial_balance": -1.0},
        {"risk_fraction": 0.0},
        {"risk_fraction": 1.0},
    ],
)
def test_invalid_account_policy_is_rejected(
    kwargs: dict[str, float],
) -> None:
    with pytest.raises(ValueError):
        AccountPolicy(**kwargs)


def test_runner_can_include_account_simulation() -> None:
    candles = load_candles_csv(Path("data/samples/documented_bull_cycle_execution.csv"))

    result = run_backtest(
        candles,
        config=ScanConfig(extrema_window=1),
        account_policy=AccountPolicy(
            initial_balance=10_000.0,
            risk_fraction=0.01,
        ),
    )

    assert result.account is not None

    assert result.account.metrics.accepted_trade_count == 1

    assert result.account.metrics.ending_balance == pytest.approx(10_200.0)


def test_runner_does_not_simulate_account_by_default() -> None:
    candles = load_candles_csv(Path("data/samples/documented_bull_cycle_execution.csv"))

    result = run_backtest(
        candles,
        config=ScanConfig(extrema_window=1),
    )

    assert result.account is None
