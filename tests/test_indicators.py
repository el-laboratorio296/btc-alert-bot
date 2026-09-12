from __future__ import annotations

from radar.indicators import (
    atr,
    compute_indicators,
    ema,
    momentum,
    relative_volume,
    rsi,
    true_range,
    trend_from_emas,
    volatility,
)
from radar.models import Candle


def make_candles(count: int = 220) -> list[Candle]:
    candles: list[Candle] = []

    price = 100.0

    for index in range(count):
        open_price = price

        close_price = (
            price + 1.0
            if index % 2 == 0
            else price + 0.5
        )

        high_price = close_price + 1.0
        low_price = open_price - 1.0

        candles.append(
            Candle(
                timestamp=index * 60_000,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=1000.0 + index,
                is_closed=True,
            )
        )

        price = close_price

    return candles


def test_ema_returns_same_length():
    values = list(range(1, 31))

    result = ema(values, 10)

    assert len(result) == len(values)
    assert result[8] is None
    assert result[9] is not None


def test_rsi_returns_same_length():
    values = [
        100.0 + index
        for index in range(30)
    ]

    result = rsi(values, 14)

    assert len(result) == len(values)
    assert result[13] is None
    assert result[14] is not None
    assert result[-1] == 100.0


def test_true_range():
    candles = [
        Candle(
            timestamp=1,
            open=100,
            high=105,
            low=98,
            close=103,
            volume=100,
        ),
        Candle(
            timestamp=2,
            open=103,
            high=110,
            low=101,
            close=108,
            volume=120,
        ),
    ]

    result = true_range(candles)

    assert result[0] == 7.0
    assert result[1] == 9.0


def test_atr_returns_values():
    candles = make_candles(30)

    result = atr(candles, 14)

    assert len(result) == 30
    assert result[12] is None
    assert result[13] is not None
    assert result[-1] is not None


def test_momentum():
    values = [
        100.0,
        110.0,
        120.0,
        130.0,
    ]

    result = momentum(values, 2)

    assert result[0] is None
    assert result[1] is None
    assert result[2] == 20.0
    assert result[3] == (
        (130.0 / 110.0) - 1.0
    ) * 100.0


def test_volatility():
    values = [
        100.0,
        101.0,
        100.0,
        101.0,
        100.0,
        101.0,
        100.0,
    ]

    result = volatility(values, 3)

    assert len(result) == len(values)
    assert result[0] is None
    assert result[-1] is not None
    assert result[-1] >= 0.0


def test_relative_volume():
    candles = []

    for index in range(25):
        volume = 100.0

        if index == 24:
            volume = 200.0

        candles.append(
            Candle(
                timestamp=index,
                open=100,
                high=101,
                low=99,
                close=100,
                volume=volume,
            )
        )

    result = relative_volume(
        candles,
        20,
    )

    assert result[-1] == 2.0


def test_trend_bullish():
    result = trend_from_emas(
        price=110.0,
        ema20=108.0,
        ema50=105.0,
        ema200=100.0,
    )

    assert result == "BULLISH"


def test_trend_bearish():
    result = trend_from_emas(
        price=90.0,
        ema20=92.0,
        ema50=95.0,
        ema200=100.0,
    )

    assert result == "BEARISH"


def test_compute_indicators():
    candles = make_candles(220)

    result = compute_indicators(candles)

    assert result["price"] > 0

    assert result["ema20"] is not None
    assert result["ema50"] is not None
    assert result["ema200"] is not None

    assert result["rsi14"] is not None
    assert result["atr14"] is not None

    assert result["volatility20"] is not None
    assert result["momentum10"] is not None

    assert result["relative_volume20"] is not None

    assert result["candles_count"] == 220
    assert result["last_candle_closed"] is True


def test_compute_indicators_requires_valid_candles():
    try:
        compute_indicators([])
    except Exception:
        return

    raise AssertionError(
        "compute_indicators debería rechazar "
        "una lista vacía."
    )