from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Any, Mapping


class ReportError(Exception):
    """Error base del sistema de reportes."""


REPORT_VERSION = "1.0"

REPORT_OPENING = "OPENING"
REPORT_INTRADAY = "INTRADAY"
REPORT_CLOSING = "CLOSING"

VALID_REPORT_TYPES = {
    REPORT_OPENING,
    REPORT_INTRADAY,
    REPORT_CLOSING,
}

VALID_DECISIONS = {
    "BUY",
    "ACCUMULATE",
    "WAIT_CONFIRMATION",
    "SPECULATIVE",
    "AVOID",
}

VALID_RISK_LEVELS = {
    "LOW",
    "MEDIUM",
    "HIGH",
    "EXTREME",
}

VALID_REGIMES = {
    "RISK_ON",
    "NEUTRAL",
    "RISK_OFF",
    "HIGH_RISK",
}


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _number(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default

    try:
        number = float(value)
    except (TypeError, ValueError):
        return default

    if not isfinite(number):
        return default

    return number


def _clamp(
    value: Any,
    minimum: float = 0.0,
    maximum: float = 100.0,
    default: float = 0.0,
) -> float:
    number = _number(value, default)
    return max(minimum, min(maximum, number))


def _items(value: Any) -> list[str]:
    if value is None:
        return []

    if not isinstance(value, (list, tuple, set)):
        return []

    result: list[str] = []

    for item in value:
        text = _text(item)

        if text and text not in result:
            result.append(text)

    return result


def _normalize_alert(
    alert: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(alert, Mapping):
        raise TypeError("Cada alert debe ser un Mapping.")

    asset = _text(alert.get("asset")).upper()

    if not asset:
        raise ValueError(
            "Cada alert debe contener un asset válido."
        )

    decision = _text(
        alert.get("decision", "WAIT_CONFIRMATION")
    ).upper()

    if decision not in VALID_DECISIONS:
        decision = "WAIT_CONFIRMATION"

    bias = _text(
        alert.get("bias", "NEUTRAL")
    ).upper()

    regime = _text(
        alert.get("market_regime", "NEUTRAL")
    ).upper()

    if regime not in VALID_REGIMES:
        regime = "NEUTRAL"

    risk_level = _text(
        alert.get("risk_level", "MEDIUM")
    ).upper()

    if risk_level not in VALID_RISK_LEVELS:
        risk_level = "MEDIUM"

    risk_reward_value = alert.get("risk_reward")

    if risk_reward_value is None:
        risk_reward = None
    else:
        risk_reward = _number(
            risk_reward_value,
            0.0,
        )

    return {
        "asset": asset,
        "price": _number(
            alert.get("price"),
            0.0,
        ),
        "decision": decision,
        "bias": bias,
        "technical_score": _clamp(
            alert.get("technical_score"),
            default=0.0,
        ),
        "confidence": _clamp(
            alert.get("confidence"),
            default=0.0,
        ),
        "trend_quality": _clamp(
            alert.get("trend_quality"),
            default=50.0,
        ),
        "timeframe_alignment": _clamp(
            alert.get("timeframe_alignment"),
            default=50.0,
        ),
        "confirmation_score": _clamp(
            alert.get("confirmation_score"),
            default=50.0,
        ),
        "market_regime": regime,
        "risk_level": risk_level,
        "reason": _text(
            alert.get("reason"),
            "Sin explicación disponible.",
        ),
        "confirmations": _items(
            alert.get("confirmations")
        ),
        "blockers": _items(
            alert.get("blockers")
        ),
        "warnings": _items(
            alert.get("warnings")
        ),
        "timeframe": _text(
            alert.get("timeframe", "MULTI"),
            "MULTI",
        ).upper(),
        "entry_zone": alert.get("entry_zone"),
        "invalidation": alert.get("invalidation"),
        "stop": alert.get("stop"),
        "tp1": alert.get("tp1"),
        "tp2": alert.get("tp2"),
        "tp3": alert.get("tp3"),
        "risk_reward": risk_reward,
    }


def _report_title(report_type: str) -> str:
    titles = {
        REPORT_OPENING: "APERTURA",
        REPORT_INTRADAY: "INTRADÍA",
        REPORT_CLOSING: "CIERRE",
    }

    return titles.get(report_type, "REPORTE")


def _decision_label(decision: str) -> str:
    labels = {
        "BUY": "🟢 COMPRA",
        "ACCUMULATE": "🟡 ACUMULACIÓN",
        "WAIT_CONFIRMATION": "🟠 ESPERAR CONFIRMACIÓN",
        "SPECULATIVE": "🟣 ESPECULATIVA",
        "AVOID": "🔴 EVITAR",
    }

    return labels.get(decision, decision)


def _risk_label(risk: str) -> str:
    labels = {
        "LOW": "BAJO",
        "MEDIUM": "MEDIO",
        "HIGH": "ALTO",
        "EXTREME": "EXTREMO",
    }

    return labels.get(risk, risk)


def _regime_label(regime: str) -> str:
    labels = {
        "RISK_ON": "RISK ON",
        "NEUTRAL": "NEUTRAL",
        "RISK_OFF": "RISK OFF",
        "HIGH_RISK": "ALTO RIESGO",
    }

    return labels.get(regime, regime)


def build_report_payload(
    report_type: str,
    alerts: list[Mapping[str, Any]],
    generated_at: str | None = None,
) -> dict[str, Any]:

    if not isinstance(alerts, (list, tuple)):
        raise TypeError(
            "alerts debe ser una lista o tupla."
        )

    report_type_value = _text(
        report_type
    ).upper()

    if report_type_value not in VALID_REPORT_TYPES:
        raise ValueError(
            f"Tipo de reporte no válido: {report_type_value}"
        )

    normalized_alerts: list[dict[str, Any]] = []

    for alert in alerts:
        normalized_alerts.append(
            _normalize_alert(alert)
        )

    if generated_at is None:
        generated_at = datetime.now(
            timezone.utc
        ).isoformat()

    generated_at_text = _text(generated_at)

    if not generated_at_text:
        generated_at_text = datetime.now(
            timezone.utc
        ).isoformat()

    asset_names: list[str] = []

    for alert in normalized_alerts:
        asset = alert["asset"]

        if asset not in asset_names:
            asset_names.append(asset)

    scores = [
        alert["technical_score"]
        for alert in normalized_alerts
    ]

    confidences = [
        alert["confidence"]
        for alert in normalized_alerts
    ]

    average_score = (
        sum(scores) / len(scores)
        if scores
        else 0.0
    )

    average_confidence = (
        sum(confidences) / len(confidences)
        if confidences
        else 0.0
    )

    decision_counts = {
        decision: 0
        for decision in VALID_DECISIONS
    }

    risk_counts = {
        risk: 0
        for risk in VALID_RISK_LEVELS
    }

    regime_counts = {
        regime: 0
        for regime in VALID_REGIMES
    }

    buy_assets: list[str] = []
    accumulation_assets: list[str] = []
    waiting_assets: list[str] = []
    avoid_assets: list[str] = []

    for alert in normalized_alerts:
        decision = alert["decision"]
        risk = alert["risk_level"]
        regime = alert["market_regime"]
        asset = alert["asset"]

        decision_counts[decision] += 1
        risk_counts[risk] += 1
        regime_counts[regime] += 1

        if decision == "BUY":
            if asset not in buy_assets:
                buy_assets.append(asset)

        elif decision == "ACCUMULATE":
            if asset not in