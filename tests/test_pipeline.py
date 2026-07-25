from datetime import UTC, datetime, timedelta

import pytest

from nds_bot.models import Candle, CycleDirection, NodeLabel
from nds_bot.pipeline import ScanConfig, scan_candles
from nds_bot.quality.validation import QualityThresholds

BASE_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def make_candle(index: int, price: float) -> Candle:
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


def test_default_scan_config_uses_six_candles_each_side() -> None:
    config = ScanConfig()

    assert config.extrema_window == 6


def test_pipeline_detects_and_validates_documented_cycle() -> None:
    candles = make_documented_cycle_candles()

    result = scan_candles(
        candles,
        config=ScanConfig(extrema_window=1),
    )

    assert len(result.cycles) == 1
    assert len(result.analyses) == 1
    assert len(result.valid_analyses) == 1
    assert len(result.rejected_analyses) == 0

    analysis = result.valid_analyses[0]

    assert analysis.cycle.direction is CycleDirection.BULL
    assert analysis.is_valid is True
    assert analysis.rejection_reasons == ()


def test_pipeline_exposes_intermediate_nodes() -> None:
    candles = make_documented_cycle_candles()

    result = scan_candles(
        candles,
        config=ScanConfig(extrema_window=1),
    )

    assert len(result.raw_nodes) == 6
    assert len(result.alternating_nodes) == 6

    labels = tuple(node.label for node in result.cycles[0].nodes)

    assert labels == (
        NodeLabel.Z,
        NodeLabel.N1,
        NodeLabel.S1,
        NodeLabel.N2,
        NodeLabel.S2,
        NodeLabel.N3,
    )


def test_pipeline_returns_no_cycles_for_monotonic_market() -> None:
    candles = [make_candle(index, 100.0 + index) for index in range(20)]

    result = scan_candles(
        candles,
        config=ScanConfig(extrema_window=1),
    )

    assert result.raw_nodes == ()
    assert result.alternating_nodes == ()
    assert result.cycles == ()
    assert result.analyses == ()


def test_custom_nsi_threshold_can_reject_cycle() -> None:
    candles = make_documented_cycle_candles()

    thresholds = QualityThresholds(
        maximum_nsi=0.10,
    )

    result = scan_candles(
        candles,
        config=ScanConfig(
            extrema_window=1,
            quality_thresholds=thresholds,
        ),
    )

    assert len(result.cycles) == 1
    assert len(result.valid_analyses) == 0
    assert len(result.rejected_analyses) == 1

    rejected = result.rejected_analyses[0]

    assert rejected.is_valid is False
    assert rejected.rejection_reasons == ("nsi",)


@pytest.mark.parametrize("window", [0, -1])
def test_invalid_extrema_window_is_rejected(window: int) -> None:
    with pytest.raises(
        ValueError,
        match="Extrema window must be at least 1",
    ):
        ScanConfig(extrema_window=window)


def test_unordered_candles_are_rejected() -> None:
    candles = make_documented_cycle_candles()

    candles[5], candles[6] = candles[6], candles[5]

    with pytest.raises(
        ValueError,
        match="Candles must be ordered by increasing time",
    ):
        scan_candles(
            candles,
            config=ScanConfig(extrema_window=1),
        )
