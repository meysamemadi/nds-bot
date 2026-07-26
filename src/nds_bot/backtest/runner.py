from collections.abc import Sequence
from dataclasses import dataclass

from nds_bot.backtest.account import (
    AccountPolicy,
    AccountResult,
    simulate_account,
)
from nds_bot.backtest.contracts import ContractSpecification
from nds_bot.backtest.costs import TradingCostPolicy
from nds_bot.backtest.execution import (
    ExecutionPolicy,
    ExecutionResult,
    execute_signals,
)
from nds_bot.backtest.margin import MarginPolicy
from nds_bot.backtest.performance import (
    BacktestMetrics,
    calculate_backtest_metrics,
)
from nds_bot.models import Candle
from nds_bot.pipeline import ScanConfig
from nds_bot.replay import (
    ReplayResult,
    replay_candles,
)
from nds_bot.signals import (
    SignalPolicy,
    TradeSignal,
    build_trade_signals,
)


@dataclass(frozen=True)
class BacktestResult:
    """Complete result of one NDS backtest."""

    replay: ReplayResult
    signals: tuple[TradeSignal, ...]
    execution: ExecutionResult
    metrics: BacktestMetrics
    account: AccountResult | None = None


def run_backtest(
    candles: Sequence[Candle],
    *,
    config: ScanConfig | None = None,
    signal_policy: SignalPolicy | None = None,
    execution_policy: ExecutionPolicy | None = None,
    account_policy: AccountPolicy | None = None,
    cost_policy: TradingCostPolicy | None = None,
    contract_specification: ContractSpecification | None = None,
    margin_policy: MarginPolicy | None = None,
) -> BacktestResult:
    """
    Run replay, signal generation, execution, and account simulation.

    Trading costs, contract constraints, and margin rules require
    account simulation because they depend on position quantity.
    """
    if cost_policy is not None and account_policy is None:
        raise ValueError("Trading costs require account simulation.")

    if contract_specification is not None and account_policy is None:
        raise ValueError("Contract specification requires account simulation.")

    if margin_policy is not None and account_policy is None:
        raise ValueError("Margin policy requires account simulation.")

    replay_result = replay_candles(
        candles,
        config=config,
    )

    signals = build_trade_signals(
        candles,
        replay_result,
        policy=signal_policy,
    )

    execution_result = execute_signals(
        candles,
        signals,
        policy=execution_policy,
    )

    metrics = calculate_backtest_metrics(execution_result.trades)

    account_result = (
        simulate_account(
            execution_result.trades,
            policy=account_policy,
            cost_policy=cost_policy,
            contract_specification=(contract_specification),
            margin_policy=margin_policy,
        )
        if account_policy is not None
        else None
    )

    return BacktestResult(
        replay=replay_result,
        signals=signals,
        execution=execution_result,
        metrics=metrics,
        account=account_result,
    )
