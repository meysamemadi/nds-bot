import csv
from pathlib import Path

import pytest

from nds_bot.backtest.account import AccountPolicy
from nds_bot.backtest.contracts import ContractSpecification
from nds_bot.backtest.costs import TradingCostPolicy
from nds_bot.backtest.runner import run_backtest
from nds_bot.data.csv_loader import load_candles_csv
from nds_bot.data.trade_csv import write_sized_trades_csv
from nds_bot.pipeline import ScanConfig


def load_sample_candles():
    return load_candles_csv(Path("data/samples/documented_bull_cycle_execution.csv"))


def test_contract_sizing_fields_are_exported(
    tmp_path: Path,
) -> None:
    result = run_backtest(
        load_sample_candles(),
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
        contract_specification=ContractSpecification(
            contract_size=100_000.0,
            minimum_lot=0.01,
            maximum_lot=100.0,
            lot_step=0.01,
        ),
    )

    assert result.account is not None

    output_path = write_sized_trades_csv(
        result.account.trades,
        tmp_path / "trades.csv",
    )

    with output_path.open(
        encoding="utf-8",
        newline="",
    ) as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert len(rows) == 1
    row = rows[0]

    assert float(row["raw_quantity"]) == pytest.approx(23_007.28150297)
    assert float(row["raw_lots"]) == pytest.approx(0.2300728150297)
    assert float(row["lots"]) == pytest.approx(0.23)
    assert float(row["quantity"]) == pytest.approx(23_000.0)
    assert float(row["contract_size"]) == pytest.approx(100_000.0)
    assert float(row["minimum_lot"]) == pytest.approx(0.01)
    assert float(row["maximum_lot"]) == pytest.approx(100.0)
    assert float(row["lot_step"]) == pytest.approx(0.01)
    assert float(row["actual_risk_amount"]) == pytest.approx(99.968351311)
    assert float(row["risk_utilization_fraction"]) == pytest.approx(0.99968351311)
    assert row["capped_at_maximum_lot"] == "False"


def test_unconstrained_export_keeps_contract_fields_empty(
    tmp_path: Path,
) -> None:
    result = run_backtest(
        load_sample_candles(),
        config=ScanConfig(extrema_window=1),
        account_policy=AccountPolicy(),
    )

    assert result.account is not None

    output_path = write_sized_trades_csv(
        result.account.trades,
        tmp_path / "trades.csv",
    )

    with output_path.open(
        encoding="utf-8",
        newline="",
    ) as csv_file:
        row = next(csv.DictReader(csv_file))

    assert row["raw_lots"] == ""
    assert row["lots"] == ""
    assert row["contract_size"] == ""
    assert row["minimum_lot"] == ""
    assert row["maximum_lot"] == ""
    assert row["lot_step"] == ""
    assert float(row["actual_risk_amount"]) == pytest.approx(100.0)
    assert float(row["risk_utilization_fraction"]) == pytest.approx(1.0)
