from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from statistics import fmean

from nds_bot.backtest.account import AccountPolicy
from nds_bot.backtest.contracts import ContractSpecification
from nds_bot.backtest.costs import TradingCostPolicy
from nds_bot.backtest.execution import ExecutionPolicy
from nds_bot.backtest.margin import MarginPolicy
from nds_bot.backtest.runner import BacktestResult, run_backtest
from nds_bot.models import Candle
from nds_bot.pipeline import ScanConfig
from nds_bot.signals import SignalPolicy


@dataclass(frozen=True)
class PortfolioDataset:
    """One symbol/timeframe dataset used by a portfolio backtest."""

    dataset_id: str
    symbol: str
    timeframe: str
    candles: tuple[Candle, ...]
    config: ScanConfig
    allocation_weight: float = 1.0
    source_path: Path | None = None

    def __post_init__(self) -> None:
        if not self.dataset_id.strip():
            raise ValueError("Portfolio dataset id cannot be empty.")

        if not self.symbol.strip():
            raise ValueError("Portfolio symbol cannot be empty.")

        if not self.timeframe.strip():
            raise ValueError("Portfolio timeframe cannot be empty.")

        if not self.candles:
            raise ValueError("Portfolio dataset candles cannot be empty.")

        if self.allocation_weight <= 0:
            raise ValueError("Portfolio allocation weight must be positive.")


@dataclass(frozen=True)
class PortfolioDatasetResult:
    """Backtest output for one independently funded sub-account."""

    dataset: PortfolioDataset
    normalized_weight: float
    allocated_balance: float
    backtest: BacktestResult

    def __post_init__(self) -> None:
        if not 0 < self.normalized_weight <= 1:
            raise ValueError("Normalized portfolio weight must be in (0, 1].")

        if self.allocated_balance <= 0:
            raise ValueError("Allocated portfolio balance must be positive.")

        if self.backtest.account is None:
            raise ValueError("Portfolio dataset backtest must include account simulation.")

    @property
    def ending_balance(self) -> float:
        account = self.backtest.account
        if account is None:
            raise ValueError("Account simulation result is missing.")
        return account.metrics.ending_balance

    @property
    def return_fraction(self) -> float:
        return self.ending_balance / self.allocated_balance - 1


@dataclass(frozen=True)
class PortfolioEquityPoint:
    """One closed-trade point on the combined portfolio equity curve."""

    event_number: int
    time: datetime | None
    balance: float
    peak_balance: float
    drawdown_amount: float
    drawdown_fraction: float

    def __post_init__(self) -> None:
        if self.event_number < 0:
            raise ValueError("Portfolio equity event number cannot be negative.")

        if self.balance <= 0:
            raise ValueError("Portfolio equity balance must be positive.")

        if self.peak_balance < self.balance:
            raise ValueError("Portfolio peak balance cannot be below balance.")

        if self.drawdown_amount < 0:
            raise ValueError("Portfolio drawdown amount cannot be negative.")

        if not 0 <= self.drawdown_fraction < 1:
            raise ValueError("Portfolio drawdown fraction must be between 0 and 1.")


@dataclass(frozen=True)
class PortfolioMetrics:
    """Aggregate metrics for independently allocated sub-accounts."""

    dataset_count: int
    profitable_dataset_count: int
    losing_dataset_count: int
    flat_dataset_count: int

    total_candle_count: int
    total_signal_count: int
    total_executed_trade_count: int
    total_accepted_trade_count: int
    total_skipped_overlap_count: int
    total_skipped_minimum_lot_count: int
    total_skipped_margin_count: int

    initial_balance: float
    ending_balance: float
    net_profit: float
    return_fraction: float
    mean_dataset_return_fraction: float

    total_cost: float
    total_commission: float
    total_spread_slippage_cost: float

    maximum_drawdown_amount: float
    maximum_drawdown_fraction: float


@dataclass(frozen=True)
class PortfolioResult:
    """Complete multi-symbol and multi-timeframe portfolio result."""

    datasets: tuple[PortfolioDatasetResult, ...]
    equity_curve: tuple[PortfolioEquityPoint, ...]
    metrics: PortfolioMetrics


def run_portfolio_backtest(
    datasets: Sequence[PortfolioDataset],
    *,
    account_policy: AccountPolicy,
    signal_policy: SignalPolicy | None = None,
    execution_policy: ExecutionPolicy | None = None,
    cost_policy: TradingCostPolicy | None = None,
    contract_specification: ContractSpecification | None = None,
    margin_policy: MarginPolicy | None = None,
) -> PortfolioResult:
    """
    Run independent sub-account backtests and combine their equity.

    The initial portfolio balance is divided by allocation weights.
    Each dataset then compounds independently. Overlap rules are applied
    inside each dataset, not across datasets. This allows simultaneous
    positions on different symbols while keeping capital allocations fixed.
    """
    dataset_tuple = tuple(datasets)
    _validate_datasets(dataset_tuple)

    total_weight = sum(dataset.allocation_weight for dataset in dataset_tuple)

    dataset_results: list[PortfolioDatasetResult] = []

    for dataset in dataset_tuple:
        normalized_weight = dataset.allocation_weight / total_weight
        allocated_balance = account_policy.initial_balance * normalized_weight

        dataset_account_policy = replace(
            account_policy,
            initial_balance=allocated_balance,
        )

        backtest = run_backtest(
            dataset.candles,
            config=dataset.config,
            signal_policy=signal_policy,
            execution_policy=execution_policy,
            account_policy=dataset_account_policy,
            cost_policy=cost_policy,
            contract_specification=contract_specification,
            margin_policy=margin_policy,
        )

        dataset_results.append(
            PortfolioDatasetResult(
                dataset=dataset,
                normalized_weight=normalized_weight,
                allocated_balance=allocated_balance,
                backtest=backtest,
            )
        )

    result_tuple = tuple(dataset_results)
    equity_curve = _build_combined_equity_curve(
        dataset_results=result_tuple,
        initial_balance=account_policy.initial_balance,
    )
    metrics = _build_portfolio_metrics(
        dataset_results=result_tuple,
        equity_curve=equity_curve,
        initial_balance=account_policy.initial_balance,
    )

    return PortfolioResult(
        datasets=result_tuple,
        equity_curve=equity_curve,
        metrics=metrics,
    )


