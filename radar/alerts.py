from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Any, Mapping


class AlertError(Exception):
    pass


ALERT_VERSION = "1.0"

DECISION_BUY = "BUY"
DECISION_ACCUMULATE = "ACCUMULATE"
DECISION_WAIT = "WAIT_CONFIRMATION"
DECISION_SPECULATIVE = "SPECULATIVE"
DECISION_AVOID = "AVOID"

VALID_DECISIONS = {
    DECISION_BUY,
    DECISION_ACCUMULATE,
    DECISION_WAIT,
    DECISION_SPECULATIVE,
    DECISION_AVOID,
}


@dataclass(frozen=True)
class AlertPayload:
    asset: str
    price: float
    decision: str
    bias: str
    technical_score: float
    confidence: float
    trend_quality: float
    timeframe_alignment: float
    confirmation_score: float
    market_regime: str
    risk_level: str
    reason: str
    entry_zone: str | None = None
    invalidation: str | None = None
    stop: str | None = None
    tp1: str | None = None
    tp2: str | None = None
    tp3: str | None = None
    risk_reward: float | None = None
    confirmations: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    timeframe: str = "MULTI"
    generated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_version": ALERT_VERSION,
            "asset": self.asset,
            "price": self.price,
            "decision": self.decision,
            "bias": self.bias,
            "technical_score": self.technical_score,
            "confidence": self.confidence,
            "trend_quality": self.trend_quality,
            "timeframe_alignment": self.timeframe_alignment,
            "confirmation_score": self.confirmation_score,
            "market_regime": self.market_regime,
            "risk_level": self.risk_level,
            "reason": self.reason,
            "entry_zone": self.entry_zone,
            "invalidation": self.invalidation,
            "stop": self.stop,
            "tp1": self.tp1,
            "tp2": self.tp2,
            "tp3": self.tp3,
            "risk_reward": self.risk_reward,
            "confirmations": list(self.confirmations),
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "timeframe": self.timeframe,
            "generated_at": self.generated_at,
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
    default: float | None = None,
) -> float | None:
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
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    return max(
        minimum,
        min(maximum, float(value)),
    )


def _optional_text(
    value: Any,
) -> str | None:
    text = _text(value)

    if not text:
        return None

    return text


def _items(
    value: Any,
) -> tuple[str, ...]:
    if value is None:
        return ()

    if not isinstance(
        value,
        (list, tuple, set),
    ):
        return ()

    result = []

    for item in value:
        text = _text(item)

        if text:
            result.append(text)

    return tuple(
        dict.fromkeys(result)
    )


def _format_price(
    value: Any,
) -> str:
    number = _number(value)

    if number is None:
        return "N/D"

    if number >= 1000:
        return f"{number:,.2f}"

    if number >= 1:
        return f"{number:,.4f}"

    if number >= 0.01:
        return f"{number:,.6f}"

    return f"{number:.8f}"


def _format_percent(
    value: Any,
) -> str:
    number = _number(value, 0.0)

    if number is None:
        number = 0.0

    return f"{_clamp(number):.0f}%"


def _decision_label(
    decision: str,
) -> str:
    labels = {
        DECISION_BUY: "🟢 COMPRA",
        DECISION_ACCUMULATE: "🟡 ACUMULACIÓN",
        DECISION_WAIT: "🟠 ESPERAR CONFIRMACIÓN",
        DECISION_SPECULATIVE: "🟣 ESPECULATIVA",
        DECISION_AVOID: "🔴 EVITAR",
    }

    return labels.get(
        decision,
        "⚪ SIN DECISIÓN",
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
        risk or "N/D",
    )


def _regime_label(
    regime: str,
) -> str:
    labels = {
        "RISK_ON": "RISK ON",
        "NEUTRAL": "NEUTRAL",
        "RISK_OFF": "RISK OFF",
        "HIGH_RISK": "ALTO RIESGO",
    }

    return labels.get(
        regime,
        regime or "N/D",
    )


