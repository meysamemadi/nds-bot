import csv
from collections.abc import Iterable, Sequence
from pathlib import Path

from nds_bot.broker.models import (
    PaperClosedTrade,
    PaperEquityPoint,
    PaperOrder,
)

PAPER_ORDER_COLUMNS = (
    "order_id",
    "symbol",
    "side",
    "status",
    "status_reason",
    "signal_index",
    "signal_time",
    "scheduled_entry_index",
    "cycle_direction",
    "created_index",
    "created_time",
    "filled_index",
    "filled_time",
    "closed_index",
    "closed_time",
)

PAPER_TRADE_COLUMNS = (
    "trade_id",
    "position_id",
    "order_id",
    "symbol",
    "side",
    "entry_index",
    "entry_time",
    "raw_entry_price",
    "effective_entry_price",
    "stop_loss",
    "take_profit",
    "exit_index",
    "exit_time",
    "raw_exit_price",
    "effective_exit_price",
    "exit_reason",
    "exit_fill_type",
    "is_gap_exit",
    "gap_distance",
    "quantity",
    "lots",
    "requested_risk_amount",
    "actual_risk_amount",
    "gross_monetary_pnl",
    "spread_slippage_cost",
    "commission_amount",
    "total_cost_amount",
    "net_monetary_pnl",
    "net_r_multiple",
    "balance_before",
    "balance_after",
    "is_winner",
)

PAPER_EQUITY_COLUMNS = (
    "event_number",
    "time",
    "balance",
    "peak_balance",
    "drawdown_amount",
    "drawdown_fraction",
)


class PaperCsvError(ValueError):
    """Raised when a paper-trading CSV cannot be written."""


def write_paper_orders_csv(
    orders: Sequence[PaperOrder],
    path: str | Path,
) -> Path:
    return _write_rows(
        path=path,
        fieldnames=PAPER_ORDER_COLUMNS,
        rows=(_order_to_row(order) for order in orders),
    )


def write_paper_trades_csv(
    trades: Sequence[PaperClosedTrade],
    path: str | Path,
) -> Path:
    return _write_rows(
        path=path,
        fieldnames=PAPER_TRADE_COLUMNS,
        rows=(_trade_to_row(trade) for trade in trades),
    )


def write_paper_equity_csv(
    equity_curve: Sequence[PaperEquityPoint],
    path: str | Path,
) -> Path:
    return _write_rows(
        path=path,
        fieldnames=PAPER_EQUITY_COLUMNS,
        rows=(_equity_point_to_row(point) for point in equity_curve),
    )


def _write_rows(
    *,
    path: str | Path,
    fieldnames: Sequence[str],
    rows: Iterable[dict[str, object]],
) -> Path:
    output_path = Path(path)

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)

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
        raise PaperCsvError(f"Could not write paper-trading CSV file: {output_path}") from error

    return output_path


def _order_to_row(order: PaperOrder) -> dict[str, object]:
    signal = order.signal

    return {
        "order_id": order.order_id,
        "symbol": order.symbol,
        "side": order.side.value,
        "status": order.status.value,
        "status_reason": order.status_reason or "",
        "signal_index": signal.generated_at_index,
        "signal_time": signal.generated_at_time.isoformat(),
        "scheduled_entry_index": order.scheduled_entry_index,
        "cycle_direction": signal.cycle_direction.value,
        "created_index": order.created_index,
        "created_time": order.created_time.isoformat(),
        "filled_index": _optional_value(order.filled_index),
        "filled_time": _optional_time(order.filled_time),
        "closed_index": _optional_value(order.closed_index),
        "closed_time": _optional_time(order.closed_time),
    }


def _trade_to_row(
    trade: PaperClosedTrade,
) -> dict[str, object]:
    position = trade.position
    raw_trade = trade.raw_trade
    adjustment = trade.cost_adjustment

    return {
        "trade_id": trade.trade_id,
        "position_id": position.position_id,
        "order_id": trade.order_id,
        "symbol": trade.symbol,
        "side": trade.side.value,
        "entry_index": position.entry_index,
        "entry_time": position.entry_time.isoformat(),
        "raw_entry_price": position.raw_entry_price,
        "effective_entry_price": position.effective_entry_price,
        "stop_loss": position.stop_loss,
        "take_profit": position.take_profit,
        "exit_index": raw_trade.exit_index,
        "exit_time": raw_trade.exit_time.isoformat(),
        "raw_exit_price": raw_trade.exit_price,
        "effective_exit_price": adjustment.effective_exit_price,
        "exit_reason": raw_trade.exit_reason.value,
        "exit_fill_type": raw_trade.exit_fill_type.value,
        "is_gap_exit": raw_trade.is_gap_exit,
        "gap_distance": raw_trade.gap_distance,
        "quantity": position.quantity,
        "lots": _optional_value(position.lots),
        "requested_risk_amount": position.requested_risk_amount,
        "actual_risk_amount": position.actual_risk_amount,
        "gross_monetary_pnl": trade.gross_monetary_pnl,
        "spread_slippage_cost": trade.spread_slippage_cost,
        "commission_amount": trade.commission_amount,
        "total_cost_amount": trade.total_cost_amount,
        "net_monetary_pnl": trade.net_monetary_pnl,
        "net_r_multiple": trade.net_r_multiple,
        "balance_before": trade.balance_before,
        "balance_after": trade.balance_after,
        "is_winner": trade.is_winner,
    }


def _equity_point_to_row(
    point: PaperEquityPoint,
) -> dict[str, object]:
    return {
        "event_number": point.event_number,
        "time": _optional_time(point.time),
        "balance": point.balance,
        "peak_balance": point.peak_balance,
        "drawdown_amount": point.drawdown_amount,
        "drawdown_fraction": point.drawdown_fraction,
    }


def _optional_value(value: object | None) -> object:
    return "" if value is None else value


def _optional_time(value: object | None) -> object:
    if value is None:
        return ""

    return value.isoformat()