def _validate_datasets(
    datasets: tuple[PortfolioDataset, ...],
) -> None:
    if not datasets:
        raise ValueError("Portfolio requires at least one dataset.")

    dataset_ids = [dataset.dataset_id for dataset in datasets]

    if len(dataset_ids) != len(set(dataset_ids)):
        raise ValueError("Portfolio dataset ids must be unique.")


def _build_combined_equity_curve(
    *,
    dataset_results: tuple[PortfolioDatasetResult, ...],
    initial_balance: float,
) -> tuple[PortfolioEquityPoint, ...]:
    deltas_by_time: dict[datetime, float] = defaultdict(float)

    for dataset_result in dataset_results:
        account = dataset_result.backtest.account
        if account is None:
            raise ValueError("Account simulation result is missing.")

        previous_balance = dataset_result.allocated_balance

        for point in account.equity_curve[1:]:
            if point.exit_time is None:
                raise ValueError("Non-initial equity points must have an exit time.")

            deltas_by_time[point.exit_time] += point.balance - previous_balance
            previous_balance = point.balance

    balance = initial_balance
    peak_balance = balance
    points: list[PortfolioEquityPoint] = [
        PortfolioEquityPoint(
            event_number=0,
            time=None,
            balance=balance,
            peak_balance=peak_balance,
            drawdown_amount=0.0,
            drawdown_fraction=0.0,
        )
    ]

    for event_number, time in enumerate(
        sorted(deltas_by_time),
        start=1,
    ):
        balance += deltas_by_time[time]

        if balance <= 0:
            raise ValueError("Combined portfolio balance became non-positive.")

        peak_balance = max(peak_balance, balance)
        drawdown_amount = peak_balance - balance
        drawdown_fraction = drawdown_amount / peak_balance

        points.append(
            PortfolioEquityPoint(
                event_number=event_number,
                time=time,
                balance=balance,
                peak_balance=peak_balance,
                drawdown_amount=drawdown_amount,
                drawdown_fraction=drawdown_fraction,
            )
        )

    return tuple(points)


def _build_portfolio_metrics(
    *,
    dataset_results: tuple[PortfolioDatasetResult, ...],
    equity_curve: tuple[PortfolioEquityPoint, ...],
    initial_balance: float,
) -> PortfolioMetrics:
    accounts = []

    for dataset_result in dataset_results:
        account = dataset_result.backtest.account
        if account is None:
            raise ValueError("Account simulation result is missing.")
        accounts.append(account)

    ending_balance = sum(account.metrics.ending_balance for account in accounts)

    dataset_returns = tuple(dataset_result.return_fraction for dataset_result in dataset_results)

    profitable_dataset_count = sum(value > 1e-12 for value in dataset_returns)
    losing_dataset_count = sum(value < -1e-12 for value in dataset_returns)
    flat_dataset_count = len(dataset_returns) - profitable_dataset_count - losing_dataset_count

    return PortfolioMetrics(
        dataset_count=len(dataset_results),
        profitable_dataset_count=profitable_dataset_count,
        losing_dataset_count=losing_dataset_count,
        flat_dataset_count=flat_dataset_count,
        total_candle_count=sum(len(result.dataset.candles) for result in dataset_results),
        total_signal_count=sum(len(result.backtest.signals) for result in dataset_results),
        total_executed_trade_count=sum(
            len(result.backtest.execution.trades) for result in dataset_results
        ),
        total_accepted_trade_count=sum(
            account.metrics.accepted_trade_count for account in accounts
        ),
        total_skipped_overlap_count=sum(
            account.metrics.skipped_overlap_count for account in accounts
        ),
        total_skipped_minimum_lot_count=sum(
            account.metrics.skipped_minimum_lot_count for account in accounts
        ),
        total_skipped_margin_count=sum(
            account.metrics.skipped_insufficient_margin_count for account in accounts
        ),
        initial_balance=initial_balance,
        ending_balance=ending_balance,
        net_profit=ending_balance - initial_balance,
        return_fraction=(ending_balance / initial_balance - 1),
        mean_dataset_return_fraction=(fmean(dataset_returns) if dataset_returns else 0.0),
        total_cost=sum(account.metrics.total_cost for account in accounts),
        total_commission=sum(account.metrics.total_commission for account in accounts),
        total_spread_slippage_cost=sum(
            account.metrics.total_spread_slippage_cost for account in accounts
        ),
        maximum_drawdown_amount=max(point.drawdown_amount for point in equity_curve),
        maximum_drawdown_fraction=max(point.drawdown_fraction for point in equity_curve),
    )
