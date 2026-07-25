from collections.abc import Sequence
from dataclasses import dataclass
from statistics import fmean

from nds_bot.backtest.execution import ExecutedTrade

BREAKEVEN_TOLERANCE = 1e-12


@dataclass(frozen=True)
class BacktestMetrics:
    """
    Account-independent backtest statistics.

    R-based metrics assume that every trade risks one normalized
    unit of risk. They are not account-currency results.
    """

    trade_count: int
    winner_count: int
    loser_count: int
    breakeven_count: int

    win_rate: float

    total_r: float
    mean_r: float
    best_r: float
    worst_r: float
    maximum_drawdown_r: float

    total_price_pnl: float


def calculate_backtest_metrics(
    trades: Sequence[ExecutedTrade],
) -> BacktestMetrics:
    """Calculate normalized performance metrics."""
    r_multiples = tuple(trade.r_multiple for trade in trades)

    winner_count = sum(value > BREAKEVEN_TOLERANCE for value in r_multiples)

    loser_count = sum(value < -BREAKEVEN_TOLERANCE for value in r_multiples)

    breakeven_count = len(r_multiples) - winner_count - loser_count

    trade_count = len(trades)

    win_rate = winner_count / trade_count if trade_count else 0.0

    return BacktestMetrics(
        trade_count=trade_count,
        winner_count=winner_count,
        loser_count=loser_count,
        breakeven_count=breakeven_count,
        win_rate=win_rate,
        total_r=sum(r_multiples),
        mean_r=(fmean(r_multiples) if r_multiples else 0.0),
        best_r=(max(r_multiples) if r_multiples else 0.0),
        worst_r=(min(r_multiples) if r_multiples else 0.0),
        maximum_drawdown_r=calculate_maximum_drawdown_r(r_multiples),
        total_price_pnl=sum(trade.price_pnl for trade in trades),
    )


def calculate_maximum_drawdown_r(
    r_multiples: Sequence[float],
) -> float:
    """
    Calculate peak-to-trough drawdown on cumulative R.

    The equity curve starts at zero R.
    """
    cumulative_r = 0.0
    peak_r = 0.0
    maximum_drawdown = 0.0

    for value in r_multiples:
        cumulative_r += value
        peak_r = max(
            peak_r,
            cumulative_r,
        )

        current_drawdown = peak_r - cumulative_r

        maximum_drawdown = max(
            maximum_drawdown,
            current_drawdown,
        )

    return maximum_drawdown
