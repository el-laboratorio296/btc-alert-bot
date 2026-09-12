from __future__ import annotations

import math
from typing import Any, Mapping


class ScoringError(Exception):
    """Error base del módulo de scoring."""


# ============================================================
# CONSTANTES
# ============================================================

SCORE_MIN = 0.0
SCORE_MAX = 100.0
SCORE_NEUTRAL = 50.0

# Pesos principales.
#
# Tendencia    30%
# Momentum     20%
# Estructura   25%
# Volumen      15%
# Volatilidad  10%
#
# Total = 100%
WEIGHT_TREND = 0.30
WEIGHT_MOMENTUM = 0.20
WEIGHT_STRUCTURE = 0.25
WEIGHT_VOLUME = 0.15
WEIGHT_VOLATILITY = 0.10


# ============================================================
# UTILIDADES INTERNAS
# ============================================================

def _clamp(
    value: float,
    minimum: float = SCORE_MIN,
    maximum: float = SCORE_MAX,
) -> float:
    """Limita un valor numérico a un rango."""

    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ScoringError(
            "El valor del scoring debe ser numérico."
        ) from exc

    if not math.isfinite(number):
        raise ScoringError(
            "El valor del scoring debe ser finito."
        )

    return max(
        minimum,
        min(maximum, number),
    )


def _safe_float(
    value: Any,
    default: float | None = None,
) -> float | None:
    """
    Conversión segura a float.

    Devuelve default cuando el dato es:
    - None
    - no numérico
    - NaN
    - infinito
    """

    if value is None:
        return default

    try:
        number = float(value)
    except (TypeError, ValueError):
        return default

    if not math.isfinite(number):
        return default

    return number


def _normalize_text(
    value: Any,
) -> str:
    """Normaliza texto para comparaciones internas."""

    if value is None:
        return ""

    return str(value).strip().upper()


def _score_from_centered_value(
    value: float,
    scale: float,
) -> float:
    """
    Convierte un valor centrado en cero a 0-100.

        0       -> 50
        +scale  -> 100
        -scale  -> 0
    """

    if scale <= 0:
        raise ValueError(
            "scale debe ser mayor que cero."
        )

    number = _safe_float(value)

    if number is None:
        return SCORE_NEUTRAL

    score = SCORE_NEUTRAL + (
        (number / scale) * 50.0
    )

    return _clamp(score)


# ============================================================
# SCORE DE TENDENCIA
# ============================================================

def score_trend(
    trend: Any,
) -> float:
    """
    Convierte la clasificación de tendencia EMA
    a un score entre 0 y 100.
    """

    normalized = _normalize_text(trend)

    scores = {
        "BULLISH": 90.0,
        "BULLISH_STRONG": 95.0,
        "BULLISH_WEAK": 72.0,

        "NEUTRAL_BULLISH": 60.0,
        "NEUTRAL": 50.0,
        "NEUTRAL_BEARISH": 40.0,

        "BEARISH