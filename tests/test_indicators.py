from __future__ import annotations

import math

import pytest

from radar.indicators import (
    IndicatorError,
    atr,
    compute_indicators,
    ema,
    indicator_snapshot,
    latest_value,
    momentum,
    relative_volume,
    rsi,
    trend_from_emas,
    true_range,
    volatility,
)
from radar.models import Candle


# ============================================================
# HELPERS
# ============================================================

def candle(
    timestamp: int,
    open_price: float,
    high: float,
    low: float,
    close: float,
    volume: float = 1000.0,
    closed: bool = True,
) -> Candle:
    return Candle(
        timestamp=timestamp,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
        is_closed=closed,
    )


def candles_from_closes(
    values: list[float],
    volume: float = 1000.0,
) -> list[Candle]:
    result = []

    for i, close in enumerate(values):
        result.append(
            candle(
                timestamp=i * 60_000,
                open_price=close,
                high=close + 1.0,
                low=close - 1.0,
                close=close,
                volume=volume,
            )
        )

    return result


def rising_candles(count: int) -> list[Candle]:
    return candles_from_closes(
        [100.0 + i for i in range(count)]
    )


# ============================================================
# EMA
# ============================================================

def test_ema_rejects_invalid_period():
    with pytest.raises(ValueError):
        ema([1.0, 2.0, 3.0], 0)


def test_ema_returns_same_length():
    values = [100.0, 110.0, 120.0, 130.0]

    result = ema(values, 3)

    assert len(result) == len(values)


def test_ema_uses_initial_sma():
    values = [100.0, 110.0, 120.0]

    result = ema(values, 3)

    assert result[0] is None
    assert result[1] is None
    assert result[2] == pytest.approx(110.0)


def test_ema_calculates_next_value():
    values = [100.0, 110.0, 120.0, 130.0]

    result = ema(values, 3)

    assert result[3] == pytest.approx(120.0)


def test_ema_returns_none_when_insufficient_data():
    result = ema([100.0, 110.0], 3)

    assert result == [None, None]


# ============================================================
# RSI
# ============================================================

def test_rsi_rejects_invalid_period():
    with pytest.raises(ValueError):
        rsi([1.0, 2.0, 3.0], 0)


def test_rsi_requires_period_plus_one_values():
    result = rsi([100.0, 101.0, 102.0], 3)

    assert result == [None, None, None]


def test_rsi_all_gains_is_100():
    values = [
        100.0,
        101.0,
        102.0,
        103.0,
        104.0,
    ]

    result = rsi(values, 3)

    assert result[-1] == pytest.approx(100.0)


def test_rsi_all_losses_is_zero():
    values = [
        104.0,
        103.0,
        102.0,
        101.0,
        100.0,
    ]

    result = rsi(values, 3)

    assert result[-1] == pytest.approx(0.0)


def test_rsi_flat_market_is_50():
    values = [
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
    ]

    result = rsi(values, 3)

    assert result[-1] == pytest.approx(50.0)


def test_rsi_stays_between_zero_and_hundred():
    values = [
        100.0,
        102.0,
        101.0,
        105.0,
        103.0,
        107.0,
        104.0,
        110.0,
    ]

    result = rsi(values, 3)

    valid = [
        value
        for value in result
        if value is not None
    ]

    assert valid

    for value in valid:
        assert 0.0 <= value <= 100.0


# ============================================================
# TRUE RANGE
# ============================================================

def test_true_range_first_candle_uses_high_low():
    data = [
        candle(
            1,
            95.0,
            110.0,
            90.0,
            100.0,
        )
    ]

    result = true_range(data)

    assert len(result) == 1
    assert result[0] == pytest.approx(20.0)


def test_true_range_uses_previous_close():
    data = [
        candle(
            1,
            95.0,
            110.0,
            90.0,
            100.0,
        ),
        candle(
            2,
            105.0,
            120.0,
            105.0,
            115.0,
        ),
    ]

    result = true_range(data)

    assert result[0] == pytest.approx(20.0)
    assert result[1] == pytest.approx(20.0)


def test_true_range_handles_gap_down():
    data = [
        candle(
            1,
            105.0,
            110.0,
            100.0,
            110.0,
        ),
        candle(
            2,
            95.0,
            100.0,
            90.0,
            95.0,
        ),
    ]

    result = true_range(data)

    assert result[0] == pytest.approx(10.0)
    assert result[1] == pytest.approx(20.0)


