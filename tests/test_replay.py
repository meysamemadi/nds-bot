from datetime import UTC, datetime, timedelta

import pytest

from nds_bot.models import Candle
from nds_bot.pipeline import ScanConfig
from nds_bot.quality.validation import QualityThresholds
from nds_bot.replay import replay_candles

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


def make_documented_cycle_candles() -> list[Candle]:
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


def test_replay_waits_for_right_side_confirmation() -> None:
    candles = make_documented_cycle_candles()

    result = replay_candles(
        candles[:-1],
        config=ScanConfig(extrema_window=1),
    )

    assert result.events == ()


def test_replay_emits_cycle_after_confirmation() -> None:
    candles = make_documented_cycle_candles()

    result = replay_candles(
        candles,
        config=ScanConfig(extrema_window=1),
    )

    assert len(result.events) == 1
    assert len(result.valid_events) == 1
    assert len(result.rejected_events) == 0

    event = result.events[0]

    assert event.is_valid is True
    assert event.rejection_reasons == ()


def test_replay_records_confirmation_metadata() -> None:
    candles = make_documented_cycle_candles()

    result = replay_candles(
        candles,
        config=ScanConfig(extrema_window=1),
    )

    event = result.events[0]

    assert event.confirmed_at_index == 12
    assert event.confirmed_at_time == candles[12].time

    assert event.cycle_indexes == (
        1,
        3,
        5,
        7,
        9,
        11,
    )


def test_replay_does_not_duplicate_existing_cycle() -> None:
    candles = make_documented_cycle_candles()

    candles.extend(
        [
            make_candle(13, 1.09100),
            make_candle(14, 1.09000),
            make_candle(15, 1.08900),
        ]
    )

    result = replay_candles(
        candles,
        config=ScanConfig(extrema_window=1),
    )

    assert len(result.events) == 1


def test_replay_can_emit_rejected_cycle() -> None:
    candles = make_documented_cycle_candles()

    strict_thresholds = QualityThresholds(
        maximum_nsi=0.10,
    )

    result = replay_candles(
        candles,
        config=ScanConfig(
            extrema_window=1,
            quality_thresholds=strict_thresholds,
        ),
    )

    assert len(result.events) == 1
    assert result.valid_events == ()
    assert len(result.rejected_events) == 1

    rejected_event = result.rejected_events[0]

    assert rejected_event.is_valid is False
    assert rejected_event.rejection_reasons == ("nsi",)


def test_empty_replay_returns_no_events() -> None:
    result = replay_candles(
        [],
        config=ScanConfig(extrema_window=1),
    )

    assert result.events == ()
    assert result.valid_events == ()
    assert result.rejected_events == ()


def test_unordered_replay_candles_are_rejected() -> None:
    candles = make_documented_cycle_candles()

    candles[5], candles[6] = (
        candles[6],
        candles[5],
    )

    with pytest.raises(
        ValueError,
        match="Candles must be ordered by increasing time",
    ):
        replay_candles(
            candles,
            config=ScanConfig(extrema_window=1),
        )
