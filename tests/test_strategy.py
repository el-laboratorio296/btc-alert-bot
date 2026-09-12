from radar.strategy import (
    DECISION_AVOID,
    DECISION_BUY,
    DECISION_SPECULATIVE,
    DECISION_WAIT,
    evaluate_strategy,
    strategy_score,
)


def base_scoring():
    return {
        "technical_score": 50.0,
        "confidence": 90.0,
        "data_completeness": 100.0,
        "bias": "NEUTRAL",
    }


def bullish_scoring():
    return {
        "technical_score": 78.0,
        "confidence": 85.0,
        "data_completeness": 100.0,
        "bias": "BULLISH",
    }


def bearish_scoring():
    return {
        "technical_score": 25.0,
        "confidence": 90.0,
        "data_completeness": 100.0,
        "bias": "BEARISH",
    }


def test_returns_complete_result():
    result = evaluate_strategy(
        scoring=base_scoring(),
        structure={},
        indicators={},
    )

    assert "decision" in result
    assert "bias" in result
    assert "confidence" in result
    assert "reason" in result
    assert "blockers" in result
    assert "confirmations" in result


def test_strong_bullish_setup_produces_buy():
    result = evaluate_strategy(
        scoring=bullish_scoring(),
        structure={
            "trend": "BULLISH",
            "bias": "BULLISH",
            "confirmed_breakout": True,
        },
        indicators={
            "rsi14": 62.0,
            "momentum10": 3.0,
        },
    )

    assert result["decision"] == DECISION_BUY
    assert result["bias"] == "BULLISH"


def test_confirmed_breakdown_produces_avoid():
    result = evaluate_strategy(
        scoring=bearish_scoring(),
        structure={
            "trend": "BEARISH",
            "bias": "BEARISH",
            "confirmed_breakdown": True,
        },
        indicators={
            "rsi14": 35.0,
            "momentum10": -3.0,
        },
    )

    assert result["decision"] == DECISION_AVOID
    assert result["bias"] == "BEARISH"


def test_oversold_alone_does_not_create_buy():
    result = evaluate_strategy(
        scoring={
            "technical_score": 52.0,
            "confidence": 85.0,
            "data_completeness": 100.0,
            "bias": "NEUTRAL",
        },
        structure={
            "trend": "BEARISH",
            "bias": "BEARISH",
        },
        indicators={
            "rsi14": 24.0,
            "momentum10": -1.0,
        },
    )

    assert result["decision"] != DECISION_BUY


def test_low_data_quality_blocks_entry():
    result = evaluate_strategy(
        scoring={
            "technical_score": 80.0,
            "confidence": 40.0,
            "data_completeness": 50.0,
            "bias": "BULLISH",
        },
        structure={
            "trend": "BULLISH",
            "confirmed_breakout": True,
        },
        indicators={
            "rsi14": 60.0,
            "momentum10": 3.0,
        },
    )

    assert result["decision"] == DECISION_WAIT


def test_potential_breakout_waits_for_confirmation():
    result = evaluate_strategy(
        scoring={
            "technical_score": 65.0,
            "confidence": 75.0,
            "data_completeness": 100.0,
            "bias": "BULLISH",
        },
        structure={
            "trend": "BULLISH",
            "potential_breakout": True,
            "confirmed_breakout": False,
        },
        indicators={
            "rsi14": 61.0,
            "momentum10": 1.5,
        },
    )

    assert result["decision"] == DECISION_WAIT


def test_bearish_conflict_prevents_buy():
    result = evaluate_strategy(
        scoring={
            "technical_score": 72.0,
            "confidence": 85.0,
            "data_completeness": 100.0,
            "bias": "BULLISH",
        },
        structure={
            "trend": "BEARISH",
            "bias": "BEARISH",
            "confirmed_breakout": False,
        },
        indicators={
            "rsi14": 63.0,
            "momentum10": 3.0,
        },
    )

    assert result["decision"] != DECISION_BUY


def test_strong_momentum_can_create_speculative_setup():
    result = evaluate_strategy(
        scoring={
            "technical_score": 58.0,
            "confidence": 65.0,
            "data_completeness": 100.0,
            "bias": "BULLISH",
        },
        structure={
            "trend": "BULLISH",
            "bias": "BULLISH",
        },
        indicators={
            "rsi14": 58.0,
            "momentum10": 3.5,
        },
    )

    assert result["decision"] in {
        DECISION_SPECULATIVE,
        DECISION_BUY,
        DECISION_WAIT,
    }


def test_confidence_is_bounded():
    result = evaluate_strategy(
        scoring={
            "technical_score": 100.0,
            "confidence": 100.0,
            "data_completeness": 100.0,
            "bias": "BULLISH",
        },
        structure={
            "trend": "BULLISH",
            "confirmed_breakout": True,
        },
        indicators={
            "rsi14": 65.0,
            "momentum10": 5.0,
        },
    )

    assert 0.0 <= result["confidence"] <= 100.0


def test_strategy_score_alias_works():
    result = strategy_score(
        scoring=bullish_scoring(),
        structure={
            "trend": "BULLISH",
            "confirmed_breakout": True,
        },
        indicators={
            "rsi14": 60.0,
            "momentum10": 3.0,
        },
    )

    assert result["decision"] == DECISION_BUY