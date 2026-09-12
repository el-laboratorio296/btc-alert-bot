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
    result = build_alert_payload