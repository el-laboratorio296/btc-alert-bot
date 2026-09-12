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

# Distribución del score técnico:
#
# Tendencia    30%
# Momentum     20%
# Estructura   25%
# Volumen      15%
# Volatilidad  10%
#
# TOTAL        100%

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
    """
    Limita un valor al rango indicado.
    """

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

    Devuelve default cuando el valor:
    - es None
    - no es numérico
    - es NaN
    - es infinito
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
    """
    Normaliza texto para comparaciones.
    """

    if value is None:
        return ""

    return str(value).strip().upper()


def _score_from_centered_value(
    value: float,
    scale: float,
) -> float:
    """
    Convierte un valor centrado en cero a score 0-100.

    Ejemplo con scale=5:

        -5  -> 0
         0  -> 50
        +5  -> 100
    """

    if scale <= 0:
        raise ValueError(
            "scale debe ser mayor que cero."
        )

    number = _safe_float(value)

    if number is None:
        return SCORE_NEUTRAL

    score = SCORE_NEUTRAL + (
        number / scale
    ) * 50.0

    return _clamp(score)


# ============================================================
# SCORE DE TENDENCIA
# ============================================================

def score_trend(
    trend: Any,
) -> float:
    """
    Convierte la tendencia EMA en un score 0-100.
    """

    normalized = _normalize_text(trend)

    scores = {
        "BULLISH_STRONG": 95.0,
        "BULLISH": 90.0,
        "BULLISH_WEAK": 72.0,

        "NEUTRAL_BULLISH": 60.0,
        "NEUTRAL": 50.0,
        "NEUTRAL_BEARISH": 40.0,

        "BEARISH_WEAK": 28.0,
        "BEARISH": 10.0,
        "BEARISH_STRONG": 5.0,

        "INSUFFICIENT_DATA": 50.0,
    }

    return scores.get(
        normalized,
        SCORE_NEUTRAL,
    )


# ============================================================
# SCORE RSI
# ============================================================

def score_rsi(
    rsi_value: float | None,
) -> float:
    """
    Evalúa RSI.

    IMPORTANTE:

    RSI sobrevendido NO significa automáticamente compra.

    Un activo puede permanecer sobrevendido durante una
    tendencia bajista fuerte.
    """

    value = _safe_float(
        rsi_value
    )

    if value is None:
        return SCORE_NEUTRAL

    value = _clamp(
        value,
        0.0,
        100.0,
    )

    # Zona equilibrada.
    if 45.0 <= value <= 60.0:
        return 50.0

    # Momentum alcista moderado.
    if 60.0 < value <= 70.0:
        return 58.0

    # Sobrecompra moderada.
    if 70.0 < value <= 80.0:
        return 52.0

    # Sobrecompra extrema.
    if value > 80.0:
        return 42.0

    # Debilidad moderada.
    if 35.0 <= value < 45.0:
        return 45.0

    # Sobreventa.
    #
    # No se interpreta como compra automática.
    if 25.0 <= value < 35.0:
        return 48.0

    # Sobreventa extrema.
    if value < 25.0:
        return 43.0

    return 50.0


# ============================================================
# SCORE MOMENTUM
# ============================================================

def score