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

# Pesos del score técnico.
#
# IMPORTANTE:
# Los pesos suman 100%.
#
# Tendencia    30%
# Momentum     20%
# Estructura   25%
# Volumen      15%
# Volatilidad  10%
#
# La volatilidad NO determina por sí sola si comprar o vender.
# Funciona principalmente como factor de calidad.
WEIGHT_TREND = 0.30
WEIGHT_MOMENTUM = 0.20
WEIGHT_STRUCTURE = 0.25
WEIGHT_VOLUME = 0.15
WEIGHT_VOLATILITY = 0.10


# ============================================================
# VALIDACIONES Y UTILIDADES
# ============================================================

def _clamp(
    value: float,
    minimum: float = SCORE_MIN,
    maximum: float = SCORE_MAX,
) -> float:
    """Limita un número a un rango."""

    value = float(value)

    if not math.isfinite(value):
        raise ScoringError(
            "El valor del scoring debe ser finito."
        )

    return max(
        minimum,
        min(maximum, value),
    )


def _safe_float(
    value: Any,
    default: float | None = None,
) -> float | None:
    """
    Convierte un valor a float de forma segura.

    None, strings vacíos o valores no numéricos
    devuelven default.
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
    Convierte un valor centrado en cero a score 0-100.

    Ejemplo:
        0     -> 50
        +scale -> 100
        -scale -> 0
    """

    if scale <= 0:
        raise ValueError("scale debe ser mayor que cero.")

    score = SCORE_NEUTRAL + (
        (float(value) / float(scale)) * 50.0
    )

    return _clamp(score)


# ============================================================
# SCORE DE TENDENCIA
# ============================================================

def score_trend(
    trend: Any,
) -> float:
    """
    Convierte la clasificación de tendencia EMA a score 0-100.

    No utiliza el RSI ni momentum.

    Esto evita contar dos veces la misma información.
    """

    normalized = _normalize_text(trend)

    scores = {
        "BULLISH": 90.0,
        "BULLISH_WEAK": 72.0,
        "NEUTRAL_BULLISH": 60.0,
        "NEUTRAL": 50.0,
        "NEUTRAL_BEARISH": 40.0,
        "BEARISH_WEAK": 28.0,
        "BEARISH": 10.0,
        "INSUFFICIENT_DATA": 50.0,
    }

    return scores.get(
        normalized,
        SCORE_NEUTRAL,
    )


# ============================================================
# SCORE DE RSI
# ============================================================

def score_rsi(
    rsi_value: float | None,
) -> float:
    """
    Evalúa RSI sin cometer el error clásico:

        RSI bajo != compra automática.

    La zona central es neutral.

    Un RSI extremadamente alto penaliza compras tardías.
    Un RSI extremadamente bajo tampoco se transforma
    automáticamente en una señal alcista.
    """

    if rsi_value is None:
        return SCORE_NEUTRAL

    rsi_value = _safe_float(rsi_value)

    if rsi_value is None:
        return SCORE_NEUTRAL

    rsi_value = _clamp(
        rsi_value,
        0.0,
        100.0,
    )

    if 45.0 <= rsi_value <= 60.0:
        return 50.0

    if 60.0 < rsi_value <= 70.0:
        return 58.0

    if 70.0 < rsi_value <= 80.0:
        return 52.0

    if rsi_value > 80.0:
        return 42.0

    if 35.0 <= rsi_value < 45.0:
        return 45.0

    if 25.0 <= rsi_value < 35.0:
        return 48.0

    # RSI extremadamente bajo:
    # no se convierte en compra automática.
    if rsi_value < 25.0:
        return 43.0

    return 50.0


# ============================================================
# SCORE DE MOMENTUM
# ============================================================

def score_momentum(
    momentum_value: float | None,
) -> float:
    """
    Evalúa momentum porcentual.

    +5% o más  -> score 100
    0%         -> score 50
    -5% o menos -> score 0

    Se limita deliberadamente para evitar que un movimiento
    extremo domine todo el sistema.
    """

    if momentum_value is None:
        return SCORE_NEUTRAL

    momentum_value = _safe_float(momentum_value)

    if momentum_value is None:
        return SCORE_NEUTRAL

    return _score_from_centered_value(
        momentum_value,
        scale=5.0,
    )


