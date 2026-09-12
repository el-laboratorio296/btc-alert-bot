from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Mapping


class StrategyError(Exception):
    """Error base del motor de estrategia."""


# ============================================================
# DECISIONES
# ============================================================

DECISION_BUY = "BUY"
DECISION_ACCUMULATE = "ACCUMULATE"
DECISION_WAIT = "WAIT_CONFIRMATION"
DECISION_SPECULATIVE = "SPECULATIVE"
DECISION_AVOID = "AVOID"


# ============================================================
# RESULTADO
# ============================================================

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


# ============================================================
# UTILIDADES
# ============================================================

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


# ============================================================
# DIRECCIÓN
# ============================================================

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


# ============================================================
# ESTRUCTURA
# ============================================================

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


# ============================================================
# CALIDAD DE DATOS
# ============================================================

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


# ============================================================
# CONFLICTO BAJISTA
# ============================================================

def _has_strong_bearish_conflict(
    scoring: Mapping[str, Any],
    structure: Mapping[str, Any],
) -> bool:
    scoring_bias = _get(
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
        _is_bearish(scoring_bias)
        or _is_bearish(structure_trend)
        or _confirmed_breakdown(structure)
    )


# ============================================================
# CONFIRMACIÓN ALCISTA
# ============================================================

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

    scoring_bias = _get(
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
            _is_bullish(scoring_bias)
            or _is_bullish(structure_trend)
            or _confirmed_breakout(structure)
        )
    )


# ============================================================
# MOTOR PRINCIPAL
# ============================================================

