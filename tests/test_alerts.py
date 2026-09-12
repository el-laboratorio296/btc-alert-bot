import math

import pytest

from radar.alerts import (
    ALERT_VERSION,
    DECISION_ACCUMULATE,
    DECISION_AVOID,
    DECISION_BUY,
    DECISION_SPECULATIVE,
    DECISION_WAIT,
    build_alert,
    build_alert_payload,
    format_alert,
)


def base_decision():
    return {
        "decision": DECISION_BUY,
        "bias": "BULLISH",
        "technical_score": 78.0,
        "confidence": 86.0,
        "trend_quality": 90.0,
        "timeframe_alignment": 85.0,
        "confirmation_score": 88.0,
        "market_regime": "RISK_ON",
        "risk_level": "LOW",
        "reason": "Estructura y momentum compatibles.",
        "confirmations": (
            "Ruptura estructural confirmada",
            "Volumen favorable",
        ),
        "blockers": (),
        "warnings": (),
    }


def base_risk():
    return {
        "entry_zone": "$100,000 - $101,000",
        "invalidation": "$98,500",
        "stop": "$98,000",
        "tp1": "$103,000",
        "tp2": "$106,000",
        "tp3": "$110,000",
        "risk_reward_tp2": 2.5,
    }


def base_strategy():
    return {
        "entry_zone": "$100,000 - $101,000",
        "invalidation": "$98,500",
        "stop": "$98,000",
        "tp1": "$103,000",
        "tp2": "$106,000",
        "tp3": "$110,000",
    }


def test_build_alert_payload_returns_complete_payload():
    result = build_alert_payload(
        asset="BTCUSDT",
        price=100500.0,
        decision=base_decision(),
        strategy=base_strategy(),
        risk=base_risk(),
        timeframe="MULTI",
        generated_at="2026-09-12T15:00:00+00:00",
    )

    assert result["alert_version"] == ALERT_VERSION
    assert result["asset"] == "BTCUSDT"
    assert result["price"] == 100500.0
    assert result["decision"] == DECISION_BUY
    assert result["bias"] == "BULLISH"
    assert result["technical_score"] == 78.0
    assert result["confidence"] == 86.0
    assert result["trend_quality"] == 90.0
    assert result["timeframe_alignment"] == 85.0
    assert result["confirmation_score"] == 88.0
    assert result["market_regime"] == "RISK_ON"
    assert result["risk_level"] == "LOW"
    assert result["risk_reward"] == 2.5
    assert result["entry_zone"] == "$100,000 - $101,000"
    assert result["invalidation"] == "$98,500"
    assert result["stop"] == "$98,000"
    assert result["tp1"] == "$103,000"
    assert result["tp2"] == "$106,000"
    assert result["tp3"] == "$110,000"
    assert result["timeframe"] == "MULTI"
    assert result["generated_at"] == (
        "2026-09-12T15:00:00+00:00"
    )


def test_asset_is_normalized_to_uppercase():
    result = build_alert_payload(
        asset="btcusdt",
        price=100000,
        decision=base_decision(),
    )

    assert result["asset"] == "BTCUSDT"


def test_price_must_be_positive():
    with pytest.raises(ValueError):
        build_alert_payload(
            asset="BTCUSDT",
            price=0,
            decision=base_decision(),
        )

    with pytest.raises(ValueError):
        build_alert_payload(
            asset="BTCUSDT",
            price=-100,
            decision=base_decision(),
        )


def test_invalid_price_is_rejected():
    with pytest.raises(ValueError):
        build_alert_payload(
            asset="BTCUSDT",
            price="not-a-number",
            decision=base_decision(),
        )


def test_nan_price_is_rejected():
    with pytest.raises(ValueError):
        build_alert_payload(
            asset="BTCUSDT",
            price=math.nan,
            decision=base_decision(),
        )


def test_infinite_price_is_rejected():
    with pytest.raises(ValueError):
        build_alert_payload(
            asset="BTCUSDT",
            price=math.inf,
            decision=base_decision(),
        )


def test_empty_asset_is_rejected():
    with pytest.raises(ValueError):
        build_alert_payload(
            asset="",
            price=100000,
            decision=base_decision(),
        )


def test_whitespace_asset_is_rejected():
    with pytest.raises(ValueError):
        build_alert_payload(
            asset="   ",
            price=100000,
            decision=base_decision(),
        )


def test_decision_must_be_valid():
    decision = base_decision()
    decision["decision"] = "INVALID"

    with pytest.raises(ValueError):
        build_alert_payload(
            asset="BTCUSDT",
            price=100000,
            decision=decision,
        )


def test_non_mapping_decision_is_rejected():
    with pytest.raises(TypeError):
        build_alert_payload(
            asset="BTCUSDT",
            price=100000,
            decision="BUY",
        )


def test_non_mapping_strategy_is_rejected():
    with pytest.raises(TypeError):
        build_alert_payload(
            asset="BTCUSDT",
            price=100000,
            decision=base_decision(),
            strategy="invalid",
        )


