import csv
from collections.abc import Iterable, Sequence
from pathlib import Path

from nds_bot.backtest.account import SizedTrade
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
    "exit_fill_type",
    "is_gap_exit",
    "theoretical_exit_price",
    "gap_distance",
    "holding_candles",
    "price_pnl",
    "return_fraction",
    "r_multiple",
    "is_winner",
    "hook_1",
    "hook_2",
    "nsi",
)


SIZED_TRADE_COLUMNS = (
    *TRADE_COLUMNS,
    "effective_entry_price",
    "effective_exit_price",
    "effective_stop_price",
    "balance_before",
    "risk_amount",
    "actual_risk_amount",
    "risk_utilization_fraction",
    "raw_quantity",
    "raw_lots",
    "lots",
    "quantity",
    "contract_size",
    "minimum_lot",
    "maximum_lot",
    "lot_step",
    "capped_at_maximum_lot",
    "margin_enabled",
    "leverage",
    "notional_value",
    "margin_required",
    "free_margin_after_entry",
    "margin_utilization_fraction",
    "margin_level_fraction",
    "gross_pnl_per_unit",
    "net_pnl_per_unit",
    "spread_slippage_cost_per_unit",
    "total_commission_per_unit",
    "total_cost_per_unit",
    "gross_monetary_pnl",
    "spread_slippage_cost",
    "commission_amount",
    "total_cost_amount",
    "net_monetary_pnl",
    "balance_after",
    "net_r_multiple",
    "net_is_winner",
)


class TradeCsvError(ValueError):
    """Raised when a trade CSV cannot be written."""


def write_trades_csv(
    trades: Sequence[ExecutedTrade],
    path: str | Path,
) -> Path:
    """
    Write raw executed trades to CSV.

    Empty input still creates a CSV containing its header.
    """
    return _write_rows(
        path=path,
        fieldnames=TRADE_COLUMNS,
        rows=(_trade_to_row(trade) for trade in trades),
    )


def write_sized_trades_csv(
    trades: Sequence[SizedTrade],
    path: str | Path,
) -> Path:
    """
    Write account-sized and cost-adjusted trades to CSV.

    Raw execution columns are preserved for backward compatibility,
    while cost-adjusted and monetary fields are appended.
    """
    return _write_rows(
        path=path,
        fieldnames=SIZED_TRADE_COLUMNS,
        rows=(_sized_trade_to_row(trade) for trade in trades),
    )


def _write_rows(
    *,
    path: str | Path,
    fieldnames: Sequence[str],
    rows: Iterable[dict[str, object]],
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

            for row in rows:
                writer.writerow(row)

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
        "cycle_direction": signal.cycle_direction.value,
        "entry_index": trade.entry_index,
        "entry_time": trade.entry_time.isoformat(),
        "entry_price": trade.entry_price,
        "stop_loss": trade.stop_loss,
        "take_profit": trade.take_profit,
        "exit_index": trade.exit_index,
        "exit_time": trade.exit_time.isoformat(),
        "exit_price": trade.exit_price,
        "exit_reason": trade.exit_reason.value,
        "exit_fill_type": trade.exit_fill_type.value,
        "is_gap_exit": trade.is_gap_exit,
        "theoretical_exit_price": (trade.theoretical_exit_price),
        "gap_distance": trade.gap_distance,
        "holding_candles": trade.holding_candles,
        "price_pnl": trade.price_pnl,
        "return_fraction": trade.return_fraction,
        "r_multiple": trade.r_multiple,
        "is_winner": trade.is_winner,
        "hook_1": quality.hook_ratios.first,
        "hook_2": quality.hook_ratios.second,
        "nsi": quality.nsi.score,
    }


def _sized_trade_to_row(
    sized_trade: SizedTrade,
) -> dict[str, object]:
    row = _trade_to_row(sized_trade.trade)
    adjustment = sized_trade.cost_adjustment

    row.update(
        {
            "effective_entry_price": (adjustment.effective_entry_price),
            "effective_exit_price": (adjustment.effective_exit_price),
            "effective_stop_price": (adjustment.effective_stop_price),
            "balance_before": sized_trade.balance_before,
            "risk_amount": sized_trade.risk_amount,
            "actual_risk_amount": (sized_trade.actual_risk_amount),
            "risk_utilization_fraction": (sized_trade.risk_utilization_fraction),
            "raw_quantity": sized_trade.raw_quantity,
            "raw_lots": _raw_lots(sized_trade),
            "lots": ("" if sized_trade.lots is None else sized_trade.lots),
            "quantity": sized_trade.quantity,
            "contract_size": (
                "" if sized_trade.contract_size is None else sized_trade.contract_size
            ),
            "minimum_lot": _specification_value(
                sized_trade,
                "minimum_lot",
            ),
            "maximum_lot": _specification_value(
                sized_trade,
                "maximum_lot",
            ),
            "lot_step": _specification_value(
                sized_trade,
                "lot_step",
            ),
            "capped_at_maximum_lot": (sized_trade.capped_at_maximum_lot),
            "margin_enabled": (sized_trade.margin_check is not None),
            "leverage": _margin_value(
                sized_trade,
                "leverage",
            ),
            "notional_value": _margin_value(
                sized_trade,
                "notional_value",
            ),
            "margin_required": _margin_value(
                sized_trade,
                "margin_required",
            ),
            "free_margin_after_entry": _margin_value(
                sized_trade,
                "free_margin_after_entry",
            ),
            "margin_utilization_fraction": _margin_value(
                sized_trade,
                "margin_utilization_fraction",
            ),
            "margin_level_fraction": _margin_value(
                sized_trade,
                "margin_level_fraction",
            ),
            "gross_pnl_per_unit": (adjustment.gross_pnl_per_unit),
            "net_pnl_per_unit": adjustment.net_pnl_per_unit,
            "spread_slippage_cost_per_unit": (adjustment.spread_slippage_cost_per_unit),
            "total_commission_per_unit": (adjustment.total_commission_per_unit),
            "total_cost_per_unit": (adjustment.total_cost_per_unit),
            "gross_monetary_pnl": (sized_trade.gross_monetary_pnl),
            "spread_slippage_cost": (sized_trade.spread_slippage_cost),
            "commission_amount": (sized_trade.commission_amount),
            "total_cost_amount": (sized_trade.total_cost_amount),
            "net_monetary_pnl": sized_trade.monetary_pnl,
            "balance_after": sized_trade.balance_after,
            "net_r_multiple": sized_trade.r_multiple,
            "net_is_winner": sized_trade.is_winner,
        }
    )

    return row


def _raw_lots(
    sized_trade: SizedTrade,
) -> float | str:
    """Return raw lots when broker contract sizing is enabled."""
    if sized_trade.position_size is None:
        return ""

    return sized_trade.position_size.raw_lots


def _specification_value(
    sized_trade: SizedTrade,
    attribute: str,
) -> float | str:
    """Return one contract field or an empty CSV value."""
    if sized_trade.position_size is None:
        return ""

    specification = sized_trade.position_size.specification

    return float(getattr(specification, attribute))


def _margin_value(
    sized_trade: SizedTrade,
    attribute: str,
) -> float | str:
    """Return one margin field or an empty CSV value."""
    margin_check = sized_trade.margin_check

    if margin_check is None:
        return ""

    if attribute == "leverage":
        return margin_check.policy.leverage

    return float(getattr(margin_check, attribute))
