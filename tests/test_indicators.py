
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


def make_candle(
    timestamp: int,
    open_price: float,
    high: float,
    low: float,
    close: float,
    volume: float = 1000.0,
    is_closed: bool = True,
) -> Candle:
    return Candle(
        timestamp=timestamp,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
        is_closed=is_closed,
    )


def make_candles(
    closes: list[float],
    volume: float = 1000.0,
) -> list[Candle]:
    candles: list[Candle] = []

    for index, close in enumerate(closes):
        candles.append(
            make_candle(
                timestamp=index * 60_000,
                open_price=close,
                high=close + 1.0,
                low=close - 1.0,
                close=close,
                volume=volume,
            )
        )

    return candles


def make_rising_candles(
    count: int,
) -> list[Candle]:
    return make_candles(
        [
            100.0 + float(index)
            for index in range(count)
        ]
    )


# ============================================================
# VALIDATION
# ============================================================


def test_indicator_error_is_exception():
    assert issubclass(
        IndicatorError,
        Exception,
    )


def test_ema_rejects_invalid_period():
    with pytest.raises(ValueError):
        ema(
            [1.0, 2.0, 3.0],
            0,
        )


def test_ema_rejects_non_integer_period():
    with pytest.raises(ValueError):
        ema(
            [1.0, 2.0, 3.0],
            2.5,
        )


def test_ema_rejects_empty_values():
    with pytest.raises(ValueError):
        ema(
            [],
            2,
        )


def test_rsi_rejects_invalid_period():
    with pytest.raises(ValueError):
        rsi(
            [1.0, 2.0, 3.0],
            0,
        )


def test_momentum_rejects_invalid_period():
    with pytest.raises(ValueError):
        momentum(
            [1.0, 2.0, 3.0],
            0,
        )


def test_volatility_rejects_invalid_period():
    with pytest.raises(ValueError):
        volatility(
            [1.0, 2.0, 3.0],
            0,
        )


def test_true_range_rejects_empty_candles():
    with pytest.raises(IndicatorError):
        true_range([])


def test_atr_rejects_insufficient_candles():
    candles = make_rising_candles(5)

    with pytest.raises(IndicatorError):
        atr(
            candles,
            period=14,
        )


# ============================================================
# EMA
# ============================================================


def test_ema_returns_same_length():
    values = [
        100.0,
        110.0,
        120.0,
        130.0,
        140.0,
    ]

    result = ema(
        values,
        period=3,
    )

    assert len(result) == len(values)


def test_ema_first_value_is_sma():
    values = [
        100.0,
        110.0,
        120.0,
    ]

    result = ema(
        values,
        period=3,
    )

    assert result[0] is None
    assert result[1] is None
    assert result[2] == pytest.approx(
        110.0
    )


def test_ema_calculates_next_value():
    values = [
        100.0,
        110.0,
        120.0,
        130.0,
    ]

    result = ema(
        values,
        period=3,
    )

    assert result[2] == pytest.approx(
        110.0
    )

    assert result[3] == pytest.approx(
        120.0
    )


def test_ema_returns_none_when_not_enough_data():
    values = [
        100.0,
        110.0,
    ]

    result = ema(
        values,
        period=3,
    )

    assert result == [
        None,
        None,
    ]


# ============================================================
# RSI
# ============================================================


def test_rsi_returns_none_before_period():
    values = [
        100.0,
        101.0,
        102.0,
        103.0,
        104.0,
    ]

    result = rsi(
        values,
        period=3,
    )

    assert result[0] is None
    assert result[1] is None
    assert result[2] is None
    assert result[3] is not None


def test_rsi_all_gains_returns_100():
    values = [
        100.0,
        101.0,
        102.0,
        103.0,
        104.0,
        105.0,
    ]

    result = rsi(
        values,
        period=3,
    )

    assert result[-1] == pytest.approx(
        100.0
    )


