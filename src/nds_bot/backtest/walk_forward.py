from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from statistics import fmean

from nds_bot.backtest.account import AccountPolicy
from nds_bot.backtest.contracts import ContractSpecification
from nds_bot.backtest.costs import TradingCostPolicy
from nds_bot.backtest.execution import ExecutedTrade, ExecutionPolicy
from nds_bot.backtest.margin import MarginPolicy
from nds_bot.backtest.performance import (
    BacktestMetrics,
    calculate_backtest_metrics,
)
from nds_bot.backtest.runner import BacktestResult, run_backtest
from nds_bot.backtest.validation import (
    BoundaryTradePolicy,
    ValidationSegment,
    build_validation_segment,
    partition_validation_trades,
    validate_validation_policy_dependencies,
)
from nds_bot.models import Candle
from nds_bot.pipeline import ScanConfig
from nds_bot.signals import SignalPolicy


@dataclass(frozen=True)
class WalkForwardValidationConfig:
    """Configuration for expanding-window walk-forward validation."""

    initial_train_candles: int
    test_candles: int
    step_candles: int | None = None
    boundary_trade_policy: BoundaryTradePolicy = BoundaryTradePolicy.EXCLUDE

    def __post_init__(self) -> None:
        if self.initial_train_candles <= 0:
            raise ValueError("Initial train candle count must be positive.")

        if self.test_candles <= 0:
            raise ValueError("Test candle count must be positive.")

        if self.step_candles is not None and self.step_candles <= 0:
            raise ValueError("Step candle count must be positive.")

        if self.effective_step_candles < self.test_candles:
            raise ValueError(
                "Step candle count cannot be smaller than "
                "the test candle count because overlapping "
                "test folds would duplicate aggregate results."
            )

    @property
    def effective_step_candles(self) -> int:
        return self.test_candles if self.step_candles is None else self.step_candles


@dataclass(frozen=True)
class WalkForwardFold:
    """One expanding train window followed by one test window."""

    fold_number: int
    split_index: int
    split_time: datetime
    full_backtest: BacktestResult
    train: ValidationSegment
    test: ValidationSegment
    boundary_trades: tuple[ExecutedTrade, ...]

    def __post_init__(self) -> None:
        if self.fold_number <= 0:
            raise ValueError("Walk-forward fold number must be positive.")

        if self.split_index != self.test.start_index:
            raise ValueError("Fold split index must equal the test start index.")

        if self.train.end_index + 1 != self.test.start_index:
            raise ValueError("Train and test segments must be contiguous.")

    @property
    def excluded_boundary_trade_count(self) -> int:
        return len(self.boundary_trades)


@dataclass(frozen=True)
class WalkForwardSummary:
    """Aggregate out-of-sample statistics across non-overlapping folds."""

    fold_count: int
    combined_test_trades: tuple[ExecutedTrade, ...]
    test_metrics: BacktestMetrics
    profitable_fold_count: int
    losing_fold_count: int
    flat_fold_count: int
    account_enabled: bool
    mean_test_return_fraction: float
    total_test_net_profit: float
    worst_test_drawdown_fraction: float
    evaluated_test_candle_count: int
    unevaluated_candle_count: int


@dataclass(frozen=True)
class WalkForwardValidationResult:
    """Complete expanding-window walk-forward validation result."""

    config: WalkForwardValidationConfig
    candle_count: int
    folds: tuple[WalkForwardFold, ...]
    summary: WalkForwardSummary

    @property
    def total_boundary_trade_count(self) -> int:
        return sum(len(fold.boundary_trades) for fold in self.folds)


