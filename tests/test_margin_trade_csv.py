import csv
from pathlib import Path

import pytest

from nds_bot.backtest.account import AccountPolicy
from nds_bot.backtest.contracts import ContractSpecification
from nds_bot.backtest.costs import TradingCostPolicy
from nds_bot.backtest.margin import MarginPolicy
from nds_bot.backtest.runner import run_backtest
from nds_bot.data.csv_loader import load_candles_csv
from nds_bot.data.trade_csv import write_sized_trades_csv
from nds_bot.pipeline import ScanConfig

SAMPLE_CSV = Path("data/samples/documented_bull_cycle_execution.csv")


def load_sample_candles():
    return load_candles_csv(SAMPLE_CSV)


def test_margin_fields_are_exported(
    tmp_path: Path,
) -> None:
    result = run_backtest(
        load_sample_candles(),
        config=ScanConfig(extrema_window=1),
        account_policy=AccountPolicy(),
        cost_policy=TradingCostPolicy(
            spread_fraction=0.0002,
            slippage_fraction=0.00005,
            commission_fraction=0.0001,
        ),
        contract_specification=ContractSpecification(),
        margin_policy=MarginPolicy(leverage=100.0),
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

    assert row["margin_enabled"] == "True"
    assert float(row["leverage"]) == pytest.approx(100.0)
    assert float(row["notional_value"]) == pytest.approx(25_089.23605)
    assert float(row["margin_required"]) == pytest.approx(250.8923605)
    assert float(row["free_margin_after_entry"]) == pytest.approx(9_749.1076395)
    assert float(row["margin_utilization_fraction"]) == pytest.approx(0.02508923605)
    assert float(row["margin_level_fraction"]) == pytest.approx(39.857730144)


def test_margin_disabled_keeps_fields_empty(
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

    assert row["margin_enabled"] == "False"
    assert row["leverage"] == ""
    assert row["notional_value"] == ""
    assert row["margin_required"] == ""
    assert row["free_margin_after_entry"] == ""
    assert row["margin_utilization_fraction"] == ""
    assert row["margin_level_fraction"] == ""