# ============================================================
# SCORE DE MOMENTUM COMPLETO
# ============================================================

def score_momentum_component(
    rsi_value: float | None,
    momentum_value: float | None,
) -> float:
    """
    Combina RSI + momentum.

    RSI:       40%
    Momentum:  60%

    El momentum tiene algo más de peso porque mide dirección
    reciente de precio, mientras RSI puede permanecer extremo
    durante tendencias fuertes.
    """

    rsi_score = score_rsi(rsi_value)
    momentum_score = score_momentum(momentum_value)

    return _clamp(
        (rsi_score * 0.40)
        + (momentum_score * 0.60)
    )


# ============================================================
# SCORE DE VOLUMEN
# ============================================================

def score_volume(
    relative_volume: float | None,
    price_direction: str | None = None,
) -> float:
    """
    Evalúa volumen relativo.

    El volumen alto por sí solo NO es alcista.

    Si existe dirección de la vela:

        volumen alto + vela alcista -> mejora score
        volumen alto + vela bajista -> reduce score

    Esto evita interpretar una venta masiva como compra.
    """

    if relative_volume is None:
        return SCORE_NEUTRAL

    relative_volume = _safe_float(relative_volume)

    if relative_volume is None:
        return SCORE_NEUTRAL

    if relative_volume < 0:
        return SCORE_NEUTRAL

    direction = _normalize_text(price_direction)

    # Volumen muy bajo:
    # poca confirmación.
    if relative_volume < 0.70:
        return 43.0

    if relative_volume < 1.00:
        return 47.0

    if relative_volume < 1.20:
        return 52.0

    if relative_volume < 1.50:
        base_score = 60.0
    elif relative_volume < 2.00:
        base_score = 70.0
    else:
        base_score = 78.0

    if direction in {
        "BEARISH",
        "DOWN",
        "RED",
        "SELL",
    }:
        return _clamp(
            base_score - 15.0
        )

    if direction in {
        "BULLISH",
        "UP",
        "GREEN",
        "BUY",
    }:
        return _clamp(
            base_score + 10.0
        )

    return base_score


# ============================================================
# SCORE DE ESTRUCTURA
# ============================================================

def score_structure(
    structure: Mapping[str, Any] | None,
) -> float:
    """
    Convierte información de estructura de mercado a score.

    El módulo es deliberadamente tolerante con los nombres
    de algunos campos para poder integrarse con structure.py
    sin acoplarlo innecesariamente.

    Prioridad:

        breakout confirmado
        breakdown confirmado
        tendencia estructural
        bias
        confianza estructural
    """

    if structure is None:
        return SCORE_NEUTRAL

    if not isinstance(structure, Mapping):
        raise TypeError(
            "structure debe ser un Mapping."
        )

    breakout = bool(
        structure.get(
            "confirmed_breakout",
            structure.get(
                "is_confirmed_breakout",
                False,
            ),
        )
    )

    breakdown = bool(
        structure.get(
            "confirmed_breakdown",
            structure.get(
                "is_confirmed_breakdown",
                False,
            ),
        )
    )

    potential_breakout = bool(
        structure.get(
            "potential_breakout",
            structure.get(
                "is_potential_breakout",
                False,
            ),
        )
    )

    potential_breakdown = bool(
        structure.get(
            "potential_breakdown",
            structure.get(
                "is_potential_breakdown",
                False,
            ),
        )
    )

    trend = _normalize_text(
        structure.get("trend")
    )

    bias = _normalize_text(
        structure.get("bias")
    )

    score = SCORE_NEUTRAL

    # ========================================================
    # ESTRUCTURA DIRECCIONAL
    # ========================================================

    bullish_terms = {
        "BULLISH",
        "UPTREND",
        "ALCISTA",
        "LONG",
    }

    bearish_terms = {
        "BEARISH",
        "DOWNTREND",
        "BAJISTA",
        "SHORT",
    }

    if trend in bullish_terms:
        score += 15.0
    elif trend in bearish_terms:
        score -= 15.0

    if bias in bullish_terms:
        score += 10.0
    elif bias in bearish_terms:
        score -= 10.0

    # ========================================================
    # RUPTURAS
    # ========================================================

    if breakout:
        score += 20.0

    if breakdown:
        score -= 20.0

    # Una ruptura potencial no vale igual que una confirmada.
    if potential_breakout and not breakout:
        score += 7.0

    if potential_breakdown and not breakdown:
        score -= 7.0

    return _clamp(score)


