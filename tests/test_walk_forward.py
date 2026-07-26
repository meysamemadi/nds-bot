from pathlib import Path

import pytest

from nds_bot.backtest.account import AccountPolicy
from nds_bot.backtest.costs import TradingCostPolicy
from nds_bot.backtest.walk_forward import (
    WalkForwardValidationConfig,
    build_walk_forward_boundaries,
    run_walk_forward_validation,
)
from nds_bot.data.csv_loader import load_candles_csv
from nds_bot.models import Candle
from nds_bot.pipeline import ScanConfig

SAMPLE_PATH = Path("data/samples/documented_bull_cycle_execution.csv")


def load_sample() -> list[Candle]:
    return load_candles_csv(SAMPLE_PATH)


def test_default_step_matches_test_window() -> None:
    config = WalkForwardValidationConfig(
        initial_train_candles=9,
        test_candles=3,
    )

    assert config.effective_step_candles == 3


@pytest.mark.parametrize(
    "kwargs",
    [
        {
            "initial_train_candles": 0,
            "test_candles": 3,
        },
        {
            "initial_train_candles": -1,
            "test_candles": 3,
        },
        {
            "initial_train_candles": 9,
            "test_candles": 0,
        },
        {
            "initial_train_candles": 9,
            "test_candles": -1,
        },
        {
            "initial_train_candles": 9,
            "test_candles": 3,
            "step_candles": 0,
        },
        {
            "initial_train_candles": 9,
            "test_candles": 3,
            "step_candles": 2,
        },
    ],
)
def test_invalid_walk_forward_config_is_rejected(
    kwargs: dict[str, int],
) -> None:
    with pytest.raises(ValueError):
        WalkForwardValidationConfig(**kwargs)


def test_builds_two_expanding_folds() -> None:
    result = run_walk_forward_validation(
        load_sample(),
        validation_config=WalkForwardValidationConfig(
            initial_train_candles=9,
            test_candles=3,
        ),
        config=ScanConfig(extrema_window=1),
    )

    assert len(result.folds) == 2

    first, second = result.folds

    assert first.train.start_index == 0
    assert first.train.end_index == 8
    assert first.test.start_index == 9
    assert first.test.end_index == 11
    assert first.test.metrics.trade_count == 0

    assert second.train.start_index == 0
    assert second.train.end_index == 11
    assert second.test.start_index == 12
    assert second.test.end_index == 14
    assert second.test.metrics.trade_count == 1
    assert second.test.metrics.total_r == pytest.approx(2.0)

    assert result.summary.fold_count == 2
    assert result.summary.test_metrics.trade_count == 1
    assert result.summary.test_metrics.total_r == pytest.approx(2.0)
    assert result.summary.profitable_fold_count == 1
    assert result.summary.flat_fold_count == 1
    assert result.summary.unevaluated_candle_count == 0


def test_account_simulation_restarts_for_each_test_fold() -> None:
    result = run_walk_forward_validation(
        load_sample(),
        validation_config=WalkForwardValidationConfig(
            initial_train_candles=9,
            test_candles=3,
        ),
        config=ScanConfig(extrema_window=1),
        account_policy=AccountPolicy(
            initial_balance=10_000.0,
            risk_fraction=0.01,
        ),
    )

    first, second = result.folds

    assert first.test.account is not None
    assert second.test.account is not None

    assert first.test.account.metrics.ending_balance == pytest.approx(10_000.0)
    assert second.test.account.metrics.ending_balance == pytest.approx(10_200.0)

    assert result.summary.account_enabled is True
    assert result.summary.mean_test_return_fraction == pytest.approx(0.01)
    assert result.summary.total_test_net_profit == pytest.approx(200.0)


def test_walk_forward_requires_a_complete_first_fold() -> None:
    config = WalkForwardValidationConfig(
        initial_train_candles=9,
        test_candles=3,
    )

    with pytest.raises(
        ValueError,
        match="at least 12 candles",
    ):
        build_walk_forward_boundaries(
            candle_count=11,
            validation_config=config,
        )


def test_costs_require_account_simulation() -> None:
    with pytest.raises(
        ValueError,
        match="Trading costs require account simulation",
    ):
        run_walk_forward_validation(
            load_sample(),
            validation_config=WalkForwardValidationConfig(
                initial_train_candles=9,
                test_candles=3,
            ),
            config=ScanConfig(extrema_window=1),
            cost_policy=TradingCostPolicy(
                spread_fraction=0.0002,
            ),
        )
