import pytest

from radar.decision import (
    DECISION_AVOID,
    DECISION_BUY,
    DECISION_WAIT,
    REGIME_HIGH_RISK,
    REGIME_RISK_OFF,
    REGIME_RISK_ON,
    build_decision,
    calculate_confirmation_score,
    calculate_timeframe_alignment,
    calculate_trend_quality,
    decision_engine,
    determine_market_regime,
)


def base_scoring():
    return {
        "technical_score": 75.0,
        "confidence": 85.0,
        "bias": "BULLISH",
        "volatility_score": 60.0,
    }


def base_strategy():
    return {
        "decision": DECISION_BUY,
        "bias": "BULLISH",
        "confidence": 85.0,
        "confirmations": (
            "Ruptura estructural confirmada",
        ),
        "blockers": (),
    }


def base_risk():
    return {
        "valid": True,
        "risk_reward_tp2": 2.0,
        "warnings": (),
    }


def bullish_timeframes():
    return {
        "1d": {
            "bias": "BULLISH",
            "last_candle_closed": True,
        },
        "4h": {
            "bias": "BULLISH",
            "last_candle_closed": True,
        },
        "1h": {
            "bias": "BULLISH",
            "last_candle_closed": True,
        },
        "15m": {
            "bias": "BULLISH",
            "last_candle_closed": True,
        },
    }


def bearish_timeframes():
    return {
        "1d": {
            "bias": "BEARISH",
            "last_candle_closed": True,
        },
        "4h": {
            "bias": "BEARISH",
            "last_candle_closed": True,
        },
        "1h": {
            "bias": "BEARISH",
            "last_candle_closed": True,
        },
        "15m": {
            "bias": "BEARISH",
            "last_candle_closed": True,
        },
    }


def test_bullish_timeframes_have_high_alignment():
    result = calculate_timeframe_alignment(
        bullish_timeframes()
    )

    assert result >= 90.0


def test_bearish_timeframes_have_low_alignment():
    result = calculate_timeframe_alignment(
        bearish_timeframes()
    )

    assert result <= 10.0


def test_mixed_timeframes_are_not_fully_aligned():
    timeframes = bullish_timeframes()

    timeframes["15m"] = {
        "bias": "BEARISH",
        "last_candle_closed": True,
    }

    result = calculate_timeframe_alignment(
        timeframes
    )

    assert 30.0 < result < 90.0


def test_trend_quality_is_high_when_all_agree():
    result = calculate_trend_quality(
        bullish_timeframes()
    )

    assert result == pytest.approx(100.0)


def test_trend_quality_is_partial_when_timeframes_conflict():
    timeframes = bullish_timeframes()

    timeframes["1h"] = {
        "bias": "BEARISH",
    }

    result = calculate_trend_quality(
        timeframes
    )

    assert result == pytest.approx(75.0)


def test_risk_on_regime():
    result = determine_market_regime(
        technical_score=80.0,
        confidence=85.0,
        trend_quality=90.0,
        volatility_score=70.0,
    )

    assert result == REGIME_RISK_ON


def test_risk_off_regime():
    result = determine_market_regime(
        technical_score=25.0,
        confidence=70.0,
        trend_quality=40.0,
        volatility_score=50.0,
    )

    assert result == REGIME_RISK_OFF


def test_high_risk_regime():
    result = determine_market_regime(
        technical_score=50.0,
        confidence=40.0,
        trend_quality=50.0,
        volatility_score=20.0,
    )

    assert result == REGIME_HIGH_RISK


def test_confirmation_score_buy_is_positive():
    result = calculate_confirmation_score(
        strategy=base_strategy(),
        risk=base_risk(),
    )

    assert result > 70.0


def test_confirmation_score_wait_is_lower():
    result = calculate_confirmation_score(
        strategy={
            "decision": DECISION_WAIT,
            "confirmations": (),
            "blockers": (
                "Falta confirmación",
            ),
        },
        risk={
            "valid": False,
        },
    )

    assert result < 50.0


def test_buy_with_aligned_market_is_preserved():
    result = build_decision(
        scoring=base_scoring(),
        strategy=base_strategy(),
        risk=base_risk(),
        timeframes=bullish_timeframes(),
    )

    assert result["decision"] == DECISION_BUY
    assert result["bias"] == "BULLISH"
    assert result["risk_level"] == "LOW"
    assert result["timeframe_alignment"] >= 90.0


def test_buy_with_poor_alignment_waits():
    result = build_decision(
        scoring=base_scoring(),
        strategy=base_strategy(),
        risk=base_risk(),
        timeframes=bearish_timeframes(),
    )

    assert result["decision"] == DECISION_WAIT


def test_buy_with_bad_rr_waits():
    result = build_decision(
        scoring=base_scoring(),
        strategy=base_strategy(),
        risk={
            "valid": True,
            "risk_reward_tp2": 1.1,
            "warnings": (),
        },
        timeframes=bullish_timeframes(),
    )

    assert result["decision"] == DECISION_WAIT


def test_buy_with_extreme_risk_is_avoided():
    result = build_decision(
        scoring={
            "technical_score": 75.0,
            "confidence": 85.0,
            "bias": "BULLISH",
            "volatility_score": 15.0,
        },
        strategy=base_strategy(),
        risk=base_risk(),
        timeframes=bullish_timeframes(),
    )

    assert result["decision"] == DECISION_AVOID


def test_open_candle_blocks_buy():
    timeframes = bullish_timeframes()

    timeframes["15m"] = {
        "bias": "BULLISH",
        "last_candle_closed": False,
    }

    result = build_decision(
        scoring=base_scoring(),
        strategy=base_strategy(),
        risk=base_risk(),
        timeframes=timeframes,
    )

    assert result["decision"] == DECISION_WAIT


def test_strategy_avoid_remains_avoid():
    result = build_decision(
        scoring=base_scoring(),
        strategy={
            "decision": DECISION_AVOID,
            "bias": "BEARISH",
            "confidence": 90.0,
            "confirmations": (),
            "blockers": (
                "Breakdown confirmado",
            ),
        },
        risk={
            "valid": False,
            "warnings": (
                "No crear posición.",
            ),
        },
        timeframes=bullish_timeframes(),
    )

    assert result["decision"] == DECISION_AVOID


def test_result_contains_explanations():
    result = build_decision(
        scoring=base_scoring(),
        strategy=base_strategy(),
        risk=base_risk(),
        timeframes=bullish_timeframes(),
    )

    assert result["reason"]
    assert isinstance(
        result["confirmations"],
        tuple,
    )
    assert isinstance(
        result["blockers"],
        tuple,
    )
    assert isinstance(
        result["warnings"],
        tuple,
    )


def test_confidence_is_bounded():
    result = build_decision(
        scoring=base_scoring(),
        strategy=base_strategy(),
        risk=base_risk(),
        timeframes=bullish_timeframes(),
    )

    assert 0.0 <= result["confidence"] <= 100.0


def test_decision_engine_alias_works():
    result = decision_engine(
        scoring=base_scoring(),
        strategy=base_strategy(),
        risk=base_risk(),
        timeframes=bullish_timeframes(),
    )

    assert result["decision"] == DECISION_BUY


def test_invalid_scoring_raises():
    with pytest.raises(TypeError):
        build_decision(
            scoring=None,
            strategy=base_strategy(),
        )


def test_invalid_strategy_raises():
    with pytest.raises(TypeError):
        build_decision(
            scoring=base_scoring(),
            strategy=None,
        )


def test_invalid_timeframes_raise():
    with pytest.raises(TypeError):
        calculate_timeframe_alignment(
            None
        )