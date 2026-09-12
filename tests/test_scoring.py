from __future__ import annotations

import pytest

from radar.scoring import (
    ScoringError,
    calculate_technical_score,
    score_momentum,
    score_momentum_component,
    score_rsi,
    score_structure,
    score_trend,
    score_volatility,
    score_volume,
)


# ============================================================
# DATOS DE PRUEBA
# ============================================================

def bullish_indicators() -> dict:
    return {
        "price": 100.0,
        "ema20": 98.0,
        "ema50": 95.0,
        "ema200": 90.0,
        "rsi14": 62.0,
        "atr14": 1.5,
        "atr_percent": 1.5,
        "volatility20": 1.8,
        "momentum10": 3.0,
        "relative_volume20": 1.5,
        "trend": "BULLISH",
        "last_candle_closed": True,
    }


def bearish_indicators() -> dict:
    return {
        "price": 90.0,
        "ema20": 95.0,
        "ema50": 100.0,
        "ema200": 105.0,
        "rsi14": 38.0,
        "atr14": 2.0,
        "atr_percent": 2.2,
        "volatility20": 2.5,
        "momentum10": -3.0,
        "relative_volume20": 1.5,
        "trend": "BEARISH",
        "last_candle_closed": True,
    }


# ============================================================
# VALIDACIÓN GENERAL
# ============================================================

def test_scoring_error_is_exception():
    assert issubclass(
        ScoringError,
        Exception,
    )


# ============================================================
# TREND
# ============================================================

def test_score_trend_bullish_is_high():
    assert score_trend("BULLISH") == 90.0


def test_score_trend_bearish_is_low():
    assert score_trend("BEARISH") == 10.0


def test_score_trend_neutral_is_50():
    assert score_trend("NEUTRAL") == 50.0


def test_score_trend_is_case_insensitive():
    assert score_trend("bullish") == 90.0


def test_score_trend_unknown_is_neutral():
    assert score_trend("UNKNOWN") == 50.0


# ============================================================
# RSI
# ============================================================

def test_rsi_none_is_neutral():
    assert score_rsi(None) == 50.0


def test_rsi_normal_zone_is_near_neutral():
    result = score_rsi(50.0)

    assert 45.0 <= result <= 55.0


def test_rsi_extreme_high_is_not_buy_signal():
    result = score_rsi(90.0)

    assert result < 50.0


def test_rsi_extreme_low_is_not_automatic_buy_signal():
    result = score_rsi(15.0)

    assert result < 50.0


def test_rsi_score_is_bounded():
    for value in (
        0.0,
        10.0,
        25.0,
        50.0,
        75.0,
        100.0,
    ):
        result = score_rsi(value)

        assert 0.0 <= result <= 100.0


# ============================================================
# MOMENTUM
# ============================================================

def test_momentum_zero_is_50():
    assert score_momentum(0.0) == 50.0


def test_momentum_positive_is_bullish():
    assert score_momentum(3.0) > 50.0


def test_momentum_negative_is_bearish():
    assert score_momentum(-3.0) < 50.0


def test_momentum_none_is_neutral():
    assert score_momentum(None) == 50.0


def test_momentum_is_bounded():
    assert score_momentum(1000.0) == 100.0
    assert score_momentum(-1000.0) == 0.0


def test_momentum_component_is_bounded():
    result = score_momentum_component(
        rsi_value=60.0,
        momentum_value=3.0,
    )

    assert 0.0 <= result <= 100.0


# ============================================================
# VOLUMEN
# ============================================================

def test_volume_none_is_neutral():
    assert score_volume(None) == 50.0


def test_low_volume_has_weak_confirmation():
    result = score_volume(0.5)

    assert result < 50.0


def test_high_volume_bullish_candle_is_positive():
    result = score_volume(
        2.0,
        "BULLISH",
    )

    assert result > 60.0


def test_high_volume_bearish_candle_is_penalized():
    result = score_volume(
        2.0,
        "BEARISH",
    )

    assert result < 70.0


def test_volume_score_is_bounded():
    for value in (
        0.0,
        0.5,
        1.0,
        2.0,
        10.0,
        100.0,
    ):
        result = score_volume(value)

        assert 0.0 <= result <= 100.0


# ============================================================
# ESTRUCTURA
# ============================================================

def test_empty_structure_is_neutral():
    assert score_structure({}) == 50.0


def test_bullish_structure_scores_higher():
    result = score_structure(
        {
            "trend": "BULLISH",
        }
    )

    assert result > 50.0


def test_bearish_structure_scores_lower():
    result = score_structure(
        {
            "trend": "BEARISH",
        }
    )

    assert result < 50.0


def test_confirmed_breakout_improves_structure():
    result = score_structure(
        {
            "confirmed_breakout": True,
        }
    )

    assert result > 50.0


def test_confirmed_breakdown_reduces_structure():
    result = score_structure(
        {
            "confirmed_breakdown": True,
        }
    )

    assert result < 50.0


def test_potential_breakout_is_weaker_than_confirmed():
    potential = score_structure(
        {
            "potential_breakout": True,
        }
    )

    confirmed = score_structure(
        {
            "confirmed_breakout": True,
        }
    )

    assert confirmed > potential


def test_structure_score_is_bounded():
    result = score_structure(
        {
            "trend": "BULLISH",
            "bias": "BULLISH",
            "confirmed_breakout": True,
            "potential_breakout": True,
        }
    )

    assert 0.0 <= result <= 100.0


# ============================================================
# VOLATILIDAD
# ============================================================