def build_alert_payload(
    asset: str,
    price: float,
    decision: Mapping[str, Any],
    strategy: Mapping[str, Any] | None = None,
    risk: Mapping[str, Any] | None = None,
    timeframe: str = "MULTI",
    generated_at: str | None = None,
) -> dict[str, Any]:

    if not isinstance(
        decision,
        Mapping,
    ):
        raise TypeError(
            "decision debe ser un Mapping."
        )

    if strategy is not None and not isinstance(
        strategy,
        Mapping,
    ):
        raise TypeError(
            "strategy debe ser un Mapping."
        )

    if risk is not None and not isinstance(
        risk,
        Mapping,
    ):
        raise TypeError(
            "risk debe ser un Mapping."
        )

    asset_text = _text(asset).upper()

    if not asset_text:
        raise ValueError(
            "asset no puede estar vacío."
        )

    price_number = _number(price)

    if price_number is None or price_number <= 0:
        raise ValueError(
            "price debe ser un número mayor que cero."
        )

    decision_value = _text(
        decision.get("decision")
    ).upper()

    if decision_value not in VALID_DECISIONS:
        raise ValueError(
            f"Decisión no válida: {decision_value}"
        )

    technical_score = _clamp(
        _number(
            decision.get("technical_score"),
            0.0,
        )
    )

    confidence = _clamp(
        _number(
            decision.get("confidence"),
            0.0,
        )
    )

    trend_quality = _clamp(
        _number(
            decision.get("trend_quality"),
            50.0,
        )
    )

    timeframe_alignment = _clamp(
        _number(
            decision.get(
                "timeframe_alignment"
            ),
            50.0,
        )
    )

    confirmation_score = _clamp(
        _number(
            decision.get(
                "confirmation_score"
            ),
            50.0,
        )
    )

    bias = _text(
        decision.get("bias"),
        "NEUTRAL",
    ).upper()

    market_regime = _text(
        decision.get(
            "market_regime"
        ),
        "NEUTRAL",
    ).upper()

    risk_level = _text(
        decision.get(
            "risk_level"
        ),
        "MEDIUM",
    ).upper()

    reason = _text(
        decision.get(
            "reason"
        ),
        "Sin explicación disponible.",
    )

    strategy_data = strategy or {}
    risk_data = risk or {}

    entry_zone = _optional_text(
        risk_data.get(
            "entry_zone",
            strategy_data.get(
                "entry_zone"
            ),
        )
    )

    invalidation = _optional_text(
        risk_data.get(
            "invalidation",
            strategy_data.get(
                "invalidation"
            ),
        )
    )

    stop = _optional_text(
        risk_data.get(
            "stop",
            strategy_data.get(
                "stop"
            ),
        )
    )

    tp1 = _optional_text(
        risk_data.get(
            "tp1",
            strategy_data.get(
                "tp1"
            ),
        )
    )

    tp2 = _optional_text(
        risk_data.get(
            "tp2",
            strategy_data.get(
                "tp2"
            ),
        )
    )

    tp3 = _optional_text(
        risk_data.get(
            "tp3",
            strategy_data.get(
                "tp3"
            ),
        )
    )

    risk_reward = _number(
        risk_data.get(
            "risk_reward_tp2"
        )
    )

    confirmations = _items(
        decision.get(
            "confirmations",
            strategy_data.get(
                "confirmations",
                (),
            ),
        )
    )

    blockers = _items(
        decision.get(
            "blockers",
            strategy_data.get(
                "blockers",
                (),
            ),
        )
    )

    warnings = _items(
        decision.get(
            "warnings",
            (),
        )
    )

    if generated_at is None:
        generated_at = datetime.now(
            timezone.utc
        ).isoformat()

    generated_at_text = _text(
        generated_at
    )

    if not generated_at_text:
        generated_at_text = datetime.now(
            timezone.utc
        ).isoformat()

    payload = AlertPayload(
        asset=asset_text,
        price=price_number,
        decision=decision_value,
        bias=bias,
        technical_score=round(
            technical_score,
            4,
        ),
        confidence=round(
            confidence,
            4,
        ),
        trend_quality=round(
            trend_quality,
            4,
        ),
        timeframe_alignment=round(
            timeframe_alignment,
            4,
        ),
        confirmation_score=round(
            confirmation_score,
            4,
        ),
        market_regime=market_regime,
        risk_level=risk_level,
        reason=reason,
        entry_zone=entry_zone,
        invalidation=invalidation,
        stop=stop,
        tp1=tp1,
        tp2=tp2,
        tp3=tp3,
        risk_reward=(
            round(risk_reward, 4)
            if risk_reward is not None
            else None
        ),
        confirmations=confirmations,
        blockers=blockers,
        warnings=warnings,
        timeframe=_text(
            timeframe,
            "MULTI",
        ).upper(),
        generated_at=generated_at_text,
    )

    return payload.to_dict()


