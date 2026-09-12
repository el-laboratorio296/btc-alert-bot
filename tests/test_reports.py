import math

import pytest

from radar.reports import (
    REPORT_VERSION,
    REPORT_CLOSING,
    REPORT_INTRADAY,
    REPORT_OPENING,
    build_report,
    build_report_payload,
    format_report,
)


def base_alert(
    asset="BTCUSDT",
    decision="BUY",
    score=78.0,
    confidence=86.0,
    risk="LOW",
    regime="RISK_ON",
):
    return {
        "asset": asset,
        "price": 100000.0,
        "decision": decision,
        "bias": "BULLISH",
        "technical_score": score,
        "confidence": confidence,
        "trend_quality": 90.0,
        "timeframe_alignment": 85.0,
        "confirmation_score": 88.0,
        "market_regime": regime,
        "risk_level": risk,
        "reason": "Estructura y momentum compatibles.",
        "confirmations": [
            "Ruptura estructural confirmada",
            "Volumen favorable",
        ],
        "blockers": [],
        "warnings": [],
        "timeframe": "MULTI",
        "entry_zone": "$100,000 - $101,000",
        "invalidation": "$98,500",
        "stop": "$98,000",
        "tp1": "$103,000",
        "tp2": "$106,000",
        "tp3": "$110,000",
        "risk_reward": 2.5,
    }


def base_alerts():
    return [
        base_alert("BTCUSDT", "BUY", 78.0, 86.0),
        base_alert("ETHUSDT", "ACCUMULATE", 72.0, 80.0),
        base_alert(
            "SOLUSDT",
            "WAIT_CONFIRMATION",
            61.0,
            70.0,
            "MEDIUM",
            "NEUTRAL",
        ),
        base_alert(
            "BNBUSDT",
            "AVOID",
            28.0,
            65.0,
            "HIGH",
            "RISK_OFF",
        ),
    ]


def test_build_report_payload_returns_complete_payload():
    result = build_report_payload(
        report_type=REPORT_OPENING,
        alerts=base_alerts(),
        generated_at="2026-09-12T08:00:00-05:00",
    )

    assert result["report_version"] == REPORT_VERSION
    assert result["report_type"] == REPORT_OPENING
    assert result["generated_at"] == (
        "2026-09-12T08:00:00-05:00"
    )
    assert "alerts" in result
    assert len(result["alerts"]) == 4


def test_all_report_types_are_supported():
    for report_type in (
        REPORT_OPENING,
        REPORT_INTRADAY,
        REPORT_CLOSING,
    ):
        result = build_report_payload(
            report_type=report_type,
            alerts=base_alerts(),
        )

        assert result["report_type"] == report_type


def test_invalid_report_type_is_rejected():
    with pytest.raises(ValueError):
        build_report_payload(
            report_type="INVALID",
            alerts=base_alerts(),
        )


def test_alerts_must_be_a_list_like_collection():
    with pytest.raises(TypeError):
        build_report_payload(
            report_type=REPORT_OPENING,
            alerts="invalid",
        )


def test_empty_alert_collection_is_allowed():
    result = build_report_payload(
        report_type=REPORT_OPENING,
        alerts=[],
    )

    assert result["alerts"] == []
    assert result["asset_count"] == 0


def test_report_counts_assets():
    result = build_report_payload(
        report_type=REPORT_OPENING,
        alerts=base_alerts(),
    )

    assert result["asset_count"] == 4


def test_duplicate_assets_are_not_double_counted():
    alerts = [
        base_alert("BTCUSDT"),
        base_alert("BTCUSDT"),
        base_alert("ETHUSDT"),
    ]

    result = build_report_payload(
        report_type=REPORT_OPENING,
        alerts=alerts,
    )

    assert result["asset_count"] == 2
    assert len(result["alerts"]) == 3


def test_asset_names_are_normalized():
    alerts = [
        base_alert("btcusdt"),
        base_alert("ethusdt"),
    ]

    result = build_report_payload(
        report_type=REPORT_OPENING,
        alerts=alerts,
    )

    assert result["alerts"][0]["asset"] == "BTCUSDT"
    assert result["alerts"][1]["asset"] == "ETHUSDT"


def test_non_mapping_alert_is_rejected():
    with pytest.raises(TypeError):
        build_report_payload(
            report_type=REPORT_OPENING,
            alerts=[
                base_alert(),
                "invalid",
            ],
        )


def test_alert_without_asset_is_rejected():
    alert = base_alert()
    del alert["asset"]

    with pytest.raises(ValueError):
        build_report_payload(
            report_type=REPORT_OPENING,
            alerts=[alert],
        )


def test_alert_with_empty_asset_is_rejected():
    alert = base_alert()
    alert["asset"] = "   "

    with pytest.raises(ValueError):
        build_report_payload(
            report_type=REPORT_OPENING,
            alerts=[alert],
        )


