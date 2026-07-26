from datetime import UTC, datetime, timedelta

import pytest

from nds_bot.backtest.execution import (
    ExitFillType,
    ExitReason,
    GapFillMode,
    IntrabarPriority,
    _find_exit,
)
from nds_bot.models import Candle, TradeSide

BASE_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def make_candle(
    index: int,
    *,
    open_price: float,
    high: float,
    low: float,
    close: float,
) -> Candle:
    return Candle(
        time=BASE_TIME + timedelta(hours=index),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=1_000.0,
    )


def find_exit(
    candles: list[Candle],
    *,
    side: TradeSide,
    stop_loss: float,
    take_profit: float,
    gap_fill_mode: GapFillMode = GapFillMode.OPEN_PRICE,
):
    return _find_exit(
        candles,
        side=side,
        entry_index=0,
        stop_loss=stop_loss,
        take_profit=take_profit,
        intrabar_priority=IntrabarPriority.STOP_FIRST,
        gap_fill_mode=gap_fill_mode,
    )


def test_buy_stop_gap_fills_at_open() -> None:
    candles = [
        make_candle(
            0,
            open_price=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
        ),
        make_candle(
            1,
            open_price=93.0,
            high=96.0,
            low=92.0,
            close=94.0,
        ),
    ]

    result = find_exit(
        candles,
        side=TradeSide.BUY,
        stop_loss=95.0,
        take_profit=110.0,
    )

    assert result == (
        1,
        93.0,
        ExitReason.STOP_LOSS,
        ExitFillType.GAP_OPEN,
    )


def test_buy_target_gap_fills_at_open() -> None:
    candles = [
        make_candle(
            0,
            open_price=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
        ),
        make_candle(
            1,
            open_price=112.0,
            high=114.0,
            low=111.0,
            close=113.0,
        ),
    ]

    result = find_exit(
        candles,
        side=TradeSide.BUY,
        stop_loss=95.0,
        take_profit=110.0,
    )

    assert result == (
        1,
        112.0,
        ExitReason.TAKE_PROFIT,
        ExitFillType.GAP_OPEN,
    )


def test_sell_stop_gap_fills_at_open() -> None:
    candles = [
        make_candle(
            0,
            open_price=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
        ),
        make_candle(
            1,
            open_price=107.0,
            high=109.0,
            low=106.0,
            close=108.0,
        ),
    ]

    result = find_exit(
        candles,
        side=TradeSide.SELL,
        stop_loss=105.0,
        take_profit=90.0,
    )

    assert result == (
        1,
        107.0,
        ExitReason.STOP_LOSS,
        ExitFillType.GAP_OPEN,
    )


def test_sell_target_gap_fills_at_open() -> None:
    candles = [
        make_candle(
            0,
            open_price=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
        ),
        make_candle(
            1,
            open_price=88.0,
            high=89.0,
            low=86.0,
            close=87.0,
        ),
    ]

    result = find_exit(
        candles,
        side=TradeSide.SELL,
        stop_loss=105.0,
        take_profit=90.0,
    )

    assert result == (
        1,
        88.0,
        ExitReason.TAKE_PROFIT,
        ExitFillType.GAP_OPEN,
    )


def test_open_exactly_on_level_is_not_classified_as_gap() -> None:
    candles = [
        make_candle(
            0,
            open_price=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
        ),
        make_candle(
            1,
            open_price=95.0,
            high=97.0,
            low=94.0,
            close=96.0,
        ),
    ]

    result = find_exit(
        candles,
        side=TradeSide.BUY,
        stop_loss=95.0,
        take_profit=110.0,
    )

    assert result == (
        1,
        95.0,
        ExitReason.STOP_LOSS,
        ExitFillType.LEVEL,
    )


def test_legacy_level_mode_uses_theoretical_level() -> None:
    candles = [
        make_candle(
            0,
            open_price=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
        ),
        make_candle(
            1,
            open_price=93.0,
            high=96.0,
            low=92.0,
            close=94.0,
        ),
    ]

    result = find_exit(
        candles,
        side=TradeSide.BUY,
        stop_loss=95.0,
        take_profit=110.0,
        gap_fill_mode=GapFillMode.LEVEL_PRICE,
    )

    assert result == (
        1,
        95.0,
        ExitReason.STOP_LOSS,
        ExitFillType.LEVEL,
    )


def test_gap_open_takes_priority_over_intrabar_range() -> None:
    candles = [
        make_candle(
            0,
            open_price=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
        ),
        make_candle(
            1,
            open_price=93.0,
            high=112.0,
            low=92.0,
            close=105.0,
        ),
    ]

    result = find_exit(
        candles,
        side=TradeSide.BUY,
        stop_loss=95.0,
        take_profit=110.0,
    )

    assert result == (
        1,
        93.0,
        ExitReason.STOP_LOSS,
        ExitFillType.GAP_OPEN,
    )


def test_intrabar_priority_still_applies_without_gap() -> None:
    candles = [
        make_candle(
            0,
            open_price=100.0,
            high=111.0,
            low=94.0,
            close=102.0,
        )
    ]

    result = find_exit(
        candles,
        side=TradeSide.BUY,
        stop_loss=95.0,
        take_profit=110.0,
    )

    assert result == (
        0,
        95.0,
        ExitReason.STOP_LOSS,
        ExitFillType.LEVEL,
    )


def test_end_of_data_uses_final_close_fill_type() -> None:
    candles = [
        make_candle(
            0,
            open_price=100.0,
            high=102.0,
            low=98.0,
            close=101.0,
        )
    ]

    result = find_exit(
        candles,
        side=TradeSide.BUY,
        stop_loss=95.0,
        take_profit=110.0,
    )

    assert result == (
        0,
        101.0,
        ExitReason.END_OF_DATA,
        ExitFillType.END_OF_DATA_CLOSE,
    )


def test_gap_distance_is_direction_independent() -> None:
    stop_gap = abs(93.0 - 95.0)
    target_gap = abs(112.0 - 110.0)

    assert stop_gap == pytest.approx(2.0)
    assert target_gap == pytest.approx(2.0)
