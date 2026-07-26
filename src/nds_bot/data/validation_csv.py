import csv
from pathlib import Path

from nds_bot.backtest.validation import (
    HoldoutValidationResult,
    ValidationSegment,
)

VALIDATION_COLUMNS = (
    "split_index",
    "split_time",
    "train_fraction",
    "boundary_trade_policy",
    "boundary_trade_count",
    "excluded_boundary_trade_count",
    "segment",
    "start_index",
    "end_index",
    "candle_count",
    "trade_count",
    "winner_count",
    "loser_count",
    "breakeven_count",
    "win_rate",
    "total_r",
    "mean_r",
    "best_r",
    "worst_r",
    "maximum_drawdown_r",
    "total_price_pnl",
    "account_enabled",
    "accepted_trade_count",
    "ending_balance",
    "net_profit",
    "account_return_fraction",
    "maximum_drawdown_amount",
    "maximum_drawdown_fraction",
    "total_trading_cost",
    "skipped_overlap_count",
    "skipped_minimum_lot_count",
    "skipped_insufficient_margin_count",
)


class ValidationCsvError(ValueError):
    """Raised when a validation CSV file cannot be written."""


def write_validation_csv(
    result: HoldoutValidationResult,
    path: str | Path,
) -> Path:
    """Write train and test validation summaries to CSV."""
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
                fieldnames=VALIDATION_COLUMNS,
            )
            writer.writeheader()
            writer.writerow(_segment_to_row(result, result.train))
            writer.writerow(_segment_to_row(result, result.test))

    except OSError as error:
        raise ValidationCsvError(f"Could not write validation CSV file: {output_path}") from error

    return output_path


def _segment_to_row(
    result: HoldoutValidationResult,
    segment: ValidationSegment,
) -> dict[str, object]:
    metrics = segment.metrics
    account = segment.account

    account_values: dict[str, object]

    if account is None:
        account_values = {
            "account_enabled": False,
            "accepted_trade_count": "",
            "ending_balance": "",
            "net_profit": "",
            "account_return_fraction": "",
            "maximum_drawdown_amount": "",
            "maximum_drawdown_fraction": "",
            "total_trading_cost": "",
            "skipped_overlap_count": "",
            "skipped_minimum_lot_count": "",
            "skipped_insufficient_margin_count": "",
        }
    else:
        account_metrics = account.metrics
        account_values = {
            "account_enabled": True,
            "accepted_trade_count": (account_metrics.accepted_trade_count),
            "ending_balance": account_metrics.ending_balance,
            "net_profit": account_metrics.net_profit,
            "account_return_fraction": (account_metrics.return_fraction),
            "maximum_drawdown_amount": (account_metrics.maximum_drawdown_amount),
            "maximum_drawdown_fraction": (account_metrics.maximum_drawdown_fraction),
            "total_trading_cost": account_metrics.total_cost,
            "skipped_overlap_count": (account_metrics.skipped_overlap_count),
            "skipped_minimum_lot_count": (account_metrics.skipped_minimum_lot_count),
            "skipped_insufficient_margin_count": (
                account_metrics.skipped_insufficient_margin_count
            ),
        }

    return {
        "split_index": result.split_index,
        "split_time": result.split_time.isoformat(),
        "train_fraction": result.config.train_fraction,
        "boundary_trade_policy": (result.config.boundary_trade_policy.value),
        "boundary_trade_count": len(result.boundary_trades),
        "excluded_boundary_trade_count": (result.excluded_boundary_trade_count),
        "segment": segment.name,
        "start_index": segment.start_index,
        "end_index": segment.end_index,
        "candle_count": segment.candle_count,
        "trade_count": metrics.trade_count,
        "winner_count": metrics.winner_count,
        "loser_count": metrics.loser_count,
        "breakeven_count": metrics.breakeven_count,
        "win_rate": metrics.win_rate,
        "total_r": metrics.total_r,
        "mean_r": metrics.mean_r,
        "best_r": metrics.best_r,
        "worst_r": metrics.worst_r,
        "maximum_drawdown_r": metrics.maximum_drawdown_r,
        "total_price_pnl": metrics.total_price_pnl,
        **account_values,
    }