def test_scores_are_clamped_inside_report():
    alert = base_alert()

    alert["technical_score"] = 150
    alert["confidence"] = -20
    alert["trend_quality"] = 200
    alert["timeframe_alignment"] = -10

    result = build_report_payload(
        report_type=REPORT_OPENING,
        alerts=[alert],
    )

    normalized = result["alerts"][0]

    assert normalized["technical_score"] == 100.0
    assert normalized["confidence"] == 0.0
    assert normalized["trend_quality"] == 100.0
    assert normalized["timeframe_alignment"] == 0.0


def test_nan_scores_are_safely_handled():
    alert = base_alert()

    alert["technical_score"] = math.nan
    alert["confidence"] = math.nan

    result = build_report_payload(
        report_type=REPORT_OPENING,
        alerts=[alert],
    )

    normalized = result["alerts"][0]

    assert normalized["technical_score"] == 0.0
    assert normalized["confidence"] == 0.0


def test_infinite_scores_are_safely_handled():
    alert = base_alert()

    alert["technical_score"] = math.inf
    alert["confidence"] = -math.inf

    result = build_report_payload(
        report_type=REPORT_OPENING,
        alerts=[alert],
    )

    normalized = result["alerts"][0]

    assert normalized["technical_score"] == 0.0
    assert normalized["confidence"] == 0.0


def test_report_calculates_average_score():
    alerts = [
        base_alert("BTCUSDT", score=80.0),
        base_alert("ETHUSDT", score=60.0),
    ]

    result = build_report_payload(
        report_type=REPORT_OPENING,
        alerts=alerts,
    )

    assert result["average_technical_score"] == 70.0


def test_report_calculates_average_confidence():
    alerts = [
        base_alert("BTCUSDT", confidence=90.0),
        base_alert("ETHUSDT", confidence=70.0),
    ]

    result = build_report_payload(
        report_type=REPORT_OPENING,
        alerts=alerts,
    )

    assert result["average_confidence"] == 80.0


def test_empty_report_has_zero_averages():
    result = build_report_payload(
        report_type=REPORT_OPENING,
        alerts=[],
    )

    assert result["average_technical_score"] == 0.0
    assert result["average_confidence"] == 0.0


def test_report_counts_decisions():
    result = build_report_payload(
        report_type=REPORT_OPENING,
        alerts=base_alerts(),
    )

    assert result["decision_counts"]["BUY"] == 1
    assert result["decision_counts"]["ACCUMULATE"] == 1
    assert result["decision_counts"][
        "WAIT_CONFIRMATION"
    ] == 1
    assert result["decision_counts"]["AVOID"] == 1


def test_report_counts_risk_levels():
    result = build_report_payload(
        report_type=REPORT_OPENING,
        alerts=base_alerts(),
    )

    assert result["risk_counts"]["LOW"] == 2
    assert result["risk_counts"]["MEDIUM"] == 1
    assert result["risk_counts"]["HIGH"] == 1


def test_report_counts_market_regimes():
    result = build_report_payload(
        report_type=REPORT_OPENING,
        alerts=base_alerts(),
    )

    assert result["regime_counts"]["RISK_ON"] == 2
    assert result["regime_counts"]["NEUTRAL"] == 1
    assert result["regime_counts"]["RISK_OFF"] == 1


def test_report_identifies_buy_opportunities():
    result = build_report_payload(
        report_type=REPORT_OPENING,
        alerts=base_alerts(),
    )

    assert result["buy_assets"] == ["BTCUSDT"]


def test_report_identifies_accumulation_opportunities():
    result = build_report_payload(
        report_type=REPORT_OPENING,
        alerts=base_alerts(),
    )

    assert result["accumulation_assets"] == ["ETHUSDT"]


def test_report_identifies_waiting_assets():
    result = build_report_payload(
        report_type=REPORT_OPENING,
        alerts=base_alerts(),
    )

    assert result["waiting_assets"] == ["SOLUSDT"]


def test_report_identifies_avoid_assets():
    result = build_report_payload(
        report_type=REPORT_OPENING,
        alerts=base_alerts(),
    )

    assert result["avoid_assets"] == ["BNBUSDT"]


def test_report_preserves_alert_information():
    alerts = [
        base_alert("BTCUSDT"),
    ]

    result = build_report_payload(
        report_type=REPORT_OPENING,
        alerts=alerts,
    )

    alert = result["alerts"][0]

    assert alert["asset"] == "BTCUSDT"
    assert alert["price"] == 100000.0
    assert alert["decision"] == "BUY"
    assert alert["technical_score"] == 78.0
    assert alert["confidence"] == 86.0
    assert alert["risk_level"] == "LOW"
    assert alert["market_regime"] == "RISK_ON"


