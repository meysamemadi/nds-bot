import csv
from pathlib import Path

from nds_bot.backtest.portfolio import PortfolioResult

PORTFOLIO_SUMMARY_COLUMNS = (
    "record_type",
    "dataset_id",
    "symbol",
    "timeframe",
    "allocation_weight",
    "normalized_weight",
    "allocated_balance",
    "candle_count",
    "signal_count",
    "executed_trade_count",
    "accepted_trade_count",
    "skipped_overlap_count",
    "skipped_minimum_lot_count",
    "skipped_margin_count",
    "ending_balance",
    "net_profit",
    "return_fraction",
    "total_cost",
    "maximum_drawdown_fraction",
)

PORTFOLIO_EQUITY_COLUMNS = (
    "event_number",
    "time",
    "balance",
    "peak_balance",
    "drawdown_amount",
    "drawdown_fraction",
)


class PortfolioCsvError(ValueError):
    """Raised when a portfolio CSV file cannot be written."""


def write_portfolio_summary_csv(
    result: PortfolioResult,
    path: str | Path,
) -> Path:
    """Write dataset rows followed by one aggregate summary row."""
    rows: list[dict[str, object]] = []

    for dataset_result in result.datasets:
        account = dataset_result.backtest.account

        if account is None:
            raise PortfolioCsvError("Portfolio dataset account result is missing.")

        metrics = account.metrics
        dataset = dataset_result.dataset

        rows.append(
            {
                "record_type": "DATASET",
                "dataset_id": dataset.dataset_id,
                "symbol": dataset.symbol,
                "timeframe": dataset.timeframe,
                "allocation_weight": dataset.allocation_weight,
                "normalized_weight": (dataset_result.normalized_weight),
                "allocated_balance": (dataset_result.allocated_balance),
                "candle_count": len(dataset.candles),
                "signal_count": len(dataset_result.backtest.signals),
                "executed_trade_count": len(dataset_result.backtest.execution.trades),
                "accepted_trade_count": metrics.accepted_trade_count,
                "skipped_overlap_count": metrics.skipped_overlap_count,
                "skipped_minimum_lot_count": (metrics.skipped_minimum_lot_count),
                "skipped_margin_count": (metrics.skipped_insufficient_margin_count),
                "ending_balance": metrics.ending_balance,
                "net_profit": metrics.net_profit,
                "return_fraction": metrics.return_fraction,
                "total_cost": metrics.total_cost,
                "maximum_drawdown_fraction": (metrics.maximum_drawdown_fraction),
            }
        )

    metrics = result.metrics
    rows.append(
        {
            "record_type": "SUMMARY",
            "dataset_id": "",
            "symbol": "",
            "timeframe": "",
            "allocation_weight": "",
            "normalized_weight": 1.0,
            "allocated_balance": metrics.initial_balance,
            "candle_count": metrics.total_candle_count,
            "signal_count": metrics.total_signal_count,
            "executed_trade_count": (metrics.total_executed_trade_count),
            "accepted_trade_count": (metrics.total_accepted_trade_count),
            "skipped_overlap_count": (metrics.total_skipped_overlap_count),
            "skipped_minimum_lot_count": (metrics.total_skipped_minimum_lot_count),
            "skipped_margin_count": (metrics.total_skipped_margin_count),
            "ending_balance": metrics.ending_balance,
            "net_profit": metrics.net_profit,
            "return_fraction": metrics.return_fraction,
            "total_cost": metrics.total_cost,
            "maximum_drawdown_fraction": (metrics.maximum_drawdown_fraction),
        }
    )

    return _write_rows(
        path=path,
        fieldnames=PORTFOLIO_SUMMARY_COLUMNS,
        rows=rows,
    )


def write_portfolio_equity_csv(
    result: PortfolioResult,
    path: str | Path,
) -> Path:
    """Write the combined closed-trade portfolio equity curve."""
    rows = [
        {
            "event_number": point.event_number,
            "time": ("" if point.time is None else point.time.isoformat()),
            "balance": point.balance,
            "peak_balance": point.peak_balance,
            "drawdown_amount": point.drawdown_amount,
            "drawdown_fraction": point.drawdown_fraction,
        }
        for point in result.equity_curve
    ]

    return _write_rows(
        path=path,
        fieldnames=PORTFOLIO_EQUITY_COLUMNS,
        rows=rows,
    )


def _write_rows(
    *,
    path: str | Path,
    fieldnames: tuple[str, ...],
    rows: list[dict[str, object]],
) -> Path:
    output_path = Path(path)

    try:
        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with output_path.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=fieldnames,
            )
            writer.writeheader()
            writer.writerows(rows)

    except OSError as error:
        raise PortfolioCsvError(f"Could not write portfolio CSV file: {output_path}") from error

    return output_path
