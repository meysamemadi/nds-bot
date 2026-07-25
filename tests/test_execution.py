from datetime import UTC, datetime, timedelta

import pytest

from nds_bot.backtest.execution import (
    ExecutionPolicy,
    ExitReason,
    IntrabarPriority,
    execute_signals,
)
from nds_bot.models import Candle
from nds_bot.pipeline import ScanConfig
from nds_bot.replay import replay_candles
from nds_bot.signals import build_trade_signals

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


def make_flat_candle(
    index: int,
    price: float,
) -> Candle:
    return make_candle(
        index,
        open_price=price,
        high=price,
        low=price,
        close=price,
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

    return [make_flat_candle(index, price) for index, price in enumerate(prices)]


def build_signals(
    candles: list[Candle],
):
    replay_result = replay_candles(
        candles,
        config=ScanConfig(extrema_window=1),
    )

    return build_trade_signals(
        candles,
        replay_result,
    )


def test_sell_signal_enters_next_open_and_hits_target() -> None:
    candles = make_cycle_candles()

    candles.extend(
        [
            make_candle(
                13,
                open_price=1.09100,
                high=1.09300,
                low=1.08800,
                close=1.08900,
            ),
            make_candle(
                14,
                open_price=1.08900,
                high=1.09000,
                low=1.08200,
                close=1.08400,
            ),
        ]
    )

    signals = build_signals(candles)
    result = execute_signals(candles, signals)

    assert len(result.trades) == 1
    assert result.unfilled_signals == ()

    trade = result.trades[0]

    assert trade.entry_index == 13
    assert trade.entry_price == pytest.approx(1.09100)
    assert trade.stop_loss == pytest.approx(1.09480)
    assert trade.take_profit == pytest.approx(1.08340)

    assert trade.exit_index == 14
    assert trade.exit_price == pytest.approx(1.08340)
    assert trade.exit_reason is ExitReason.TAKE_PROFIT

    assert trade.price_pnl == pytest.approx(0.00760)
    assert trade.r_multiple == pytest.approx(2.0)
    assert trade.is_winner is True

    assert result.win_rate == pytest.approx(1.0)
    assert result.mean_r_multiple == pytest.approx(2.0)


def test_sell_signal_can_hit_stop_loss() -> None:
    candles = make_cycle_candles()

    candles.append(
        make_candle(
            13,
            open_price=1.09100,
            high=1.09500,
            low=1.09000,
            close=1.09400,
        )
    )

    result = execute_signals(
        candles,
        build_signals(candles),
    )

    trade = result.trades[0]

    assert trade.exit_index == 13
    assert trade.exit_reason is ExitReason.STOP_LOSS
    assert trade.exit_price == pytest.approx(1.09480)
    assert trade.price_pnl == pytest.approx(-0.00380)
    assert trade.r_multiple == pytest.approx(-1.0)
    assert trade.is_winner is False


def test_stop_is_assumed_first_when_both_levels_hit() -> None:
    candles = make_cycle_candles()

    candles.append(
        make_candle(
            13,
            open_price=1.09100,
            high=1.09500,
            low=1.08300,
            close=1.09000,
        )
    )

    result = execute_signals(
        candles,
        build_signals(candles),
    )

    assert result.trades[0].exit_reason is ExitReason.STOP_LOSS


def test_take_profit_can_be_prioritized() -> None:
    candles = make_cycle_candles()

    candles.append(
        make_candle(
            13,
            open_price=1.09100,
            high=1.09500,
            low=1.08300,
            close=1.09000,
        )
    )

    policy = ExecutionPolicy(intrabar_priority=(IntrabarPriority.TAKE_PROFIT_FIRST))

    result = execute_signals(
        candles,
        build_signals(candles),
        policy=policy,
    )

    assert result.trades[0].exit_reason is ExitReason.TAKE_PROFIT


def test_open_trade_is_closed_at_end_of_data() -> None:
    candles = make_cycle_candles()

    candles.append(
        make_candle(
            13,
            open_price=1.09100,
            high=1.09300,
            low=1.08800,
            close=1.08900,
        )
    )

    result = execute_signals(
        candles,
        build_signals(candles),
    )

    trade = result.trades[0]

    assert trade.exit_reason is ExitReason.END_OF_DATA
    assert trade.exit_index == 13
    assert trade.exit_price == pytest.approx(1.08900)
    assert trade.price_pnl == pytest.approx(0.00200)


def test_signal_without_next_candle_is_unfilled() -> None:
    candles = make_cycle_candles()
    signals = build_signals(candles)

    result = execute_signals(
        candles,
        signals,
    )

    assert result.trades == ()
    assert result.unfilled_signals == signals


def test_sell_entry_above_n3_is_rejected() -> None:
    candles = make_cycle_candles()

    candles.append(
        make_candle(
            13,
            open_price=1.09600,
            high=1.09700,
            low=1.09500,
            close=1.09600,
        )
    )

    with pytest.raises(
        ValueError,
        match="SELL stop loss must be above entry price",
    ):
        execute_signals(
            candles,
            build_signals(candles),
        )


def test_unordered_candles_are_rejected() -> None:
    ordered_candles = make_cycle_candles()
    signals = build_signals(ordered_candles)

    unordered_candles = list(ordered_candles)

    (
        unordered_candles[5],
        unordered_candles[6],
    ) = (
        unordered_candles[6],
        unordered_candles[5],
    )

    with pytest.raises(
        ValueError,
        match="Candles must be ordered by increasing time",
    ):
        execute_signals(
            unordered_candles,
            signals,
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"reward_to_risk": 0.0},
        {"stop_buffer_fraction": -0.1},
        {"stop_buffer_fraction": 1.0},
    ],
)
def test_invalid_execution_policy_is_rejected(
    kwargs: dict[str, float],
) -> None:
    with pytest.raises(ValueError):
        ExecutionPolicy(**kwargs)
