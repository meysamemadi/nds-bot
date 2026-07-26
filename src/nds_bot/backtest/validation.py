from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from nds_bot.backtest.account import (
    AccountPolicy,
    AccountResult,
    simulate_account,
)
from nds_bot.backtest.contracts import ContractSpecification
from nds_bot.backtest.costs import TradingCostPolicy
from nds_bot.backtest.execution import (
    ExecutedTrade,
    ExecutionPolicy,
)
from nds_bot.backtest.margin import MarginPolicy
from nds_bot.backtest.performance import (
    BacktestMetrics,
    calculate_backtest_metrics,
)
from nds_bot.backtest.runner import BacktestResult, run_backtest
from nds_bot.models import Candle
from nds_bot.pipeline import ScanConfig
from nds_bot.signals import SignalPolicy


class BoundaryTradePolicy(str, Enum):
    """Define how a trade crossing a validation boundary is handled."""

    EXCLUDE = "EXCLUDE"
    ASSIGN_TO_TRAIN = "ASSIGN_TO_TRAIN"


@dataclass(frozen=True)
class HoldoutValidationConfig:
    """Configuration for one chronological train/test split."""

    train_fraction: float = 0.70
    boundary_trade_policy: BoundaryTradePolicy = BoundaryTradePolicy.EXCLUDE

    def __post_init__(self) -> None:
        if not 0 < self.train_fraction < 1:
            raise ValueError("Train fraction must be greater than 0 and less than 1.")


@dataclass(frozen=True)
class ValidationSegment:
    """Metrics and optional account result for one validation segment."""

    name: str
    start_index: int
    end_index: int
    candle_count: int
    trades: tuple[ExecutedTrade, ...]
    metrics: BacktestMetrics
    account: AccountResult | None

    def __post_init__(self) -> None:
        if self.name not in {"TRAIN", "TEST"}:
            raise ValueError("Validation segment name must be TRAIN or TEST.")

        if self.start_index < 0:
            raise ValueError("Validation segment start index cannot be negative.")

        if self.end_index < self.start_index:
            raise ValueError("Validation segment end index cannot precede start index.")

        if self.candle_count != self.end_index - self.start_index + 1:
            raise ValueError("Validation segment candle count does not match its indexes.")


@dataclass(frozen=True)
class HoldoutValidationResult:
    """Complete chronological holdout-validation result."""

    config: HoldoutValidationConfig
    split_index: int
    split_time: datetime
    full_backtest: BacktestResult
    train: ValidationSegment
    test: ValidationSegment
    boundary_trades: tuple[ExecutedTrade, ...]

    @property
    def included_trade_count(self) -> int:
        return len(self.train.trades) + len(self.test.trades)

    @property
    def excluded_boundary_trade_count(self) -> int:
        if self.config.boundary_trade_policy is BoundaryTradePolicy.EXCLUDE:
            return len(self.boundary_trades)

        return 0


def run_holdout_validation(
    candles: Sequence[Candle],
    *,
    validation_config: HoldoutValidationConfig | None = None,
    config: ScanConfig | None = None,
    signal_policy: SignalPolicy | None = None,
    execution_policy: ExecutionPolicy | None = None,
    account_policy: AccountPolicy | None = None,
    cost_policy: TradingCostPolicy | None = None,
    contract_specification: ContractSpecification | None = None,
    margin_policy: MarginPolicy | None = None,
) -> HoldoutValidationResult:
    """
    Evaluate one chronological train/test holdout split.

    Replay and execution run once on the complete chronological candle
    sequence. This preserves pre-split market context while retaining the
    no-look-ahead behavior of replay. Executed trades are then partitioned
    by their entry and exit indexes.

    Account simulation, when enabled, is restarted independently for the
    train and test segments using the same initial account policy.
    """
    active_validation_config = validation_config or HoldoutValidationConfig()

    validate_validation_policy_dependencies(
        account_policy=account_policy,
        cost_policy=cost_policy,
        contract_specification=contract_specification,
        margin_policy=margin_policy,
    )

    split_index = calculate_split_index(
        candle_count=len(candles),
        train_fraction=active_validation_config.train_fraction,
    )

    full_backtest = run_backtest(
        candles,
        config=config,
        signal_policy=signal_policy,
        execution_policy=execution_policy,
    )

    train_trades, test_trades, boundary_trades = partition_validation_trades(
        full_backtest.execution.trades,
        split_index=split_index,
        boundary_trade_policy=(active_validation_config.boundary_trade_policy),
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
        end_index=len(candles) - 1,
        trades=test_trades,
        account_policy=account_policy,
        cost_policy=cost_policy,
        contract_specification=contract_specification,
        margin_policy=margin_policy,
    )

    return HoldoutValidationResult(
        config=active_validation_config,
        split_index=split_index,
        split_time=candles[split_index].time,
        full_backtest=full_backtest,
        train=train_segment,
        test=test_segment,
        boundary_trades=boundary_trades,
    )


