import pytest

from radar.risk import (
    DECISION_AVOID,
    DECISION_BUY,
    DECISION_WAIT,
    RiskError,
    calculate_position_size,
    calculate_risk_plan,
    calculate_risk_reward,
    calculate_stop,
    calculate_targets,
    risk_plan,
)


def bullish_strategy():
    return {
        "decision": DECISION_BUY,
        "bias": "BULLISH",
        "confidence": 85.0,
    }


def base_indicators():
    return {
        "price": 100.0,
        "atr14": 2.0,
    }


def base_structure():
    return {
        "support": 96.0,
        "resistance": 105.0,
    }


def test_calculate_stop_is_below_price():
    stop = calculate_stop(
        price=100.0,
        atr=2.0,
    )

    assert stop < 100.0
    assert stop > 0.0


def test_support_can_influence_stop():
    stop = calculate_stop(
        price=100.0,
        atr=2.0,
        support=96.0,
    )

    assert stop < 96.0
    assert stop < 100.0


def test_invalid_stop_parameters_raise():
    with pytest.raises(RiskError):
        calculate_stop(
            price=100.0,
            atr=0.0,
        )


def test_targets_are_ordered():
    tp1, tp2, tp3 = calculate_targets(
        entry=100.0,
        risk_per_unit=2.0,
    )

    assert tp1 > 100.0
    assert tp2 > tp1
    assert tp3 > tp2


def test_risk_reward_is_calculated():
    rr = calculate_risk_reward(
        entry=100.0,
        stop=98.0,
        target=104.0,
    )

    assert rr == pytest.approx(2.0)


def test_invalid_risk_reward_raises():
    with pytest.raises(RiskError):
        calculate_risk_reward(
            entry=100.0,
            stop=101.0,
            target=105.0,
        )


def test_position_size_respects_risk():
    size, capital_at_risk = calculate_position_size(
        capital=1000.0,
        risk_percent=1.0,
        entry=100.0,
        stop=98.0,
    )

    assert capital_at_risk == pytest.approx(10.0)
    assert size == pytest.approx(5.0)


def test_wait_does_not_create_position():
    result = calculate_risk_plan(
        strategy={
            "decision": DECISION_WAIT,
            "bias": "BULLISH",
            "confidence": 70.0,
        },
        indicators=base_indicators(),
        structure=base_structure(),
        capital=1000.0,
    )

    assert result["valid"] is False
    assert result["entry_reference"] is None
    assert result["stop"] is None
    assert result["tp1"] is None


def test_avoid_does_not_create_position():
    result = calculate_risk_plan(
        strategy={
            "decision": DECISION_AVOID,
            "bias": "BEARISH",
            "confidence": 90.0,
        },
        indicators=base_indicators(),
        structure=base_structure(),
        capital=1000.0,
    )

    assert result["valid"] is False
    assert result["position_size"] is None


def test_buy_creates_complete_risk_plan():
    result = calculate_risk_plan(
        strategy=bullish_strategy(),
        indicators=base_indicators(),
        structure=base_structure(),
        capital=1000.0,
        risk_percent=1.0,
    )

    assert result["valid"] is True
    assert result["decision"] == DECISION_BUY

    assert result["entry_low"] < result["entry_reference"]
    assert result["entry_high"] > result["entry_reference"]

    assert result["stop"] < result["entry_reference"]
    assert result["invalidation"] == result["stop"]

    assert result["tp1"] > result["entry_reference"]
    assert result["tp2"] > result["tp1"]
    assert result["tp3"] > result["tp2"]

    assert result["risk_per_unit"] > 0

    assert result["risk_reward_tp1"] > 0
    assert result["risk_reward_tp2"] > result["risk_reward_tp1"]
    assert result["risk_reward_tp3"] > result["risk_reward_tp2"]


def test_position_size_is_returned_when_capital_exists():
    result = calculate_risk_plan(
        strategy=bullish_strategy(),
        indicators=base_indicators(),
        structure=base_structure(),
        capital=1000.0,
        risk_percent=1.0,
    )

    assert result["position_size"] is not None
    assert result["capital_at_risk"] == pytest.approx(10.0)
    assert result["risk_percent"] == pytest.approx(1.0)


def test_without_capital_no_position_size():
    result = calculate_risk_plan(
        strategy=bullish_strategy(),
        indicators=base_indicators(),
        structure=base_structure(),
    )

    assert result["valid"] is True
    assert result["position_size"] is None
    assert result["capital_at_risk"] is None


def test_speculative_trade_is_flagged():
    result = calculate_risk_plan(
        strategy={
            "decision": "SPECULATIVE",
            "bias": "BULLISH",
            "confidence": 60.0,
        },
        indicators=base_indicators(),
        structure=base_structure(),
        capital=1000.0,
    )

    assert result["valid"] is True
    assert any(
        "especulativa" in warning.lower()
        for warning in result["warnings"]
    )


def test_missing_price_raises():
    with pytest.raises(RiskError):
        calculate_risk_plan(
            strategy=bullish_strategy(),
            indicators={
                "atr14": 2.0,
            },
            structure=base_structure(),
        )


def test_missing_atr_raises():
    with pytest.raises(RiskError):
        calculate_risk_plan(
            strategy=bullish_strategy(),
            indicators={
                "price": 100.0,
            },
            structure=base_structure(),
        )


def test_risk_plan_alias_works():
    result = risk_plan(
        strategy=bullish_strategy(),
        indicators=base_indicators(),
        structure=base_structure(),
    )

    assert result["valid"] is True
    assert result["decision"] == DECISION_BUY