def run_walk_forward_validation(
    candles: Sequence[Candle],
    *,
    validation_config: WalkForwardValidationConfig,
    config: ScanConfig | None = None,
    signal_policy: SignalPolicy | None = None,
    execution_policy: ExecutionPolicy | None = None,
    account_policy: AccountPolicy | None = None,
    cost_policy: TradingCostPolicy | None = None,
    contract_specification: ContractSpecification | None = None,
    margin_policy: MarginPolicy | None = None,
) -> WalkForwardValidationResult:
    """
    Run expanding-window walk-forward validation.

    Each fold replays candles from index zero through the end of that
    fold's test window. Therefore the test segment has historical context
    but never receives candles beyond its own test end. Account simulation
    restarts independently for every train and test segment.
    """
    validate_validation_policy_dependencies(
        account_policy=account_policy,
        cost_policy=cost_policy,
        contract_specification=contract_specification,
        margin_policy=margin_policy,
    )

    boundaries = build_walk_forward_boundaries(
        candle_count=len(candles),
        validation_config=validation_config,
    )

    folds: list[WalkForwardFold] = []

    for fold_number, (split_index, test_end_index) in enumerate(
        boundaries,
        start=1,
    ):
        prefix = candles[: test_end_index + 1]

        full_backtest = run_backtest(
            prefix,
            config=config,
            signal_policy=signal_policy,
            execution_policy=execution_policy,
        )

        train_trades, test_trades, boundary_trades = partition_validation_trades(
            full_backtest.execution.trades,
            split_index=split_index,
            boundary_trade_policy=(validation_config.boundary_trade_policy),
        )

        train_segment = build_validation_segment(
            name="TRAIN",
            start_index=0,
            end_index=split_index - 1,
            trades=train_trades,
            account_policy=account_policy,
            cost_policy=cost_policy,
            contract_specification=contract_specification,
            margin_policy=margin_policy,
        )

        test_segment = build_validation_segment(
            name="TEST",
            start_index=split_index,
            end_index=test_end_index,
            trades=test_trades,
            account_policy=account_policy,
            cost_policy=cost_policy,
            contract_specification=contract_specification,
            margin_policy=margin_policy,
        )

        folds.append(
            WalkForwardFold(
                fold_number=fold_number,
                split_index=split_index,
                split_time=candles[split_index].time,
                full_backtest=full_backtest,
                train=train_segment,
                test=test_segment,
                boundary_trades=boundary_trades,
            )
        )

    fold_tuple = tuple(folds)
    summary = _build_summary(
        folds=fold_tuple,
        candle_count=len(candles),
        initial_train_candles=(validation_config.initial_train_candles),
        account_enabled=account_policy is not None,
    )

    return WalkForwardValidationResult(
        config=validation_config,
        candle_count=len(candles),
        folds=fold_tuple,
        summary=summary,
    )


def build_walk_forward_boundaries(
    *,
    candle_count: int,
    validation_config: WalkForwardValidationConfig,
) -> tuple[tuple[int, int], ...]:
    """Build non-overlapping expanding-window fold boundaries."""
    minimum_required = validation_config.initial_train_candles + validation_config.test_candles

    if candle_count < minimum_required:
        raise ValueError(
            "Walk-forward validation requires at least "
            f"{minimum_required} candles for the first fold."
        )

    boundaries: list[tuple[int, int]] = []
    split_index = validation_config.initial_train_candles
    step = validation_config.effective_step_candles

    while split_index + validation_config.test_candles <= candle_count:
        test_end_index = split_index + validation_config.test_candles - 1
        boundaries.append((split_index, test_end_index))
        split_index += step

    return tuple(boundaries)


def _build_summary(
    *,
    folds: tuple[WalkForwardFold, ...],
    candle_count: int,
    initial_train_candles: int,
    account_enabled: bool,
) -> WalkForwardSummary:
    combined_test_trades = tuple(trade for fold in folds for trade in fold.test.trades)

    fold_scores = tuple(_fold_score(fold) for fold in folds)

    profitable_fold_count = sum(score > 0 for score in fold_scores)
    losing_fold_count = sum(score < 0 for score in fold_scores)
    flat_fold_count = len(fold_scores) - profitable_fold_count - losing_fold_count

    account_results = tuple(fold.test.account for fold in folds if fold.test.account is not None)

    mean_test_return_fraction = (
        fmean(account.metrics.return_fraction for account in account_results)
        if account_results
        else 0.0
    )

    total_test_net_profit = sum(account.metrics.net_profit for account in account_results)

    worst_test_drawdown_fraction = max(
        (account.metrics.maximum_drawdown_fraction for account in account_results),
        default=0.0,
    )

    evaluated_test_candle_count = sum(fold.test.candle_count for fold in folds)

    unevaluated_candle_count = candle_count - initial_train_candles - evaluated_test_candle_count

    return WalkForwardSummary(
        fold_count=len(folds),
        combined_test_trades=combined_test_trades,
        test_metrics=calculate_backtest_metrics(combined_test_trades),
        profitable_fold_count=profitable_fold_count,
        losing_fold_count=losing_fold_count,
        flat_fold_count=flat_fold_count,
        account_enabled=account_enabled,
        mean_test_return_fraction=(mean_test_return_fraction),
        total_test_net_profit=total_test_net_profit,
        worst_test_drawdown_fraction=(worst_test_drawdown_fraction),
        evaluated_test_candle_count=(evaluated_test_candle_count),
        unevaluated_candle_count=(unevaluated_candle_count),
    )


def _fold_score(fold: WalkForwardFold) -> float:
    if fold.test.account is not None:
        return fold.test.account.metrics.net_profit

    return fold.test.metrics.total_r