def format_alert(
    payload: Mapping[str, Any],
) -> str:
    if not isinstance(
        payload,
        Mapping,
    ):
        raise TypeError(
            "payload debe ser un Mapping."
        )

    asset = _text(
        payload.get("asset"),
        "UNKNOWN",
    ).upper()

    price = _format_price(
        payload.get("price")
    )

    decision = _text(
        payload.get("decision")
    ).upper()

    bias = _text(
        payload.get(
            "bias",
            "NEUTRAL",
        )
    ).upper()

    technical_score = _format_percent(
        payload.get(
            "technical_score",
            0,
        )
    )

    confidence = _format_percent(
        payload.get(
            "confidence",
            0,
        )
    )

    trend_quality = _format_percent(
        payload.get(
            "trend_quality",
            0,
        )
    )

    alignment = _format_percent(
        payload.get(
            "timeframe_alignment",
            0,
        )
    )

    confirmation = _format_percent(
        payload.get(
            "confirmation_score",
            0,
        )
    )

    regime = _regime_label(
        _text(
            payload.get(
                "market_regime"
            )
        ).upper()
    )

    risk = _risk_label(
        _text(
            payload.get(
                "risk_level"
            )
        ).upper()
    )

    reason = _text(
        payload.get(
            "reason"
        ),
        "Sin explicación disponible.",
    )

    timeframe = _text(
        payload.get(
            "timeframe",
            "MULTI",
        ),
        "MULTI",
    ).upper()

    lines = [
        "🧪 EL LABORATORIO — RADAR",
        "",
        f"💠 {asset}",
        f"💰 Precio: ${price}",
        f"⏱ Marco: {timeframe}",
        "",
        f"🎯 DECISIÓN: {_decision_label(decision)}",
        f"📊 Score técnico: {technical_score}",
        f"🧠 Confianza: {confidence}",
        f"📈 Tendencia: {trend_quality}",
        f"🔗 Alineación: {alignment}",
        f"✅ Confirmación: {confirmation}",
        f"🌐 Régimen: {regime}",
        f"⚠️ Riesgo: {risk}",
        f"🧭 Sesgo: {bias}",
        "",
        f"📝 Motivo: {reason}",
    ]

    entry_zone = _optional_text(
        payload.get("entry_zone")
    )

    invalidation = _optional_text(
        payload.get("invalidation")
    )

    stop = _optional_text(
        payload.get("stop")
    )

    tp1 = _optional_text(
        payload.get("tp1")
    )

    tp2 = _optional_text(
        payload.get("tp2")
    )

    tp3 = _optional_text(
        payload.get("tp3")
    )

    risk_reward = _number(
        payload.get("risk_reward")
    )

    has_trade_plan = any(
        value is not None
        for value in (
            entry_zone,
            invalidation,
            stop,
            tp1,
            tp2,
            tp3,
            risk_reward,
        )
    )

    if has_trade_plan:

        lines.extend(
            [
                "",
                "🎯 PLAN OPERATIVO",
            ]
        )

        if entry_zone is not None:
            lines.append(
                f"Entrada: {entry_zone}"
            )

        if invalidation is not None:
            lines.append(
                f"Invalidación: {invalidation}"
            )

        if stop is not None:
            lines.append(
                f"Stop: {stop}"
            )

        if tp1 is not None:
            lines.append(
                f"TP1: {tp1}"
            )

        if tp2 is not None:
            lines.append(
                f"TP2: {tp2}"
            )

        if tp3 is not None:
            lines.append(
                f"TP3: {tp3}"
            )

        if risk_reward is not None:
            lines.append(
                f"R:R TP2: {risk_reward:.2f}:1"
            )

    confirmations = _items(
        payload.get(
            "confirmations"
        )
    )

    blockers = _items(
        payload.get(
            "blockers"
        )
    )

    warnings = _items(
        payload.get(
            "warnings"
        )
    )

    if confirmations:

        lines.extend(
            [
                "",
                "✅ CONFIRMACIONES",
            ]
        )

        for item in confirmations[:5]:
            lines.append(
                f"• {item}"
            )

    if blockers:

        lines.extend(
            [
                "",
                "⛔ BLOQUEADORES",
            ]
        )

        for item in blockers[:5]:
            lines.append(
                f"• {item}"
            )

    if warnings:

        lines.extend(
            [
                "",
                "⚠️ ADVERTENCIAS",
            ]
        )

        for item in warnings[:5]:
            lines.append(
                f"• {item}"
            )

    lines.extend(
        [
            "",
            "━━━━━━━━━━━━━━━━",
            "⚠️ Radar informativo. "
            "No garantiza resultados.",
        ]
    )

    return "\n".join(lines)


def build_alert(
    asset: str,
    price: float,
    decision: Mapping[str, Any],
    strategy: Mapping[str, Any] | None = None,
    risk: Mapping[str, Any] | None = None,
    timeframe: str = "MULTI",
    generated_at: str | None = None,
) -> dict[str, Any]:

    payload = build_alert_payload(
        asset=asset,
        price=price,
        decision=decision,
        strategy=strategy,
        risk=risk,
        timeframe=timeframe,
        generated_at=generated_at,
    )

    return {
        "payload": payload,
        "message": format_alert(
            payload
        ),
    }