def test_volatility_without_data_is_neutral():
    assert score_volatility(
        None,
        None,
    ) == 50.0


def test_reasonable_volatility_has_positive_quality():
    result = score_volatility(
        atr_percent=1.5,
        volatility_percent=1.5,
    )

    assert result > 50.0


def test_extreme_volatility_is_penalized():
    result = score_volatility(
        atr_percent=10.0,
        volatility_percent=10.0,
    )

    assert result < 50.0


def test_volatility_score_is_bounded():
    for value in (
        0.0,
        1.0,
        2.0,
        5.0,
        10.0,
        100.0,
    ):
        result = score_volatility(
            atr_percent=value,
            volatility_percent=value,
        )

        assert 0.0 <= result <= 100.0


# ============================================================
# SCORE TÉCNICO
# ============================================================

def test_bullish_market_produces_bullish_bias():
    result = calculate_technical_score(
        bullish_indicators()
    )

    assert result["technical_score"] > 50.0
    assert result["bias"] == "BULLISH"


def test_bearish_market_produces_bearish_bias():
    result = calculate_technical_score(
        bearish_indicators()
    )

    assert result["technical_score"] < 50.0
    assert result["bias"] == "BEARISH"


def test_technical_score_is_bounded():
    for indicators in (
        bullish_indicators(),
        bearish_indicators(),
        {},
    ):
        result = calculate_technical_score(
            indicators
        )

        assert 0.0 <= result["technical_score"] <= 100.0


def test_confidence_is_bounded():
    result = calculate_technical_score(
        bullish_indicators()
    )

    assert 0.0 <= result["confidence"] <= 100.0


def test_complete_closed_data_has_high_confidence():
    result = calculate_technical_score(
        bullish_indicators()
    )

    assert result["confidence"] >= 70.0


def test_open_candle_reduces_confidence():
    indicators = bullish_indicators()

    indicators["last_candle_closed"] = False

    result = calculate_technical_score(
        indicators
    )

    closed_result = calculate_technical_score(
        bullish_indicators()
    )

    assert result["confidence"] < closed_result["confidence"]


def test_missing_data_reduces_confidence():
    complete = calculate_technical_score(
        bullish_indicators()
    )

    incomplete = bullish_indicators()

    incomplete["rsi14"] = None
    incomplete["atr14"] = None
    incomplete["momentum10"] = None
    incomplete["relative_volume20"] = None

    result = calculate_technical_score(
        incomplete
    )

    assert result["confidence"] < complete["confidence"]


def test_components_exist():
    result = calculate_technical_score(
        bullish_indicators()
    )

    components = result["components"]

    assert "trend" in components
    assert "momentum" in components
    assert "structure" in components
    assert "volume" in components
    assert "volatility" in components


def test_component_scores_are_bounded():
    result = calculate_technical_score(
        bullish_indicators()
    )

    for value in result["components"].values():
        assert 0.0 <= value <= 100.0


def test_confirmed_bullish_structure_improves_score():
    indicators = bullish_indicators()

    without_structure = calculate_technical_score(
        indicators
    )

    with_structure = calculate_technical_score(
        indicators,
        {
            "trend": "BULLISH",
            "confirmed_breakout": True,
        },
    )

    assert (
        with_structure["technical_score"]
        > without_structure["technical_score"]
    )


def test_confirmed_bearish_structure_reduces_score():
    indicators = bullish_indicators()

    without_structure = calculate_technical_score(
        indicators
    )

    with_structure = calculate_technical_score(
        indicators,
        {
            "trend": "BEARISH",
            "confirmed_breakdown": True,
        },
    )

    assert (
        with_structure["technical_score"]
        < without_structure["technical_score"]
    )


def test_alias_matches_main_function():
    from radar.scoring import score_indicators

    indicators = bullish_indicators()

    first = calculate_technical_score(
        indicators
    )

    second = score_indicators(
        indicators
    )

    assert first == second


def test_score_contains_required_public_fields():
    result = calculate_technical_score(
        bullish_indicators()
    )

    required = {
        "technical_score",
        "trend_score",
        "momentum_score",
        "structure_score",
        "volume_score",
        "volatility_score",
        "confidence",
        "data_completeness",
        "directional_consistency",
        "bias",
        "signal",
        "quality",
        "components",
    }

    assert required.issubset(
        result.keys()
    )


def test_invalid_indicators_type_is_rejected():
    with pytest.raises(TypeError):
        calculate_technical_score([])


def test_invalid_structure_type_is_rejected():
    with pytest.raises(TypeError):
        calculate_technical_score(
            bullish_indicators(),
            [],
        )


# ============================================================
# PRINCIPIO CRÍTICO DEL RADAR
# ============================================================

def test_oversold_does_not_create_automatic_bullish_signal():
    indicators = bullish_indicators()

    indicators["rsi14"] = 18.0
    indicators["momentum10"] = -4.0
    indicators["trend"] = "BEARISH"

    result = calculate_technical_score(
        indicators
    )

    assert result["bias"] != "BULLISH"


def test_extreme_volatility_cannot_create_bullish_signal():
    indicators = bullish_indicators()

    indicators["atr_percent"] = 12.0
    indicators["volatility20"] = 12.0

    result = calculate_technical_score(
        indicators
    )

    assert result["volatility_score"] < 50.0


def test_bearish_high_volume_is_not_treated_as_bullish():
    indicators = bearish_indicators()

    indicators["relative_volume20"] = 3.0

    result = calculate_technical_score(
        indicators
    )

    assert result["volume_score"] < 70.0