def evaluate_strategy(
    scoring: Mapping[str, Any],
    structure: Mapping[str, Any] | None = None,
    indicators: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Convierte scoring + estructura + indicadores
    en una decisión operativa.

    Principios:

    - Una ruptura potencial NO es una ruptura confirmada.
    - RSI sobrevendido NO significa compra automática.
    - Un breakdown confirmado bloquea entradas largas.
    - Datos insuficientes bloquean entradas.
    - Los conflictos estructurales tienen prioridad.
    """

    # --------------------------------------------------------
    # VALIDACIÓN
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # DATOS PRINCIPALES
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # LISTAS EXPLICATIVAS
    # --------------------------------------------------------

    blockers: list[str] = []
    confirmations: list[str] = []

    # --------------------------------------------------------
    # ESTRUCTURA
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # CONFIRMACIONES
    # --------------------------------------------------------

    if confirmed_breakout:
        confirmations.append(
            "Ruptura estructural confirmada"
        )

    if (
        potential_breakout
        and not confirmed_breakout
    ):
        confirmations.append(
            "Ruptura potencial"
        )

    # --------------------------------------------------------
    # BLOQUEADORES
    # --------------------------------------------------------

    if confirmed_breakdown:
        blockers.append(
            "Ruptura bajista confirmada"
        )

    if (
        potential_breakdown
        and not confirmed_breakdown
    ):
        blockers.append(
            "Ruptura bajista potencial"
        )

    # --------------------------------------------------------
    # CALIDAD
    # --------------------------------------------------------

    data_quality_ok = _data_quality_ok(
        scoring
    )

    if not data_quality_ok:
        blockers.append(
            "Datos o confianza insuficientes"
        )

    # --------------------------------------------------------
    # CONFLICTO BAJISTA
    # --------------------------------------------------------

    bearish_conflict = _has_strong_bearish_conflict(
        scoring,
        structure,
    )

    # --------------------------------------------------------
    # CONFIRMACIÓN ALCISTA
    # --------------------------------------------------------

    bullish_confirmation = _has_strong_bullish_confirmation(
        scoring,
        structure,
    )

    # ========================================================
    # SOBREVENTA
    # ========================================================

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

    # ========================================================
    # MOMENTUM
    # ========================================================

    weak_momentum = (
        momentum is not None
        and momentum < -2.0
    )

    strong_momentum = (
        momentum is not None
        and momentum > 2.0
    )

    if strong_momentum:
        confirmations.append(
            "Momentum favorable"
        )

    if weak_momentum:
        blockers.append(
            "Momentum débil"
        )

    # ========================================================
    # DECISIÓN
    # ========================================================

    decision = DECISION_WAIT

    reason = (
        "No existe confirmación suficiente."
    )

    # --------------------------------------------------------
    # PRIORIDAD 1
    # BREAKDOWN CONFIRMADO
    # --------------------------------------------------------

    if confirmed_breakdown:
        decision = DECISION_AVOID

        reason = (
            "Estructura bajista confirmada; "
            "no se recomienda buscar entradas largas."
        )

    # --------------------------------------------------------
    # PRIORIDAD 2
    # CALIDAD DE DATOS
    # --------------------------------------------------------

    elif not data_quality_ok:
        decision = DECISION_WAIT

        reason = (
            "La calidad de los datos o la confianza "
            "no permite una decisión operativa."
        )

    # --------------------------------------------------------
    # PRIORIDAD 3
    # BREAKOUT POTENCIAL
    #
    # CRÍTICO:
    #
    # Aunque technical_score >= 65
    # y confidence >= 70,
    # NO se permite BUY mientras el breakout
    # siga siendo solamente potencial.
    # --------------------------------------------------------

    elif (
        potential_breakout
        and not confirmed_breakout
    ):
        decision = DECISION_WAIT

        reason = (
            "Existe una ruptura potencial, pero "
            "todavía no está confirmada. "
            "Esperar cierre y confirmación."
        )

    # --------------------------------------------------------
    # PRIORIDAD 4
    # SOBREVENTA SIN REVERSIÓN
    # --------------------------------------------------------

    elif oversold_without_confirmation:
        decision = DECISION_WAIT

        reason = (
            "El mercado está sobrevendido, pero "
            "no existe confirmación de reversión."
        )

    # --------------------------------------------------------
    # PRIORIDAD 5
    # CONFLICTO BAJISTA
    # --------------------------------------------------------

    elif (
        bearish_conflict
        and not confirmed_breakout
    ):
        decision = DECISION_AVOID

        reason = (
            "Existe conflicto bajista con la "
            "estructura o tendencia."
        )

    # --------------------------------------------------------
    # PRIORIDAD 6
    # BUY CONFIRMADO
    # --------------------------------------------------------

    elif bullish_confirmation:
        decision = DECISION_BUY

        reason = (
            "Score, confianza y estructura "
            "presentan confirmación alcista."
        )

    # --------------------------------------------------------
    # PRIORIDAD 7
    # BREAKOUT CONFIRMADO MODERADO
    # --------------------------------------------------------

    elif (
        confirmed_breakout
        and technical_score >= 55.0
        and confidence >= 60.0
    ):
        decision = DECISION_ACCUMULATE

        reason = (
            "Ruptura confirmada con condiciones "
            "favorables, pero sin suficiente fuerza "
            "para una entrada agresiva."
        )

    # --------------------------------------------------------
    # PRIORIDAD 8
    # SETUP ESPECULATIVO
    # --------------------------------------------------------

    elif (
        technical_score >= 55.0
        and confidence >= 55.0
        and strong_momentum
        and not bearish_conflict
    ):
        decision = DECISION_SPECULATIVE

        reason = (
            "Condiciones favorables, pero todavía "
            "sin confirmación suficiente para una "
            "entrada principal."
        )

    # --------------------------------------------------------
    # PRIORIDAD 9
    # SCORE MUY DÉBIL
    # --------------------------------------------------------

    elif technical_score <= 35.0:
        decision = DECISION_AVOID

        reason = (
            "Score técnico demasiado débil."
        )

    # ========================================================
    # BIAS FINAL
    # ========================================================

    if decision in {
        DECISION_BUY,
        DECISION_ACCUMULATE,
        DECISION_SPECULATIVE,
    }:
        result_bias = "BULLISH"

    elif decision == DECISION_AVOID:
        result_bias = "BEARISH"

    else:
        if _is_bullish(bias):
            result_bias = "BULLISH"

        elif _is_bearish(bias):
            result_bias = "BEARISH"

        else:
            result_bias = "NEUTRAL"

    # ========================================================
    # CONFIANZA FINAL
    # ========================================================

    final_confidence = confidence

    if oversold_without_confirmation:
        final_confidence -= 10.0

    if confirmed_breakout:
        final_confidence += 5.0

    if confirmed_breakdown:
        final_confidence -= 15.0

    if weak_momentum:
        final_confidence -= 5.0

    if (
        potential_breakout
        and not confirmed_breakout
    ):
        final_confidence -= 5.0

    final_confidence = _clamp(
        final_confidence
    )

    # ========================================================
    # RESULTADO
    # ========================================================

    return StrategyResult(
        decision=decision,
        bias=result_bias,
        confidence=round(
            final_confidence,
            4,
        ),
        reason=reason,
        blockers=tuple(blockers),
        confirmations=tuple(confirmations),
    ).to_dict()


# ============================================================
# ALIAS PÚBLICO
# ============================================================

def strategy_score(
    scoring: Mapping[str, Any],
    structure: Mapping[str, Any] | None = None,
    indicators: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Alias público para mantener una API sencilla
    y facilitar futuras integraciones.
    """

    return evaluate_strategy(
        scoring=scoring,
        structure=structure,
        indicators=indicators,
    )