def test_non_mapping_risk_is_rejected():
    with pytest.raises(TypeError):
        build_alert_payload(
            asset="BTCUSDT",
            price=100000,
            decision=base_decision(),
            risk="invalid",
        )


def test_missing_optional_risk_fields_are_allowed():
    result = build_alert_payload(
        asset="BTCUSDT",
        price=100000,
        decision=base_decision(),
    )

    assert result["entry_zone"] is None
    assert result["invalidation"] is None
    assert result["stop"] is None
    assert result["tp1"] is None
    assert result["tp2"] is None
    assert result["tp3"] is None
    assert result["risk_reward"] is None


def test_strategy_can_supply_trade_levels():
    result = build_alert_payload(
        asset="BTCUSDT",
        price=100000,
        decision=base_decision(),
        strategy=base_strategy(),
    )

    assert result["entry_zone"] == "$100,000 - $101,000"
    assert result["invalidation"] == "$98,500"
    assert result["stop"] == "$98,000"
    assert result["tp1"] == "$103,000"
    assert result["tp2"] == "$106,000"
    assert result["tp3"] == "$110,000"


def test_risk_takes_priority_over_strategy():
    strategy = {
        "entry_zone": "STRATEGY ENTRY",
        "stop": "STRATEGY STOP",
    }

    risk = {
        "entry_zone": "RISK ENTRY",
        "stop": "RISK STOP",
    }

    result = build_alert_payload(
        asset="BTCUSDT",
        price=100000,
        decision=base_decision(),
        strategy=strategy,
        risk=risk,
    )

    assert result["entry_zone"] == "RISK ENTRY"
    assert result["stop"] == "RISK STOP"


def test_decision_values_are_normalized():
    decision = base_decision()
    decision["decision"] = "buy"

    result = build_alert_payload(
        asset="BTCUSDT",
        price=100000,
        decision=decision,
    )

    assert result["decision"] == DECISION_BUY


def test_scores_are_clamped():
    decision = base_decision()

    decision["technical_score"] = 150
    decision["confidence"] = -20
    decision["trend_quality"] = 200
    decision["timeframe_alignment"] = -10
    decision["confirmation_score"] = 999

    result = build_alert_payload(
        asset="BTCUSDT",
        price=100000,
        decision=decision,
    )

    assert result["technical_score"] == 100.0
    assert result["confidence"] == 0.0
    assert result["trend_quality"] == 100.0
    assert result["timeframe_alignment"] == 0.0
    assert result["confirmation_score"] == 100.0


def test_invalid_numeric_scores_use_safe_defaults():
    decision = base_decision()

    decision["technical_score"] = "invalid"
    decision["confidence"] = None
    decision["trend_quality"] = "invalid"
    decision["timeframe_alignment"] = None
    decision["confirmation_score"] = "invalid"

    result = build_alert_payload(
        asset="BTCUSDT",
        price=100000,
        decision=decision,
    )

    assert result["technical_score"] == 0.0
    assert result["confidence"] == 0.0
    assert result["trend_quality"] == 50.0
    assert result["timeframe_alignment"] == 50.0
    assert result["confirmation_score"] == 50.0


def test_nan_scores_use_safe_defaults():
    decision = base_decision()

    decision["technical_score"] = math.nan
    decision["confidence"] = math.nan
    decision["trend_quality"] = math.nan

    result = build_alert_payload(
        asset="BTCUSDT",
        price=100000,
        decision=decision,
    )

    assert result["technical_score"] == 0.0
    assert result["confidence"] == 0.0
    assert result["trend_quality"] == 50.0


def test_duplicate_confirmations_are_removed():
    decision = base_decision()

    decision["confirmations"] = (
        "Ruptura",
        "Ruptura",
        "Volumen",
        "Ruptura",
    )

    result = build_alert_payload(
        asset="BTCUSDT",
        price=100000,
        decision=decision,
    )

    assert result["confirmations"] == (
        "Ruptura",
        "Volumen",
    )


def test_empty_confirmation_values_are_removed():
    decision = base_decision()

    decision["confirmations"] = (
        "",
        "   ",
        "Ruptura",
        None,
    )

    result = build_alert_payload(
        asset="BTCUSDT",
        price=100000,
        decision=decision,
    )

    assert result["confirmations"] == (
        "Ruptura",
    )


def test_non_list_confirmations_are_safe():
    decision = base_decision()
    decision["confirmations"] = "invalid"

    result = build_alert_payload(
        asset="BTCUSDT",
        price=100000,
        decision=decision,
    )

    assert result["confirmations"] == ()


def test_non_list_blockers_are_safe():
    decision = base_decision()
    decision["blockers"] = "invalid"

    result = build_alert_payload(
        asset="BTCUSDT",
        price=100000,
        decision=decision,
    )

    assert result["blockers"] == ()


def test_warnings_are_preserved():
    decision = base_decision()

    decision["warnings"] = (
        "Volatilidad elevada",
        "Vela abierta",
    )

    result = build_alert_payload(
        asset="BTCUSDT",
        price=100000,
        decision=decision,
    )

    assert result["warnings"] == (
        "Volatilidad elevada",
        "Vela abierta",
    )