# ============================================================
# SCORE DE VOLATILIDAD
# ============================================================

def score_volatility(
    atr_percent: float | None,
    volatility_percent: float | None,
) -> float:
    """
    Evalúa la calidad de la volatilidad.

    No intenta decir "alta volatilidad = bajista".

    La pregunta es:

        ¿la volatilidad actual es razonable para tomar
        una decisión técnica?

    Volatilidad excesiva reduce la calidad del score.
    """

    atr = _safe_float(atr_percent)
    historical = _safe_float(volatility_percent)

    available = [
        value
        for value in (
            atr,
            historical,
        )
        if value is not None
        and value >= 0
    ]

    if not available:
        return SCORE_NEUTRAL

    # Utilizamos el promedio de las medidas disponibles.
    current_volatility = sum(
        available
    ) / len(available)

    # Estos límites son deliberadamente conservadores.
    #
    # 0-1%   -> baja
    # 1-2%   -> saludable
    # 2-4%   -> elevada
    # 4-7%   -> muy elevada
    # >7%     -> extrema
    if current_volatility < 1.0:
        return 48.0

    if current_volatility < 2.0:
        return 60.0

    if current_volatility < 4.0:
        return 58.0

    if current_volatility < 7.0:
        return 42.0

    return 25.0


# ============================================================
# SCORE DE INDICADORES
# ============================================================