def test_rsi_all_losses_returns_zero():
    values = [
        105.0,
        104.0,
        103.0,
        102.0,
        101.0,
        100.0,
    ]

    result = rsi(
        values,
        period=3,
    )

    assert result[-1] == pytest.approx(
        0.0
    )


def test_rsi_flat_market_returns_50():
    values = [
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
    ]

    result = rsi(
        values,
        period=3,
    )

    assert result[-1] == pytest.approx(
        50.0
    )


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

    result = rsi(
        values,
        period=3,
    )

    valid_values = [
        value
        for value in result
        if value is not None
    ]

    assert valid_values

    for value in valid_values:
        assert 0.0 <= value <= 100.0


# ============================================================
# TRUE RANGE
# ============================================================


def test_true_range_first_candle_uses_high_low():
    candles = [
        make_candle(
            timestamp=1,
            open_price=95.0,
            high=110.0,
            low=90.0,
            close=100.0,
        )
    ]

    result = true_range(
        candles
    )

    assert len(result) == 1
    assert result[0] == pytest.approx(
        20.0
    )


def test_true_range_uses_previous_close():
    candles = [
        make_candle(
            timestamp=1,
            open_price=95.0,
            high=110.0,
            low=90.0,
            close=100.0,
        ),
        make_candle(
            timestamp=2,
            open_price=105.0,
            high=120.0,
            low=105.0,
            close=115.0,
        ),
    ]

    result = true_range(
        candles
    )

    assert result[0] == pytest.approx(
        20.0
    )

    assert result[1] == pytest.approx(
        20.0
    )


def test_true_range_handles_gap_down():
    candles = [
        make_candle(
            timestamp=1,
            open_price=110.0,
            high=115.0,
            low=105.0,
            close=110.0,
        ),
        make_candle(
            timestamp=2,
            open_price=95.0,
            high=100.0,
            low=90.0,
            close=95.0,
        ),
    ]

    result = true_range(
        candles
    )

    assert result[0] == pytest.approx(
        10.0
    )

    assert result[1] == pytest.approx(
        20.0
    )


def test_true_range_returns_one_value_per_candle():
    candles = make_rising_candles(10)

    result = true_range(
        candles
    )

    assert len(result) == 10

    for value in result:
        assert value >= 0.0
        assert math.isfinite(value)


# ============================================================
# ATR
# ============================================================


def test_atr_returns_same_length():
    candles = make_rising_candles(20)

    result = atr(
        candles,
        period=14,
    )

    assert len(result) == 20


def test_atr_initial_value_is_average_true_range():
    candles = make_candles(
        [
            100.0,
            100.0,
            100.0,
            100.0,
            100.0,
        ]
    )

    result = atr(
        candles,
        period=3,
    )

    assert result[0] is None
    assert result[1] is None
    assert result[2] is not None

    assert result[2] == pytest.approx(
        2.0
    )


def test_atr_values_are_non_negative():
    candles = make_rising_candles(30)

    result = atr(
        candles,
        period=14,
    )

    valid_values = [
        value
        for value in result
        if value is not None
    ]

    assert valid_values

    for value in valid_values:
        assert value >= 0.0


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

    result = volatility(
        values,
        period=3,
    )

    assert len(result) == len(values)


def test_volatility_flat_market_is_zero():
    values = [
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
    ]

    result = volatility(
        values,
        period=3,
    )

    valid_values = [
        value
        for value in result
        if value is not None
    ]

    assert valid_values

    for value in valid_values:
        assert value == pytest.approx(
            0.0
        )


def test_volatility_is_non_negative():
    values = [
        100.0,
        102.0,
        99.0,
        105.0,
        101.0,
        108.0,
        103.0,
    ]

    result = volatility(
        values,
        period=3,
    )

    valid_values = [
        value
        for value in result
        if value is not None
    ]

    assert valid_values

    for value in valid_values:
        assert value >= 0.0


# ============================================================
# MOMENTUM
# ============================================================


def test_momentum_returns_none_before_period():
    values = [
        100.0,
        110.0,
        120.0,
       