import csv
from collections.abc import Sequence
from pathlib import Path

from nds_bot.backtest.execution import ExecutedTrade

TRADE_COLUMNS = (
    "side",
    "signal_index",
    "signal_time",
    "cycle_direction",
    "entry_index",
    "entry_time",
    "entry_price",
    "stop_loss",
    "take_profit",
    "exit_index",
    "exit_time",
    "exit_price",
    "exit_reason",
    "holding_candles",
    "price_pnl",
    "return_fraction",
    "r_multiple",
    "is_winner",
    "hook_1",
    "hook_2",
    "nsi",
)


class TradeCsvError(ValueError):
    """Raised when a trade CSV cannot be written."""


def write_trades_csv(
    trades: Sequence[ExecutedTrade],
    path: str | Path,
) -> Path:
    """
    Write executed trades to CSV.

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
                fieldnames=TRADE_COLUMNS,
            )

            writer.writeheader()

            for trade in trades:
                writer.writerow(_trade_to_row(trade))

    except OSError as error:
        raise TradeCsvError(f"Could not write trade CSV file: {output_path}") from error

    return output_path


def _trade_to_row(
    trade: ExecutedTrade,
) -> dict[str, object]:
    signal = trade.signal
    analysis = signal.analysis
    quality = analysis.quality

    return {
        "side": trade.side.value,
        "signal_index": signal.generated_at_index,
        "signal_time": signal.generated_at_time.isoformat(),
        "cycle_direction": (signal.cycle_direction.value),
        "entry_index": trade.entry_index,
        "entry_time": trade.entry_time.isoformat(),
        "entry_price": trade.entry_price,
        "stop_loss": trade.stop_loss,
        "take_profit": trade.take_profit,
        "exit_index": trade.exit_index,
        "exit_time": trade.exit_time.isoformat(),
        "exit_price": trade.exit_price,
        "exit_reason": trade.exit_reason.value,
        "holding_candles": trade.holding_candles,
        "price_pnl": trade.price_pnl,
        "return_fraction": trade.return_fraction,
        "r_multiple": trade.r_multiple,
        "is_winner": trade.is_winner,
        "hook_1": quality.hook_ratios.first,
        "hook_2": quality.hook_ratios.second,
        "nsi": quality.nsi.score,
    }