def test_format_opening_report_contains_core_information():
    payload = build_report_payload(
        report_type=REPORT_OPENING,
        alerts=base_alerts(),
        generated_at="2026-09-12T08:00:00-05:00",
    )

    message = format_report(payload)

    assert "EL LABORATORIO" in message
    assert "APERTURA" in message
    assert "BTCUSDT" in message
    assert "ETHUSDT" in message
    assert "SOLUSDT" in message
    assert "BNBUSDT" in message
    assert "78%" in message
    assert "86%" in message


def test_format_intraday_report_contains_intraday_label():
    payload = build_report_payload(
        report_type=REPORT_INTRADAY,
        alerts=base_alerts(),
    )

    message = format_report(payload)

    assert "INTRADÍA" in message


def test_format_closing_report_contains_closing_label():
    payload = build_report_payload(
        report_type=REPORT_CLOSING,
        alerts=base_alerts(),
    )

    message = format_report(payload)

    assert "CIERRE" in message


def test_format_report_contains_market_summary():
    payload = build_report_payload(
        report_type=REPORT_OPENING,
        alerts=base_alerts(),
    )

    message = format_report(payload)

    assert "RESUMEN DEL MERCADO" in message
    assert "Score medio" in message
    assert "Confianza media" in message


def test_format_report_contains_opportunities():
    payload = build_report_payload(
        report_type=REPORT_OPENING,
        alerts=base_alerts(),
    )

    message = format_report(payload)

    assert "OPORTUNIDADES" in message
    assert "BTCUSDT" in message
    assert "ETHUSDT" in message


def test_format_report_contains_waiting_section():
    payload = build_report_payload(
        report_type=REPORT_OPENING,
        alerts=base_alerts(),
    )

    message = format_report(payload)

    assert "ESPERANDO CONFIRMACIÓN" in message
    assert "SOLUSDT" in message


def test_format_report_contains_avoid_section():
    payload = build_report_payload(
        report_type=REPORT_OPENING,
        alerts=base_alerts(),
    )

    message = format_report(payload)

    assert "EVITAR" in message
    assert "BNBUSDT" in message


def test_format_empty_report_is_safe():
    payload = build_report_payload(
        report_type=REPORT_OPENING,
        alerts=[],
    )

    message = format_report(payload)

    assert "EL LABORATORIO" in message
    assert "APERTURA" in message
    assert "Sin señales" in message


def test_format_report_rejects_non_mapping():
    with pytest.raises(TypeError):
        format_report("invalid")


def test_build_report_returns_payload_and_message():
    result = build_report(
        report_type=REPORT_OPENING,
        alerts=base_alerts(),
        generated_at="2026-09-12T08:00:00-05:00",
    )

    assert "payload" in result
    assert "message" in result
    assert isinstance(result["payload"], dict)
    assert isinstance(result["message"], str)


def test_build_report_message_matches_payload():
    result = build_report(
        report_type=REPORT_OPENING,
        alerts=[
            base_alert("BTCUSDT"),
        ],
    )

    assert result["payload"]["alerts"][0]["asset"] == (
        "BTCUSDT"
    )
    assert "BTCUSDT" in result["message"]


def test_default_generated_at_is_created():
    result = build_report_payload(
        report_type=REPORT_OPENING,
        alerts=[],
    )

    assert result["generated_at"]
    assert "T" in result["generated_at"]


def test_report_payload_is_json_friendly():
    result = build_report_payload(
        report_type=REPORT_OPENING,
        alerts=base_alerts(),
    )

    assert isinstance(result["alerts"], list)
    assert isinstance(result["decision_counts"], dict)
    assert isinstance(result["risk_counts"], dict)
    assert isinstance(result["regime_counts"], dict)
    assert isinstance(result["buy_assets"], list)
    assert isinstance(result["accumulation_assets"], list)
    assert isinstance(result["waiting_assets"], list)
    assert isinstance(result["avoid_assets"], list)


def test_report_does_not_change_input_alerts():
    alerts = base_alerts()

    original_asset = alerts[0]["asset"]
    original_score = alerts[0]["technical_score"]

    build_report_payload(
        report_type=REPORT_OPENING,
        alerts=alerts,
    )

    assert alerts[0]["asset"] == original_asset
    assert alerts[0]["technical_score"] == original_score


def test_report_preserves_asset_order():
    alerts = [
        base_alert("SOLUSDT"),
        base_alert("BTCUSDT"),
        base_alert("ETHUSDT"),
    ]

    result = build_report_payload(
        report_type=REPORT_OPENING,
        alerts=alerts,
    )

    assert [
        item["asset"]
        for item in result["alerts"]
    ] == [
        "SOLUSDT",
        "BTCUSDT",
        "ETHUSDT",
    ]


def test_report_limits_message_sections_to_available_assets():
    payload = build_report_payload(
        report_type=REPORT_OPENING,
        alerts=[
            base_alert("BTCUSDT"),
        ],
    )

    message = format_report(payload)

    assert "BTCUSDT" in message
    assert "ETHUSDT" not in message
    assert "SOLUSDT" not in message
    assert "BNBUSDT" not in message