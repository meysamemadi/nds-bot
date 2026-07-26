import csv
from collections.abc import Sequence
from pathlib import Path

from nds_bot.backtest.account import EquityPoint

EQUITY_COLUMNS = (
    "trade_number",
    "exit_index",
    "exit_time",
    "balance",
    "peak_balance",
    "drawdown_amount",
    "drawdown_fraction",
)


class EquityCsvError(ValueError):
    """Raised when an equity CSV file cannot be written."""


def write_equity_csv(
    equity_curve: Sequence[EquityPoint],
    path: str | Path,
) -> Path:
    """
    Write a closed-trade equity curve to CSV.

    Empty input still creates a CSV containing its header.
    """
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
                fieldnames=EQUITY_COLUMNS,
            )

            writer.writeheader()

            for point in equity_curve:
                writer.writerow(_equity_point_to_row(point))

    except OSError as error:
        raise EquityCsvError(f"Could not write equity CSV file: {output_path}") from error

    return output_path


def _equity_point_to_row(
    point: EquityPoint,
) -> dict[str, object]:
    return {
        "trade_number": point.trade_number,
        "exit_index": ("" if point.exit_index is None else point.exit_index),
        "exit_time": ("" if point.exit_time is None else point.exit_time.isoformat()),
        "balance": point.balance,
        "peak_balance": point.peak_balance,
        "drawdown_amount": point.drawdown_amount,
        "drawdown_fraction": point.drawdown_fraction,
    }
