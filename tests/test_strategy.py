from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Mapping


class StrategyError(Exception):
    """Error base del motor de estrategia."""


DECISION_BUY = "BUY"
DECISION_ACCUMULATE = "ACCUMULATE"
DECISION_WAIT = "WAIT_CONFIRMATION"
DECISION_SPECULATIVE = "SPECULATIVE"
DECISION_AVOID = "AVOID"


@dataclass(frozen=True)
class StrategyResult:
    decision: str
    bias: str
    confidence: float
    reason: str
    blockers: tuple[str, ...] = ()
    confirmations: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalize(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip().upper()


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

    if number != number:
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


def _get(
    data: Mapping[str, Any],
    *names: str,
    default: Any = None,
) -> Any:
    for name in names:
        if name in data:
            return data[name]

    return default


def _is_bullish(value: Any) -> bool:
    return _normalize(value) in {
        "BULLISH",
        "BULLISH_STRONG",
        "BULLISH_WEAK",
        "UPTREND",
        "ALCISTA",
        "UP",
        "LONG",
    }


def _is_bearish(value: Any) -> bool:
    return _normalize(value) in {
        "BEARISH",
        "BEARISH_STRONG",
        "BEARISH_WEAK",
        "DOWNTREND",
        "BAJISTA",
        "DOWN",
        "SHORT",
    }


def _is_neutral(value: Any) -> bool:
    return _normalize(value) in {
        "",
        "NEUTRAL",
        "NEUTRAL_BULLISH",
        "NEUTRAL_BEARISH",
        "SIDEWAYS",
        "LATERAL",
    }


def _confirmed_breakout(
    structure: Mapping[str, Any],
) -> bool:
    return bool(
        _get(
            structure,
            "confirmed_breakout",
            "is_confirmed_breakout",
            default=False,
        )
    )


def _potential_breakout(
    structure: Mapping[str, Any],
) -> bool:
    return bool(
        _get(
            structure,
            "potential_breakout",
            "is_potential_breakout",
            default=False,
        )
    )


def _confirmed_breakdown(
    structure: Mapping[str, Any],
) -> bool:
    return bool(
        _get(
            structure,
            "confirmed_breakdown",
            "is_confirmed_breakdown",
            default=False,
        )
    )


def _potential_breakdown(
    structure: Mapping[str, Any],
) -> bool:
    return bool(
        _get(
            structure,
            "potential_breakdown",
            "is_potential_breakdown",
            default=False,
        )
    )


def _data_quality_ok(
    scoring: Mapping[str, Any],
) -> bool:
    completeness = _number(
        _get(
            scoring,
            "data_completeness",
            default=0.0,
        ),
        0.0,
    )

    confidence = _number(
        _get(
            scoring,
            "confidence",
            default=0.0,
        ),
        0.0,
    )

    return (
        completeness >= 70.0
        and confidence >= 50.0
    )


def _has_strong_bearish_conflict(
    scoring: Mapping[str, Any],
    structure: Mapping[str, Any],
) -> bool:
    trend = _get(
        scoring,
        "bias",
        "trend",
    )

    structure_trend = _get(
        structure,
        "trend",
        "bias",
    )

    return (
        _is_bearish(trend)
        or _is_bearish(structure_trend)
        or _confirmed_breakdown(structure)
    )


def _has_strong_bullish_confirmation(
    scoring: Mapping[str, Any],
    structure: Mapping[str, Any],
) -> bool:
    score = _number(
        _get(
            scoring,
            "technical_score",
            default=50.0,
        ),
        50.0,
    )

    confidence = _number(
        _get(
            scoring,
            "confidence",
            default=0.0,
        ),
        0.0,
    )

    trend = _get(
        scoring,
        "bias",
        "trend",
    )

    structure_trend = _get(
        structure,
        "trend",
        "bias",
    )

    return (
        score >= 65.0
        and confidence >= 70.0
        and (
            _is_bullish(trend)
            or _is_bullish(structure_trend)
            or _confirmed_breakout(structure)
        )
    )


def evaluate_strategy(
    scoring: Mapping[str, Any],
    structure: Mapping[str, Any] | None = None,
    indicators: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Convierte scoring + estructura + indicadores
    en una decisión operativa.

    Reglas principales:

    1. RSI sobrevendido por sí solo NO genera compra.
    2. Una ruptura potencial NO equivale a una ruptura confirmada.
    3. Una estructura bajista fuerte puede bloquear una compra.
    4. Datos insuficientes bloquean entradas.
    5. La confianza se ajusta según el contexto.
    """

    if not isinstance(scoring, Mapping):
        raise TypeError(
            "scoring debe ser un Mapping."
        )

    if structure is None:
        structure = {}

    if indicators is None:
        indicators = {}

    if not isinstance(structure, Mapping):
        raise TypeError(
            "structure debe ser un Mapping."
        )

    if not isinstance(indicators, Mapping):
        raise TypeError(
            "indicators debe ser un Mapping."
        )

    technical_score = _number(
        _get(
            scoring,
            "technical_score",
            default=50.0,
        ),
        50.0,
    )

    confidence = _number(
        _get(
            scoring,
            "confidence",
            default=0.0,
        ),
        0.0,
    )

    bias = _normalize(
        _get(
            scoring,
            "bias",
            "trend",
        )
    )

    rsi = _number(
        _get(
            indicators,
            "rsi14",
            "rsi",
        )
    )

    momentum = _number(
        _get(
            indicators,
            "momentum10",
            "momentum",
        )
    )

    blockers: list[str] = []
    confirmations: list[str] = []

    # =========================================================
    # 1. CALIDAD DE DATOS
    # =========================================================

    data_quality_ok = _data_quality_ok(
        scoring
    )

    if not data_quality_ok:
        blockers.append(
            "Datos o confianza insuficientes"
        )

    # =========================================================
    # 2. ESTRUCTURA DE MERCADO
    # =========================================================

    confirmed_breakout = _confirmed_breakout(
        structure
    )

    potential_breakout = _potential_breakout(
        structure
    )

    confirmed_breakdown = _confirmed_breakdown(
        structure
    )

    potential_breakdown = _potential_breakdown(
        structure
    )

    if confirmed_breakout:
        confirmations.append(
            "Ruptura estructural confirmada"
        )

    if potential_breakout and not confirmed_breakout:
        confirmations.append(
            "Ruptura potencial"
        )

    if confirmed_breakdown:
        blockers.append(
            "Ruptura bajista confirmada"
        )

    if potential_breakdown and not confirmed_breakdown:
        blockers.append(
            "Ruptura bajista potencial"
        )

    # =========================================================
    # 3. CONFLICTO BAJISTA
    # =========================================================

    bearish_conflict = _has_strong_bearish_conflict(
        scoring,
        structure,
    )

    # =========================================================
    # 4. CONFIRMACIÓN ALCISTA
    # =========================================================

    bullish_confirmation = _has_strong_bullish_confirmation(
        scoring,
        structure,
    )

    # =========================================================
    # 5. SOBREVENTA SIN CONFIRMACIÓN
    # =========================================================

    oversold_without_confirmation = (
        rsi is not None
        and rsi < 30.0
        and not confirmed_breakout
        and not bullish_confirmation
    )

    if oversold_without_confirmation:
        blockers.append(
            "RSI sobrevendido sin confirmación alcista"
        )

    # =========================================================
    # 6. MOMENTUM
    # =========================================================

   