def test_format_alert_contains_core_information():
    payload = build_alert_payload(
        asset="BTCUSDT",
        price=100500,
        decision=base_decision(),
        strategy=base_strategy(),
        risk=base_risk(),
        timeframe="MULTI",
        generated_at="2026-09-12T15:00:00+00:00",
    )

    message = format_alert(payload)

    assert "EL LABORATORIO" in message
    assert "RADAR" in message
    assert "BTCUSDT" in message
    assert "100,500.00" in message
    assert "COMPRA" in message
    assert "78%" in message
    assert "86%" in message
    assert "RISK ON" in message
    assert "BAJO" in message
    assert "PLAN OPERATIVO" in message
    assert "TP1" in message
    assert "TP2" in message
    assert "TP3" in message
    assert "R:R TP2: 2.50:1" in message


def test_format_alert_contains_confirmations():
    payload = build_alert_payload(
        asset="BTCUSDT",
        price=100000,
        decision=base_decision(),
    )

    message = format_alert(payload)

    assert "CONFIRMACIONES" in message
    assert "Ruptura estructural confirmada" in message
    assert "Volumen favorable" in message


def test_format_alert_contains_blockers():
    decision = base_decision()

    decision["blockers"] = (
        "R:R insuficiente",
        "Estructura débil",
    )

    payload = build_alert_payload(
        asset="BTCUSDT",
        price=100000,
        decision=decision,
    )

    message = format_alert(payload)

    assert "BLOQUEADORES" in message
    assert "R:R insuficiente" in message
    assert "Estructura débil" in message


def test_format_alert_contains_warnings():
    decision = base_decision()

    decision["warnings"] = (
        "Volatilidad elevada",
    )

    payload = build_alert_payload(
        asset="BTCUSDT",
        price=100000,
        decision=decision,
    )

    message = format_alert(payload)

    assert "ADVERTENCIAS" in message
    assert "Volatilidad elevada" in message


@pytest.mark.parametrize(
    "decision_value,expected_text",
    [
        (DECISION_BUY, "COMPRA"),
        (DECISION_ACCUMULATE, "ACUMULACIÓN"),
        (DECISION_WAIT, "ESPERAR CONFIRMACIÓN"),
        (DECISION_SPECULATIVE, "ESPECULATIVA"),
        (DECISION_AVOID, "EVITAR"),
    ],
)
def test_all_decisions_have_human_readable_labels(
    decision_value,
    expected_text,
):
    decision = base_decision()
    decision["decision"] = decision_value

    payload = build_alert_payload(
        asset="BTCUSDT",
        price=100000,
        decision=decision,
    )

    message = format_alert(payload)

    assert expected_text in message


def test_format_alert_handles_missing_optional_trade_plan():
    payload = build_alert_payload(
        asset="BTCUSDT",
        price=100000,
        decision=base_decision(),
    )

    message = format_alert(payload)

    assert "BTCUSDT" in message
    assert "COMPRA" in message
    assert "PLAN OPERATIVO" not in message


def test_format_alert_rejects_non_mapping():
    with pytest.raises(TypeError):
        format_alert("invalid")


def test_build_alert_returns_payload_and_message():
    result = build_alert(
        asset="BTCUSDT",
        price=100000,
        decision=base_decision(),
        strategy=base_strategy(),
        risk=base_risk(),
        timeframe="MULTI",
        generated_at="2026-09-12T15:00:00+00:00",
    )

    assert "payload" in result
    assert "message" in result
    assert isinstance(result["payload"], dict)
    assert isinstance(result["message"], str)
    assert "BTCUSDT" in result["message"]


def test_build_alert_message_matches_payload():
    result = build_alert(
        asset="BTCUSDT",
        price=100000,
        decision=base_decision(),
        risk=base_risk(),
    )

    assert result["payload"]["asset"] == "BTCUSDT"
    assert "BTCUSDT" in result["message"]


def test_default_generated_at_is_created():
    result = build_alert_payload(
        asset="BTCUSDT",
        price=100000,
        decision=base_decision(),
    )

    assert result["generated_at"]
    assert "T" in result["generated_at"]


def test_timeframe_is_normalized():
    result = build_alert_payload(
        asset="BTCUSDT",
        price=100000,
        decision=base_decision(),
        timeframe="15m",
    )

    assert result["timeframe"] == "15M"


def test_default_timeframe_is_multi():
    result = build_alert_payload(
        asset="BTCUSDT",
        price=100000,
        decision=base_decision(),
    )

    assert result["timeframe"] == "MULTI"


def test_payload_lists_are_json_friendly():
    result = build_alert_payload(
        asset="BTCUSDT",
        price=100000,
        decision=base_decision(),
    )

    assert isinstance(
        result["confirmations"],
        list,
    )

    assert isinstance(
        result["blockers"],
        list,
    )

    assert isinstance(
        result["warnings"],
        list,
    )