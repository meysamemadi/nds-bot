from collections.abc import Sequence
from dataclasses import dataclass

from nds_bot.backtest.execution import (
    ExecutionPolicy,
    ExecutionResult,
    execute_signals,
)
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


def run_backtest(
    candles: Sequence[Candle],
    *,
    config: ScanConfig | None = None,
    signal_policy: SignalPolicy | None = None,
    execution_policy: ExecutionPolicy | None = None,
) -> BacktestResult:
    """
    Run replay, signal generation, execution, and metrics.
    """
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

    return BacktestResult(
        replay=replay_result,
        signals=signals,
        execution=execution_result,
        metrics=metrics,
    )
