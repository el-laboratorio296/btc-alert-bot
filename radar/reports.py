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


def _text(
    value: Any,
    default: str = "",
) -> str:
    if value is None:
        return default

    return str(value).strip()


def _number(
    value: Any,
    default: float = 0.0,
) -> float:
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
    number = _number(
        value,
        default,
    )

    return max(
        minimum,
        min(maximum, number),
    )


def _items(
    value: Any,
) -> list[str]:
    if value is None:
        return []

    if not isinstance(
        value,
        (list, tuple, set),
    ):
        return []

    result: list[str] = []

    for item in value:
        text = _text(item)

        if not text:
            continue

        if text not in result:
            result.append(text)

    return result


def _normalize_alert(
    alert: Mapping[str, Any],
) -> dict[str, Any]:

    if not isinstance(
        alert,
        Mapping,
    ):
        raise TypeError(
            "Cada alert debe ser un Mapping."
        )

    asset = _text(
        alert.get("asset")
    ).upper()

    if not asset:
        raise ValueError(
            "Cada alert debe contener un asset válido."
        )

    decision = _text(
        alert.get(
            "decision",
            "WAIT_CONFIRMATION",
        )
    ).upper()

    if decision not in VALID_DECISIONS:
        decision = "WAIT_CONFIRMATION"

    bias = _text(
        alert.get(
            "bias",
            "NEUTRAL",
        )
    ).upper()

    regime = _text(
        alert.get(
            "market_regime",
            "NEUTRAL",
        )
    ).upper()

    if regime not in VALID_REGIMES:
        regime = "NEUTRAL"

    risk_level = _text(
        alert.get(
            "risk_level",
            "MEDIUM",
        )
    ).upper()

    if risk_level not in VALID_RISK_LEVELS:
        risk_level = "MEDIUM"

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
            alert.get(
                "timeframe_alignment"
            ),
            default=50.0,
        ),
        "confirmation_score": _clamp(
            alert.get(
                "confirmation_score"
            ),
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
            alert.get(
                "timeframe",
                "MULTI",
            ),
            "MULTI",
        ).upper(),
        "entry_zone": alert.get(
            "entry_zone"
        ),
        "invalidation": alert.get(
            "invalidation"
        ),
        "stop": alert.get(
            "stop"
        ),
        "tp1": alert.get("tp1"),
        "tp2": alert.get("tp2"),
        "tp3": alert.get("tp3"),
        "risk_reward": (
            _number(
                alert.get(
                    "risk_reward"
                ),
                0.0,
            )
            if alert.get(
                "risk_reward"
            ) is not None
            else None
        ),
    }


def _report_title(
    report_type: str,
) -> str:
    titles = {
        REPORT_OPENING: "APERTURA",
        REPORT_INTRADAY: "INTRADÍA",
        REPORT_CLOSING: "CIERRE",
    }

    return titles.get(
        report_type,
        "REPORTE",
    )


def _decision_label(
    decision: str,
) -> str:
    labels = {
        "BUY": "🟢 COMPRA",
        "ACCUMULATE": "🟡 ACUMULACIÓN",
        "WAIT_CONFIRMATION": (
            "🟠 ESPERAR CONFIRMACIÓN"
        ),
        "SPECULATIVE": "🟣 ESPECULATIVA",
        "AVOID": "🔴 EVITAR",
    }

    return labels.get(
        decision,
        decision,
    )


def _risk_label(
    risk: str,
) -> str:
    labels = {
        "LOW": "BAJO",
        "MEDIUM": "MEDIO",
        "HIGH": "ALTO",
        "EXTREME": "EXTREMO",
    }

    return labels.get(
        risk,
        risk,
    )


def _regime_label(
    regime: str,
) -> str:
    labels = {
        "RISK_ON": "RISK ON",
        "NEUTRAL": "NEUTRAL",
        "RISK_OFF": "RISK OFF",
        "HIGH_RISK