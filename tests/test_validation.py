from pathlib import Path

import pytest

from nds_bot.backtest.account import AccountPolicy
from nds_bot.backtest.costs import TradingCostPolicy
from nds_bot.backtest.validation import (
    BoundaryTradePolicy,
    HoldoutValidationConfig,
    run_holdout_validation,
)
from nds_bot.data.csv_loader import load_candles_csv
from nds_bot.models import Candle
from nds_bot.pipeline import ScanConfig

SAMPLE_PATH = Path("data/samples/documented_bull_cycle_execution.csv")


def load_sample() -> list[Candle]:
    return load_candles_csv(SAMPLE_PATH)


def test_default_validation_config() -> None:
    config = HoldoutValidationConfig()

    assert config.train_fraction == pytest.approx(0.70)
    assert config.boundary_trade_policy is BoundaryTradePolicy.EXCLUDE


@pytest.mark.parametrize(
    "train_fraction",
    [0.0, -0.1, 1.0, 1.1],
)
def test_invalid_train_fraction_is_rejected(
    train_fraction: float,
) -> None:
    with pytest.raises(ValueError):
        HoldoutValidationConfig(train_fraction=train_fraction)


def test_trade_after_split_is_assigned_to_test() -> None:
    candles = load_sample()

    result = run_holdout_validation(
        candles,
        validation_config=HoldoutValidationConfig(
            train_fraction=0.80,
        ),
        config=ScanConfig(extrema_window=1),
    )

    assert result.split_index == 12
    assert result.train.metrics.trade_count == 0
    assert result.test.metrics.trade_count == 1
    assert result.boundary_trades == ()
    assert result.test.metrics.total_r == pytest.approx(2.0)


def test_boundary_trade_is_excluded_by_default() -> None:
    candles = load_sample()

    result = run_holdout_validation(
        candles,
        validation_config=HoldoutValidationConfig(
            train_fraction=14 / 15,
        ),
        config=ScanConfig(extrema_window=1),
    )

    assert result.split_index == 14
    assert result.train.metrics.trade_count == 0
    assert result.test.metrics.trade_count == 0
    assert len(result.boundary_trades) == 1
    assert result.excluded_boundary_trade_count == 1


def test_boundary_trade_can_be_assigned_to_train() -> None:
    candles = load_sample()

    result = run_holdout_validation(
        candles,
        validation_config=HoldoutValidationConfig(
            train_fraction=14 / 15,
            boundary_trade_policy=(BoundaryTradePolicy.ASSIGN_TO_TRAIN),
        ),
        config=ScanConfig(extrema_window=1),
    )

    assert result.train.metrics.trade_count == 1
    assert result.test.metrics.trade_count == 0
    assert len(result.boundary_trades) == 1
    assert result.excluded_boundary_trade_count == 0


def test_account_simulation_restarts_for_each_segment() -> None:
    candles = load_sample()

    result = run_holdout_validation(
        candles,
        validation_config=HoldoutValidationConfig(
            train_fraction=0.80,
        ),
        config=ScanConfig(extrema_window=1),
        account_policy=AccountPolicy(
            initial_balance=10_000.0,
            risk_fraction=0.01,
        ),
    )

    assert result.train.account is not None
    assert result.test.account is not None

    assert result.train.account.metrics.ending_balance == pytest.approx(10_000.0)

    assert result.test.account.metrics.ending_balance == pytest.approx(10_200.0)


def test_costs_require_account_simulation() -> None:
    with pytest.raises(
        ValueError,
        match="Trading costs require account simulation",
    ):
        run_holdout_validation(
            load_sample(),
            config=ScanConfig(extrema_window=1),
            cost_policy=TradingCostPolicy(
                spread_fraction=0.0002,
            ),
        )


def test_validation_requires_at_least_two_candles() -> None:
    candles = load_sample()[:1]

    with pytest.raises(
        ValueError,
        match="at least two candles",
    ):
        run_holdout_validation(candles)
