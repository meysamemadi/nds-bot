from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from nds_bot.models import (
    Candle,
    TradeSide,
)
from nds_bot.pipeline import ScanConfig
from nds_bot.quality.validation import QualityThresholds
from nds_bot.replay import ReplayResult, replay_candles
from nds_bot.signals import (
    SignalPolicy,
    build_trade_signals,
)

BASE_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def make_candle(
    index: int,
    price: float,
) -> Candle:
    return Candle(
        time=BASE_TIME + timedelta(hours=index),
        open=price,
        high=price,
        low=price,
        close=price,
        volume=1_000.0,
    )


def make_cycle_candles() -> list[Candle]:
    prices = [
        1.08100,
        1.08000,
        1.08300,
        1.08650,
        1.08400,
        1.08230,
        1.08600,
        1.09100,
        1.08800,
        1.08600,
        1.09000,
        1.09480,
        1.09200,
    ]

    return [make_candle(index, price) for index, price in enumerate(prices)]


def test_valid_bull_event_generates_sell_signal() -> None:
    candles = make_cycle_candles()

    replay_result = replay_candles(
        candles,
        config=ScanConfig(extrema_window=1),
    )

    signals = build_trade_signals(
        candles,
        replay_result,
    )

    assert len(signals) == 1

    signal = signals[0]

    assert signal.side is TradeSide.SELL
    assert signal.generated_at_index == 12
    assert signal.generated_at_time == candles[12].time
    assert signal.reference_price == pytest.approx(candles[12].close)
    assert signal.n3_price == pytest.approx(1.09480)

    assert signal.cycle_indexes == (
        1,
        3,
        5,
        7,
        9,
        11,
    )


def test_rejected_event_does_not_generate_signal() -> None:
    candles = make_cycle_candles()

    replay_result = replay_candles(
        candles,
        config=ScanConfig(
            extrema_window=1,
            quality_thresholds=QualityThresholds(
                maximum_nsi=0.10,
            ),
        ),
    )

    signals = build_trade_signals(
        candles,
        replay_result,
    )

    assert len(replay_result.rejected_events) == 1
    assert signals == ()


def test_signal_policy_can_override_bull_side() -> None:
    candles = make_cycle_candles()

    replay_result = replay_candles(
        candles,
        config=ScanConfig(extrema_window=1),
    )

    policy = SignalPolicy(
        bull_cycle_side=TradeSide.BUY,
    )

    signals = build_trade_signals(
        candles,
        replay_result,
        policy=policy,
    )

    assert signals[0].side is TradeSide.BUY


def test_invalid_confirmation_index_is_rejected() -> None:
    candles = make_cycle_candles()

    replay_result = replay_candles(
        candles,
        config=ScanConfig(extrema_window=1),
    )

    invalid_event = replace(
        replay_result.events[0],
        confirmed_at_index=100,
    )

    invalid_result = ReplayResult(
        events=(invalid_event,),
    )

    with pytest.raises(
        ValueError,
        match="confirmation index is outside",
    ):
        build_trade_signals(
            candles,
            invalid_result,
        )


def test_confirmation_time_mismatch_is_rejected() -> None:
    candles = make_cycle_candles()

    replay_result = replay_candles(
        candles,
        config=ScanConfig(extrema_window=1),
    )

    invalid_event = replace(
        replay_result.events[0],
        confirmed_at_index=11,
    )

    invalid_result = ReplayResult(
        events=(invalid_event,),
    )

    with pytest.raises(
        ValueError,
        match="confirmation time does not match",
    ):
        build_trade_signals(
            candles,
            invalid_result,
        )
