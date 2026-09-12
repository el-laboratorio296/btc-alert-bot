from __future__ import annotations

import pytest

from radar.models import Candle
from radar.structure import (
    StructureError,
    analyze_structure,
    classify_highs,
    classify_lows,
    detect_breakout,
    find_swing_highs,
    find_swing_lows,
    market_structure,
    structure_confidence,
    structure_levels,
)


def make_candle(
    index: int,
    high: float,
    low: float,
    close: float | None = None,
    is_closed: bool = True,
) -> Candle:
    if close is None:
        close = (high + low) / 2.0

    return Candle(
        timestamp=index,
        open=close,
        high=high,
        low=low,
        close=close,
        volume=100.0,
        is_closed=is_closed,
    )


def test_swing_high_requires_confirmation_window():
    candles = [
        make_candle(0, 10, 8),
        make_candle(1, 12, 9),
        make_candle(2, 20, 10),
        make_candle(3, 13, 9),
        make_candle(4, 11, 8),
    ]

    swings = find_swing_highs(
        candles,
        window=2,
    )

    assert len(swings) == 1
    assert swings[0].index == 2
    assert swings[0].price == 20.0


def test_swing_low_requires_confirmation_window():
    candles = [
        make_candle(0, 12, 10),
        make_candle(1, 13, 9),
        make_candle(2, 15, 5),
        make_candle(3, 14, 8),
        make_candle(4, 13, 9),
    ]

    swings = find_swing_lows(
        candles,
        window=2,
    )

    assert len(swings) == 1
    assert swings[0].index == 2
    assert swings[0].price == 5.0


def test_classify_highs():
    swings = [
        make_swing_high(100.0),
        make_swing_high(110.0),
        make_swing_high(105.0),
    ]

    result = classify_highs(swings)

    assert result == [
        None,
        "HH",
        "LH",
    ]


def test_classify_lows():
    swings = [
        make_swing_low(100.0),
        make_swing_low(110.0),
        make_swing_low(105.0),
    ]

    result = classify_lows(swings)

    assert result == [
        None,
        "HL",
        "LL",
    ]


def test_market_structure_bullish():
    highs = [
        make_swing_high(100.0),
        make_swing_high(120.0),
    ]

    lows = [
        make_swing_low(80.0),
        make_swing_low(100.0),
    ]

    assert (
        market_structure(highs, lows)
        == "BULLISH"
    )


def test_market_structure_bearish():
    highs = [
        make_swing_high(120.0),
        make_swing_high(100.0),
    ]

    lows = [
        make_swing_low(100.0),
        make_swing_low(80.0),
    ]

    assert (
        market_structure(highs, lows)
        == "BEARISH"
    )


def test_market_structure_requires_enough_swings():
    assert (
        market_structure([], [])
        == "INSUFFICIENT_DATA"
    )


def test_structure_levels():
    highs = [
        make_swing_high(100.0),
        make_swing_high(120.0),
    ]

    lows = [
        make_swing_low(80.0),
        make_swing_low(90.0),
    ]

    levels = structure_levels(
        highs,
        lows,
    )

    assert levels.resistance == 120.0
    assert levels.previous_resistance == 100.0
    assert levels.support == 90.0
    assert levels.previous_support == 80.0


def test_detect_confirmed_breakout():
    result = detect_breakout(
        price=121.0,
        support=90.0,
        resistance=120.0,
        candle_closed=True,
    )

    assert result == "BREAKOUT"


def test_open_candle_is_not_confirmed_breakout():
    result = detect_breakout(
        price=121.0,
        support=90.0,
        resistance=120.0,
        candle_closed=False,
    )

    assert result == "POTENTIAL_BREAKOUT"


def test_detect_confirmed_breakdown():
    result = detect_breakout(
        price=79.0,
        support=80.0,
        resistance=120.0,
        candle_closed=True,
    )

    assert result == "BREAKDOWN"


def test_open_candle_is_potential_breakdown():
    result = detect_breakout(
        price=79.0,
        support=80.0,
        resistance=120.0,
        candle_closed=False,
    )

    assert result == "POTENTIAL_BREAKDOWN"


def test_invalid_levels_are_rejected():
    with pytest.raises(StructureError):
        detect_breakout(
            price=100.0,
            support=120.0,
            resistance=110.0,
        )


def test_structure_confidence_is_bounded():
    score = structure_confidence(
        state="BULLISH",
        swing_high_count=4,
        swing_low_count=4,
        candle_closed=True,
    )

    assert 0.0 <= score <= 100.0


def test_analyze_structure_returns_complete_result():
    candles = [
        make_candle(0, 10, 8),
        make_candle(1, 12, 7),
        make_candle(2, 20, 10),
        make_candle(3, 13, 8),
        make_candle(4, 11, 7),
        make_candle(5, 18, 9),
        make_candle(6, 15, 10),
    ]

    result = analyze_structure(
        candles,
        window=2,
    )

    assert result.price == candles[-1].close
    assert result.breakout in {
        "NONE",
        "BREAKOUT",
        "BREAKDOWN",
        "POTENTIAL_BREAKOUT",
        "POTENTIAL_BREAKDOWN",
    }
    assert 0.0 <= result.confidence <= 100.0


def make_swing_high(price: float):
    from radar.structure import SwingPoint

    return SwingPoint(
        index=0,
        timestamp=0,
        price=price,
        kind="SWING_HIGH",
    )


def make_swing_low(price: float):
    from radar.structure import SwingPoint

    return SwingPoint(
        index=0,
        timestamp=0,
        price=price,
        kind="SWING_LOW",
    )