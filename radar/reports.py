from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Any, Mapping


class ReportError(Exception):
    pass


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
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default

    if not isfinite(number):
        return default

    return number


def _score(value: Any, default: float = 0.0) -> float:
    number = _number(value, default)
    return max(0.0, min(100.0, number))


def _items(value: Any) -> list[str]:
    if value is None:
        return []

    if not isinstance(value, (list, tuple, set)):
        return []

    result = []

    for item in value:
        text = _text(item)

        if text and text not in result:
            result.append(text)

    return result


def _normalize_alert(alert: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(alert, Mapping):
        raise TypeError("Cada alert debe ser un Mapping.")

    asset = _text(alert.get("asset")).upper()

    if not asset:
        raise ValueError("Cada alert debe contener un asset válido.")

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

    risk = _text(
        alert.get("risk_level", "MEDIUM")
    ).upper()

    if risk not in VALID_RISK_LEVELS:
        risk = "MEDIUM"

    rr = alert.get("risk_reward")

    if rr is not None:
        rr = _number(rr, 0.0)

    return {
        "asset": asset,
        "price": _number(alert.get("price"), 0.0),
        "decision": decision,
        "bias": bias,
        "technical_score": _score(
            alert.get("technical_score"),
            0.0,
        ),
        "confidence": _score(
            alert.get("confidence"),
            0.0,
        ),
        "trend_quality": _score(
            alert.get("trend_quality"),
            50.0,
        ),
        "timeframe_alignment": _score(
            alert.get("timeframe_alignment"),
            50.0,
        ),
        "confirmation_score": _score(
            alert.get("confirmation_score"),
            50.0,
        ),
        "market_regime": regime,
        "risk_level": risk,
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
        "risk_reward": rr,
    }


def _title(report_type: str) -> str:
    if report_type == REPORT_OPENING:
        return "APERTURA"

    if report_type == REPORT_INTRADAY:
        return "INTRADÍA"

    if report_type == REPORT_CLOSING:
        return "CIERRE"

    return "REPORTE"


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
        raise TypeError("alerts debe ser una lista o tupla.")

    report_type = _text(report_type).upper()

    if report_type not in VALID_REPORT_TYPES:
        raise ValueError(
            f"Tipo de reporte no válido: {report_type}"
        )

    normalized = []

    for alert in alerts:
        normalized.append(
            _normalize_alert(alert)
        )

    if generated_at is None:
        generated_at = datetime.now(
            timezone.utc
        ).isoformat()

    generated_at = _text(generated_at)

    if not generated_at:
        generated_at = datetime.now(
            timezone.utc
        ).isoformat()

    assets = []

    for alert in normalized:
        asset = alert["asset"]

        if asset not in assets:
            assets.append(asset)

    scores = [
        alert["technical_score"]
        for alert in normalized
    ]

    confidences = [
        alert["confidence"]
        for alert in normalized
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
        "BUY": 0,
        "ACCUMULATE": 0,
        "WAIT_CONFIRMATION": 0,
        "SPECULATIVE": 0,
        "AVOID": 0,
    }

    risk_counts = {
        "LOW": 0,
        "MEDIUM": 0,
        "HIGH": 0,
        "EXTREME": 0,
    }

    regime_counts = {
        "RISK_ON": 0,
        "NEUTRAL": 0,
        "RISK_OFF": 0,
        "HIGH_RISK": 0,
    }

    buy_assets = []
    accumulation_assets = []
    waiting_assets = []
    avoid_assets = []

    for alert in normalized:
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
            if asset not in accumulation_assets:
                accumulation_assets.append(asset)

        elif decision == "WAIT_CONFIRMATION":
            if asset not in waiting_assets:
                waiting_assets.append(asset)

        elif decision == "AVOID":
            if asset not in avoid_assets:
                avoid_assets.append(asset)

    return {
        "report_version": REPORT_VERSION,
        "report_type": report_type,
        "generated_at": generated_at,
        "alerts": normalized,
        "asset_count": len(assets),
        "average_technical_score": round(
            average_score,
            4,
        ),
        "average_confidence": round(
            average_confidence,
            4,
        ),
        "decision_counts": decision_counts,
        "risk_counts": risk_counts,
        "regime_counts": regime_counts,
        "buy_assets": buy_assets,
        "accumulation_assets": accumulation_assets,
        "waiting_assets": waiting_assets,
        "avoid_assets": avoid_assets,
    }


def _format_price(value: Any) -> str:
    number = _number(value, 0.0)

    if number <= 0:
        return "N/D"

    if number >= 1000:
        return f"{number:,.2f}"

    if number >= 1:
        return f"{number:,.4f}"

    if number >= 0.01:
        return f"{number:,.6f}"

    return f"{number:.8f}"


def format_report(
    payload: Mapping[str, Any],
) -> str:

    if not isinstance(payload, Mapping):
        raise TypeError("payload debe ser un Mapping.")

    report_type = _text(
        payload.get(
            "report_type",
            REPORT_OPENING,
        )
    ).upper()

    title = _title(report_type)

    alerts = payload.get("alerts", [])

    if not isinstance(alerts, (list, tuple)):
        alerts = []

    average_score = _score(
        payload.get(
            "average_technical_score",
            0.0,
        )
    )

    average_confidence = _score(
        payload.get(
            "average_confidence",
            0.0,
        )
    )

    asset_count = int(
        _number(
            payload.get("asset_count", 0),
            0.0,
        )
    )

    lines = []

    lines.append(
        "🧪 EL LABORATORIO — RADAR"
    )

    lines.append("")

    lines.append(
        f"📋 REPORTE DE {title}"
    )

    lines.append("")

    lines.append(
        "📊 RESUMEN DEL MERCADO"
    )

    lines.append(
        f"Activos analizados: {asset_count}"
    )

    lines.append(
        f"Score medio: {average_score:.0f}%"
    )

    lines.append(
        f"Confianza media: {average_confidence:.0f}%"
    )

    if not alerts:
        lines.append("")
        lines.append(
            "ℹ️ Sin señales disponibles."
        )
        lines.append("")
        lines.append(
            "━━━━━━━━━━━━━━━━"
        )
        lines.append(
            "⚠️ Radar informativo. No garantiza resultados."
        )

        return "\n".join(lines)

    lines.append("")
    lines.append("🔎 SEÑALES")

    for alert in alerts:
        if not isinstance(alert, Mapping):
            continue

        asset = _text(
            alert.get("asset"),
            "UNKNOWN",
        ).upper()

        price = _format_price(
            alert.get("price")
        )

        decision = _text(
            alert.get(
                "decision",
                "WAIT_CONFIRMATION",
            )
        ).upper()

        score = _score(
            alert.get(
                "technical_score",
                0.0,
            )
        )

        confidence = _score(
            alert.get(
                "confidence",
                0.0,
            )
        )

        risk = _risk_label(
            _text(
                alert.get(
                    "risk_level",
                    "MEDIUM",
                )
            ).upper()
        )

        regime = _regime_label(
            _text(
                alert.get(
                    "market_regime",
                    "NEUTRAL",
                )
            ).upper()
        )

        lines.append("")
        lines.append(
            f"💠 {asset}"
        )
        lines.append(
            f"Precio: ${price}"
        )
        lines.append(
            f"Decisión: {_decision_label(decision)}"
        )
        lines.append(
            f"Score: {score:.0f}%"
        )
        lines.append(
            f"Confianza: {confidence:.0f}%"
        )
        lines.append(
            f"Riesgo: {risk}"
        )
        lines.append(
            f"Régimen: {regime}"
        )

    buy_assets = _items(
        payload.get("buy_assets")
    )

    accumulation_assets = _items(
        payload.get("accumulation_assets")
    )

    waiting_assets = _items(
        payload.get("waiting_assets")
    )

    avoid_assets = _items(
        payload.get("avoid_assets")
    )

    if buy_assets or accumulation_assets:
        lines.append("")
        lines.append("🚀 OPORTUNIDADES")

        if buy_assets:
            lines.append(
                "🟢 Compra: "
                + ", ".join(buy_assets)
            )

        if accumulation_assets:
            lines.append(
                "🟡 Acumulación: "
                + ", ".join(
                    accumulation_assets
                )
            )

    if waiting_assets:
        lines.append("")
        lines.append(
            "⏳ ESPERANDO CONFIRMACIÓN"
        )
        lines.append(
            ", ".join(waiting_assets)
        )

    if avoid_assets:
        lines.append("")
        lines.append("⛔ EVITAR")
        lines.append(
            ", ".join(avoid_assets)
        )

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━")
    lines.append(
        "⚠️ Radar informativo. No garantiza resultados."
    )

    return "\n".join(lines)


def build_report(
    report_type: str,
    alerts: list[Mapping[str, Any]],
    generated_at: str | None = None,
) -> dict[str, Any]:

    payload = build_report_payload(
        report_type=report_type,
        alerts=alerts,
        generated_at=generated_at,
    )

    return {
        "payload": payload,
        "message": format_report(payload),
    }