def calculate_split_index(
    *,
    candle_count: int,
    train_fraction: float,
) -> int:
    """Calculate a non-empty chronological holdout split index."""
    if candle_count < 2:
        raise ValueError("Holdout validation requires at least two candles.")

    split_index = int(candle_count * train_fraction)

    if split_index <= 0 or split_index >= candle_count:
        raise ValueError("Train fraction produces an empty train or test segment.")

    return split_index


def partition_validation_trades(
    trades: Sequence[ExecutedTrade],
    *,
    split_index: int,
    boundary_trade_policy: BoundaryTradePolicy,
) -> tuple[
    tuple[ExecutedTrade, ...],
    tuple[ExecutedTrade, ...],
    tuple[ExecutedTrade, ...],
]:
    """Partition trades into train, test, and boundary groups."""
    train_trades: list[ExecutedTrade] = []
    test_trades: list[ExecutedTrade] = []
    boundary_trades: list[ExecutedTrade] = []

    for trade in trades:
        if trade.exit_index < split_index:
            train_trades.append(trade)
            continue

        if trade.entry_index >= split_index:
            test_trades.append(trade)
            continue

        boundary_trades.append(trade)

        if boundary_trade_policy is BoundaryTradePolicy.ASSIGN_TO_TRAIN:
            train_trades.append(trade)

    return (
        tuple(train_trades),
        tuple(test_trades),
        tuple(boundary_trades),
    )


def build_validation_segment(
    *,
    name: str,
    start_index: int,
    end_index: int,
    trades: tuple[ExecutedTrade, ...],
    account_policy: AccountPolicy | None,
    cost_policy: TradingCostPolicy | None,
    contract_specification: ContractSpecification | None,
    margin_policy: MarginPolicy | None,
) -> ValidationSegment:
    """Build metrics and an independent account result for one segment."""
    account_result = (
        simulate_account(
            trades,
            policy=account_policy,
            cost_policy=cost_policy,
            contract_specification=contract_specification,
            margin_policy=margin_policy,
        )
        if account_policy is not None
        else None
    )

    return ValidationSegment(
        name=name,
        start_index=start_index,
        end_index=end_index,
        candle_count=end_index - start_index + 1,
        trades=trades,
        metrics=calculate_backtest_metrics(trades),
        account=account_result,
    )


def validate_validation_policy_dependencies(
    *,
    account_policy: AccountPolicy | None,
    cost_policy: TradingCostPolicy | None,
    contract_specification: ContractSpecification | None,
    margin_policy: MarginPolicy | None,
) -> None:
    """Validate dependencies shared by holdout and walk-forward runs."""
    if cost_policy is not None and account_policy is None:
        raise ValueError("Trading costs require account simulation.")

    if contract_specification is not None and account_policy is None:
        raise ValueError("Contract specification requires account simulation.")

    if margin_policy is not None and account_policy is None:
        raise ValueError("Margin policy requires account simulation.")
