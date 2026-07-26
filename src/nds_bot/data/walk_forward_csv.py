import csv
from pathlib import Path

from nds_bot.backtest.walk_forward import (
    WalkForwardFold,
    WalkForwardValidationResult,
)

WALK_FORWARD_COLUMNS = (
    "row_type",
    "fold_number",
    "initial_train_candles",
    "test_candles",
    "step_candles",
    "boundary_trade_policy",
    "split_index",
    "split_time",
    "train_start_index",
    "train_end_index",
    "train_candle_count",
    "train_trade_count",
    "train_total_r",
    "test_start_index",
    "test_end_index",
    "test_candle_count",
    "test_trade_count",
    "test_winner_count",
    "test_loser_count",
    "test_breakeven_count",
    "test_win_rate",
    "test_total_r",
    "test_mean_r",
    "test_best_r",
    "test_worst_r",
    "test_maximum_drawdown_r",
    "boundary_trade_count",
    "account_enabled",
    "test_ending_balance",
    "test_net_profit",
    "test_return_fraction",
    "test_maximum_drawdown_fraction",
    "summary_fold_count",
    "summary_test_trade_count",
    "summary_test_win_rate",
    "summary_test_total_r",
    "summary_test_mean_r",
    "summary_test_maximum_drawdown_r",
    "profitable_fold_count",
    "losing_fold_count",
    "flat_fold_count",
    "mean_test_return_fraction",
    "total_test_net_profit",
    "worst_test_drawdown_fraction",
    "evaluated_test_candle_count",
    "unevaluated_candle_count",
)


class WalkForwardCsvError(ValueError):
    """Raised when a walk-forward CSV file cannot be written."""


def write_walk_forward_csv(
    result: WalkForwardValidationResult,
    path: str | Path,
) -> Path:
    """Write fold rows followed by one aggregate summary row."""
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
                fieldnames=WALK_FORWARD_COLUMNS,
            )
            writer.writeheader()

            for fold in result.folds:
                writer.writerow(_fold_to_row(result, fold))

            writer.writerow(_summary_to_row(result))

    except OSError as error:
        raise WalkForwardCsvError(
            f"Could not write walk-forward CSV file: {output_path}"
        ) from error

    return output_path


def _fold_to_row(
    result: WalkForwardValidationResult,
    fold: WalkForwardFold,
) -> dict[str, object]:
    metrics = fold.test.metrics
    account = fold.test.account

    if account is None:
        account_values: dict[str, object] = {
            "account_enabled": False,
            "test_ending_balance": "",
            "test_net_profit": "",
            "test_return_fraction": "",
            "test_maximum_drawdown_fraction": "",
        }
    else:
        account_values = {
            "account_enabled": True,
            "test_ending_balance": (account.metrics.ending_balance),
            "test_net_profit": account.metrics.net_profit,
            "test_return_fraction": (account.metrics.return_fraction),
            "test_maximum_drawdown_fraction": (account.metrics.maximum_drawdown_fraction),
        }

    return {
        "row_type": "FOLD",
        "fold_number": fold.fold_number,
        "initial_train_candles": (result.config.initial_train_candles),
        "test_candles": result.config.test_candles,
        "step_candles": (result.config.effective_step_candles),
        "boundary_trade_policy": (result.config.boundary_trade_policy.value),
        "split_index": fold.split_index,
        "split_time": fold.split_time.isoformat(),
        "train_start_index": fold.train.start_index,
        "train_end_index": fold.train.end_index,
        "train_candle_count": fold.train.candle_count,
        "train_trade_count": fold.train.metrics.trade_count,
        "train_total_r": fold.train.metrics.total_r,
        "test_start_index": fold.test.start_index,
        "test_end_index": fold.test.end_index,
        "test_candle_count": fold.test.candle_count,
        "test_trade_count": metrics.trade_count,
        "test_winner_count": metrics.winner_count,
        "test_loser_count": metrics.loser_count,
        "test_breakeven_count": metrics.breakeven_count,
        "test_win_rate": metrics.win_rate,
        "test_total_r": metrics.total_r,
        "test_mean_r": metrics.mean_r,
        "test_best_r": metrics.best_r,
        "test_worst_r": metrics.worst_r,
        "test_maximum_drawdown_r": (metrics.maximum_drawdown_r),
        "boundary_trade_count": len(fold.boundary_trades),
        **account_values,
        **_blank_summary_values(),
    }


def _summary_to_row(
    result: WalkForwardValidationResult,
) -> dict[str, object]:
    summary = result.summary
    metrics = summary.test_metrics

    row = {column: "" for column in WALK_FORWARD_COLUMNS}

    row.update(
        {
            "row_type": "SUMMARY",
            "initial_train_candles": (result.config.initial_train_candles),
            "test_candles": result.config.test_candles,
            "step_candles": (result.config.effective_step_candles),
            "boundary_trade_policy": (result.config.boundary_trade_policy.value),
            "account_enabled": summary.account_enabled,
            "summary_fold_count": summary.fold_count,
            "summary_test_trade_count": metrics.trade_count,
            "summary_test_win_rate": metrics.win_rate,
            "summary_test_total_r": metrics.total_r,
            "summary_test_mean_r": metrics.mean_r,
            "summary_test_maximum_drawdown_r": (metrics.maximum_drawdown_r),
            "profitable_fold_count": (summary.profitable_fold_count),
            "losing_fold_count": summary.losing_fold_count,
            "flat_fold_count": summary.flat_fold_count,
            "mean_test_return_fraction": (summary.mean_test_return_fraction),
            "total_test_net_profit": (summary.total_test_net_profit),
            "worst_test_drawdown_fraction": (summary.worst_test_drawdown_fraction),
            "evaluated_test_candle_count": (summary.evaluated_test_candle_count),
            "unevaluated_candle_count": (summary.unevaluated_candle_count),
        }
    )

    return row


def _blank_summary_values() -> dict[str, object]:
    return {
        "summary_fold_count": "",
        "summary_test_trade_count": "",
        "summary_test_win_rate": "",
        "summary_test_total_r": "",
        "summary_test_mean_r": "",
        "summary_test_maximum_drawdown_r": "",
        "profitable_fold_count": "",
        "losing_fold_count": "",
        "flat_fold_count": "",
        "mean_test_return_fraction": "",
        "total_test_net_profit": "",
        "worst_test_drawdown_fraction": "",
        "evaluated_test_candle_count": "",
        "unevaluated_candle_count": "",
    }