def calculate_technical_score(
    indicators: Mapping[str, Any],
    structure: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Calcula el score técnico principal.

    Entrada:

        indicators:
            resultado de compute_indicators()

        structure:
            resultado del análisis estructural.

    Salida:

        {
            "technical_score": 0-100,
            "trend_score": 0-100,
            "momentum_score": 0-100,
            "structure_score": 0-100,
            "volume_score": 0-100,
            "volatility_score": 0-100,
            "confidence": 0-100,
            "bias": "BULLISH/NEUTRAL/BEARISH",
            "quality": "...",
        }

    IMPORTANTE:

    technical_score representa sesgo técnico.

    confidence representa cuánta información válida tenemos.

    Son métricas diferentes.
    """

    if not isinstance(indicators, Mapping):
        raise TypeError(
            "indicators debe ser un Mapping."
        )

    # ========================================================
    # COMPONENTES
    # ========================================================

    trend_score = score_trend(
        indicators.get("trend")
    )

    momentum_score = score_momentum_component(
        rsi_value=indicators.get("rsi14"),
        momentum_value=indicators.get("momentum10"),
    )

    structure_score = score_structure(
        structure
    )

    volume_score = score_volume(
        relative_volume=indicators.get(
            "relative_volume20"
        ),
        price_direction=(
            indicators.get(
                "candle_direction"
            )
        ),
    )

    volatility_score = score_volatility(
        atr_percent=indicators.get(
            "atr_percent"
        ),
        volatility_percent=indicators.get(
            "volatility20"
        ),
    )

    # ========================================================
    # SCORE PONDERADO
    # ========================================================

    technical_score = (
        trend_score * WEIGHT_TREND
        + momentum_score * WEIGHT_MOMENTUM
        + structure_score * WEIGHT_STRUCTURE
        + volume_score * WEIGHT_VOLUME
        + volatility_score * WEIGHT_VOLATILITY
    )

    technical_score = _clamp(
        technical_score
    )

    # ========================================================
    # CALIDAD DE DATOS
    # ========================================================

    required_fields = (
        "price",
        "ema20",
        "ema50",
        "rsi14",
        "atr14",
        "momentum10",
        "relative_volume20",
    )

    available_count = sum(
        1
        for field in required_fields
        if indicators.get(field) is not None
    )

    data_completeness = (
        available_count
        / len(required_fields)
    ) * 100.0

    # ========================================================
    # CONFIRMACIÓN DE VELA
    # ========================================================

    last_candle_closed = indicators.get(
        "last_candle_closed"
    )

    if last_candle_closed is False:
        closed_factor = 0.70
    elif last_candle_closed is True:
        closed_factor = 1.00
    else:
        # Si no sabemos si la vela está cerrada,
        # reducimos confianza.
        closed_factor = 0.85

    # ========================================================
    # CONSISTENCIA ENTRE COMPONENTES
    # ========================================================

    component_scores = (
        trend_score,
        momentum_score,
        structure_score,
        volume_score,
    )

    bullish_components = sum(
        1
        for value in component_scores
        if value >= 60.0
    )

    bearish_components = sum(
        1
        for value in component_scores
        if value <= 40.0
    )

    directional_consistency = (
        max(
            bullish_components,
            bearish_components,
        )
        / len(component_scores)
    ) * 100.0

    # ========================================================
    # CONFIANZA
    # ========================================================

    confidence = (
        data_completeness * 0.50
        + directional_consistency * 0.30
        + (closed_factor * 100.0) * 0.20
    )

    confidence = _clamp(
        confidence
    )

    # ========================================================
    # BIAS
    # ========================================================

    if technical_score >= 65.0:
        bias = "BULLISH"

    elif technical_score <= 35.0:
        bias = "BEARISH"

    else:
        bias = "NEUTRAL"

    # ========================================================
    # CALIDAD
    # ========================================================

    if confidence >= 80.0:
        quality = "HIGH"

    elif confidence >= 60.0:
        quality = "MEDIUM"

    elif confidence >= 40.0:
        quality = "LOW"

    else:
        quality = "VERY_LOW"

    # ========================================================
    # SCORE DIRECCIONAL
    # ========================================================

    if (
        technical_score >= 65.0
        and confidence >= 70.0
    ):
        signal = "BULLISH_CONFIRMED"

    elif (
        technical_score <= 35.0
        and confidence >= 70.0
    ):
        signal = "BEARISH_CONFIRMED"

    elif technical_score > 55.0:
        signal = "BULLISH_BIAS"

    elif technical_score < 45.0:
        signal = "BEARISH_BIAS"

    else:
        signal = "NEUTRAL"

    return {
        "technical_score": round(
            technical_score,
            4,
        ),

        "trend_score": round(
            trend_score,
            4,
        ),

        "momentum_score": round(
            momentum_score,
            4,
        ),

        "structure_score": round(
            structure_score,
            4,
        ),

        "volume_score": round(
            volume_score,
            4,
        ),

        "volatility_score": round(
            volatility_score,
            4,
        ),

        "confidence": round(
            confidence,
            4,
        ),

        "data_completeness": round(
            data_completeness,
            4,
        ),

        "directional_consistency": round(
            directional_consistency,
            4,
        ),

        "bias": bias,

        "signal": signal,

        "quality": quality,

        "components": {
            "trend": round(
                trend_score,
                4,
            ),
            "momentum": round(
                momentum_score,
                4,
            ),
            "structure": round(
                structure_score,
                4,
            ),
            "volume": round(
                volume_score,
                4,
            ),
            "volatility": round(
                volatility_score,
                4,
            ),
        },
    }


# ============================================================
# ALIAS
# ============================================================

def score_indicators(
    indicators: Mapping[str, Any],
    structure: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Alias público para calculate_technical_score().
    """

    return calculate_technical_score(
        indicators=indicators,
        structure=structure,
    )