def test_true_range_returns_one_value_per_candle():
    data = rising_candles(20)

    result = true_range(data)

    assert len(result) == len(data)

    for value in result:
        assert math.isfinite(value)
        assert value >= 0.0


def test_true_range_rejects_empty_data():
    with pytest.raises(IndicatorError):
        true_range([])


# ============================================================
# ATR
# ============================================================

def test_atr_returns_same_length():
    data = rising_candles(30)

    result = atr(data, 14)

    assert len(result) == len(data)


def test_atr_has_initial_value_at_period_minus_one():
    data = candles_from_closes(
        [100.0] * 20
    )

    result = atr(data, 14)

    for i in range(13):
        assert result[i] is None

    assert result[13] == pytest.approx(2.0)


def test_atr_values_are_non_negative():
    data = rising_candles(40)

    result = atr(data, 14)

    valid = [
        value
        for value in result
        if value is not None
    ]

    assert valid

    for value in valid:
        assert value >= 0.0


def test_atr_rejects_insufficient_data():
    data = rising_candles(5)

    with pytest.raises(IndicatorError):
        atr(data, 14)


# ============================================================
# VOLATILITY
# ============================================================

def test_volatility_returns_same_length():
    values = [
        100.0,
        101.0,
        102.0,
        101.0,
        103.0,
        105.0,
    ]

    result = volatility(values, 3)

    assert len(result) == len(values)


def test_volatility_flat_market_is_zero():
    values = [100.0] * 10

    result = volatility(values, 3)

    valid = [
        value
        for value in result
        if value is not None
    ]

    assert valid

    for value in valid:
        assert value == pytest.approx(0.0)


def test_volatility_is_non_negative():
    values = [
        100.0,
        102.0,
        99.0,
        105.0,
        101.0,
        108.0,
    ]

    result = volatility(values, 3)

    valid = [
        value
        for value in result
        if value is not None
    ]

    assert valid

    for value in valid:
        assert value >= 0.0


# ============================================================
# MOMENTUM
# ============================================================

def test_momentum_returns_none_before_period():
    values = [
        100.0,
        110.0,
        120.0,
        130.0,
    ]

    result = momentum(values, 2)

    assert result[0] is None
    assert result[1] is None


def test_momentum_calculates_percentage():
    values = [
        100.0,
        110.0,
        120.0,
        130.0,
    ]

    result = momentum(values, 2)

    assert result[2] == pytest.approx(20.0)
    assert result[3] == pytest.approx(
        ((130.0 / 110.0) - 1.0) * 100.0
    )


def test_momentum_detects_negative_move():
    values = [
        100.0,
        90.0,
        80.0,
    ]

    result = momentum(values, 2)

    assert result[2] == pytest.approx(-20.0)


# ============================================================
# RELATIVE VOLUME
# ============================================================

def test_relative_volume_uses_previous_volume():
    data = [
        candle(1, 100, 101, 99, 100, 100),
        candle(2, 100, 101, 99, 100, 100),
        candle(3, 100, 101, 99, 100, 100),
        candle(4, 100, 101, 99, 100, 300),
    ]

    result = relative_volume(data, 3)

    assert result[-1] == pytest.approx(3.0)


def test_relative_volume_does_not_include_current_volume():
    data = [
        candle(1, 100, 101, 99, 100, 100),
        candle(2, 100, 101, 99, 100, 100),
        candle(3, 100, 101, 99, 100, 100),
        candle(4, 100, 101, 99, 100, 10000),
    ]

    result = relative_volume(data, 3)

    assert result[-1] == pytest.approx(100.0)


def test_relative_volume_returns_none_when_insufficient_data():
    data = candles_from_closes(
        [100.0, 101.0, 102.0]
    )

    result = relative_volume(data, 3)

    assert result[0] is None
    assert result[1] is None
    assert result[2] is None


# ============================================================
# TREND
# ============================================================

def test_trend_requires_ema20():
    result = trend_from_emas(
        100.0,
        None,
        90.0,
        80.0,
    )

    assert result == "INSUFFICIENT_DATA"


