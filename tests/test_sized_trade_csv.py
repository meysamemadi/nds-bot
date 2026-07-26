import csv
from pathlib import Path

import pytest

from nds_bot.backtest.account import AccountPolicy
from nds_bot.backtest.costs import TradingCostPolicy
from nds_bot.backtest.runner import run_backtest
from nds_bot.data.csv_loader import load_candles_csv
from nds_bot.data.trade_csv import write_sized_trades_csv
from nds_bot.pipeline import ScanConfig


def test_writes_cost_adjusted_sized_trade_csv(
    tmp_path: Path,
) -> None:
    candles = load_candles_csv(Path("data/samples/documented_bull_cycle_execution.csv"))

    result = run_backtest(
        candles,
        config=ScanConfig(extrema_window=1),
        account_policy=AccountPolicy(
            initial_balance=10_000.0,
            risk_fraction=0.01,
        ),
        cost_policy=TradingCostPolicy(
            spread_fraction=0.0002,
            slippage_fraction=0.00005,
            commission_fraction=0.0001,
        ),
    )

    assert result.account is not None

    output_path = write_sized_trades_csv(
        result.account.trades,
        tmp_path / "results" / "trades.csv",
    )

    with output_path.open(
        encoding="utf-8",
        newline="",
    ) as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert len(rows) == 1

    row = rows[0]

    assert row["side"] == "SELL"
    assert row["exit_reason"] == "TAKE_PROFIT"

    assert float(row["effective_entry_price"]) == pytest.approx(1.09083635)

    assert float(row["effective_exit_price"]) == pytest.approx(1.08356251)

    assert float(row["quantity"]) == pytest.approx(23_007.28150297)

    assert float(row["total_cost_amount"]) == pytest.approx(12.506755602)

    assert float(row["net_monetary_pnl"]) == pytest.approx(162.34858382)

    assert float(row["balance_after"]) == pytest.approx(10_162.34858382)

    assert float(row["net_r_multiple"]) == pytest.approx(1.6234858382)

    assert row["net_is_winner"] == "True"


def test_empty_sized_trade_export_contains_header(
    tmp_path: Path,
) -> None:
    output_path = write_sized_trades_csv(
        [],
        tmp_path / "trades.csv",
    )

    lines = output_path.read_text(encoding="utf-8").splitlines()

    assert len(lines) == 1
    assert lines[0].startswith("side,signal_index")
    assert "effective_entry_price" in lines[0]
    assert "net_monetary_pnl" in lines[0]