def test_trend_requires_ema50():
    result = trend_from_emas(
        100.0,
        95.0,
        None,
        80.0,
    )

    assert result == "INSUFFICIENT_DATA"


def test_trend_detects_bullish():
    result = trend_from_emas(
        120.0,
        110.0,
        100.0,
        90.0,
    )

    assert result == "BULLISH"


def test_trend_detects_bearish():
    result = trend_from_emas(
        80.0,
        90.0,
        100.0,
        110.0,
    )

    assert result == "BEARISH"


def test_trend_detects_bullish_weak():
    result = trend_from_emas(
        120.0,
        110.0,
        100.0,
        None,
    )

    assert result == "BULLISH_WEAK"


def test_trend_detects_bearish_weak():
    result = trend_from_emas(
        80.0,
        90.0,
        100.0,
        None,
    )

    assert result == "BEARISH_WEAK"


def test_trend_detects_neutral_bullish():
    result = trend_from_emas(
        105.0,
        110.0,
        100.0,
        90.0,
    )

    assert result == "NEUTRAL_BULLISH"


def test_trend_detects_neutral_bearish():
    result = trend_from_emas(
        95.0,
        90.0,
        100.0,
        110.0,
    )

    assert result == "NEUTRAL_BEARISH"


def test_trend_rejects_nan_price():
    with pytest.raises(ValueError):
        trend_from_emas(
            float("nan"),
            100.0,
            90.0,
            80.0,
        )


# ============================================================
# LATEST VALUE
# ============================================================

def test_latest_value_returns_last_value():
    result = latest_value(
        [None, 10.0, 20.0]
    )

    assert result == pytest.approx(20.0)


def test_latest_value_ignores_trailing_none():
    result = latest_value(
        [10.0, 20.0, None, None]
    )

    assert result == pytest.approx(20.0)


def test_latest_value_returns_none_if_empty():
    result = latest_value([])

    assert result is None


def test_latest_value_returns_none_if_all_none():
    result = latest_value(
        [None, None, None]
    )

    assert result is None


# ============================================================
# COMPUTE INDICATORS
# ============================================================

def test_compute_indicators_returns_expected_keys():
    data = rising_candles(250)

    result = compute_indicators(data)

    expected = {
        "price",
        "ema20",
        "ema50",
        "ema200",
        "rsi14",
        "atr14",
        "atr_percent",
        "volatility20",
        "momentum10",
        "relative_volume20",
        "trend",
        "candles_count",
        "last_candle_timestamp",
        "last_candle_closed",
    }

    assert expected.issubset(result.keys())


def test_compute_indicators_price_is_last_close():
    data = rising_candles(250)

    result = compute_indicators(data)

    assert result["price"] == pytest.approx(
        data[-1].close
    )


def test_compute_indicators_count_is_correct():
    data = rising_candles(250)

    result = compute_indicators(data)

    assert result["candles_count"] == 250


def test_compute_indicators_has_ema200():
    data = rising_candles(250)

    result = compute_indicators(data)

    assert result["ema200"] is not None


def test_compute_indicators_has_rsi():
    data = rising_candles(50)

    result = compute_indicators(data)

    assert result["rsi14"] is not None


def test_compute_indicators_has_atr():
    data = rising_candles(50)

    result = compute_indicators(data)

    assert result["atr14"] is not None


def test_compute_indicators_has_relative_volume():
    data = rising_candles(50)

    result = compute_indicators(data)

    assert result["relative_volume20"] is not None


def test_compute_indicators_detects_bullish_trend():
    data = rising_candles(250)

    result = compute_indicators(data)

    assert result["trend"] == "BULLISH"


def test_compute_indicators_detects_open_candle():
    data = rising_candles(250)

    data[-1] = candle(
        timestamp=data[-1].timestamp,
        open_price=data[-1].open,
        high=data[-1].high,
        low=data[-1].low,
        close=data[-1].close,
        volume=data[-1].volume,
        closed=False,
    )

    result = compute_indicators(data)

    assert result["last_candle_closed"] is False


# ============================================================
# SNAPSHOT
# ============================================================

def test_indicator_snapshot_matches_compute():
    data = rising_candles(250)

    first = compute_indicators(data)
    second = indicator_snapshot(data)

    assert second == first