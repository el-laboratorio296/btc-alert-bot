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

def score_momentum(
    momentum_value: float | None,
) -> float:
    """
    Convierte momentum porcentual en score.

    +5% -> 100
     0% -> 50
    -5% -> 0

    Movimientos superiores a ese rango se limitan.
    """

    value = _safe_float(
        momentum_value
    )

    if value is None:
        return SCORE_NEUTRAL

    return _score_from_centered_value(
        value,
        scale=5.0,
    )


# ============================================================
# COMPONENTE MOMENTUM
# ============================================================

def score_momentum_component(
    rsi_value: float | None,
    momentum_value: float | None,
) -> float:
    """
    Combina RSI y momentum.

    RSI       = 40%
    Momentum  = 60%
    """

    rsi_score = score_rsi(
        rsi_value
    )

    momentum_score = score_momentum(
        momentum_value
    )

    return _clamp(
        rsi_score * 0.40
        + momentum_score * 0.60
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

    Regla fundamental:

        VOLUMEN ALTO != ALCISTA

    El volumen debe interpretarse junto con la dirección
    del movimiento.

    Esto evita exactamente el problema que encontramos:
    relative_volume20 = 3.0 no puede convertirse
    automáticamente en una señal alcista.
    """

    volume = _safe_float(
        relative_volume
    )

    if volume is None:
        return SCORE_NEUTRAL

    if volume < 0:
        return SCORE_NEUTRAL

    direction = _normalize_text(
        price_direction
    )

    # --------------------------------------------------------
    # VOLUMEN MUY BAJO
    # --------------------------------------------------------

    if volume < 0.70:
        base_score = 43.0

    # --------------------------------------------------------
    # VOLUMEN BAJO / NORMAL
    # --------------------------------------------------------

    elif volume < 1.00:
        base_score = 47.0

    elif volume < 1.20:
        base_score = 52.0

    # --------------------------------------------------------
    # VOLUMEN ELEVADO
    # --------------------------------------------------------

    elif volume < 1.50:
        base_score = 58.0

    elif volume < 2.00:
        base_score = 65.0

    # --------------------------------------------------------
    # VOLUMEN EXTREMO
    # --------------------------------------------------------

    else:
        base_score = 60.0

    # --------------------------------------------------------
    # MOVIMIENTO ALCISTA
    # --------------------------------------------------------

    if direction in {
        "BULLISH",
        "UP",
        "GREEN",
        "BUY",
        "ALCISTA",
    }:
        if volume >= 2.00:
            return 80.0

        return _clamp(
            base_score + 10.0
        )

    # --------------------------------------------------------
    # MOVIMIENTO BAJISTA
    # --------------------------------------------------------

    if direction in {
        "BEARISH",
        "DOWN",
        "RED",
        "SELL",
        "BAJISTA",
    }:
        return _clamp(
            base_score - 15.0
        )

    # --------------------------------------------------------
    # DIRECCIÓN DESCONOCIDA
    # --------------------------------------------------------
    #
    # No asumimos que volumen alto significa compra.
    #

    return _clamp(
        min(base_score, 65.0)
    )


# ============================================================
# SCORE DE ESTRUCTURA
# ============================================================

def score_structure(
    structure: Mapping[str, Any] | None,
) -> float:
    """
    Convierte estructura de mercado en score 0-100.

    Considera:

    - tendencia
    - bias
    - breakout confirmado
    - breakdown confirmado
    - breakout potencial
    - breakdown potencial
    """

    if structure is None:
        return SCORE_NEUTRAL

    if not isinstance(
        structure,
        Mapping,
    ):
        raise TypeError(
            "structure debe ser un Mapping."
        )

    confirmed_breakout = bool(
        structure.get(
            "confirmed_breakout",
            structure.get(
                "is_confirmed_breakout",
                False,
            ),
        )
    )

    confirmed_breakdown = bool(
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

    # --------------------------------------------------------
    # TENDENCIA
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # BIAS
    # --------------------------------------------------------

    if bias in bullish_terms:
        score += 10.0

    elif bias in bearish_terms:
        score -= 10.0

    # --------------------------------------------------------
    # BREAKOUT CONFIRMADO
    # --------------------------------------------------------

    if confirmed_breakout:
        score += 20.0

    # --------------------------------------------------------
    # BREAKDOWN CONFIRMADO
    # --------------------------------------------------------

    if confirmed_breakdown:
        score -= 20.0

    # --------------------------------------------------------
    # BREAKOUT POTENCIAL
    # --------------------------------------------------------

    if (
        potential_breakout
        and not confirmed_breakout
    ):
        score += 7.0

    # --------------------------------------------------------
    # BREAKDOWN POTENCIAL
    # --------------------------------------------------------

    if (
        potential_breakdown
        and not confirmed_breakdown
    ):
        score -= 7.0

    return _clamp(
        score
    )


# ============================================================
# SCORE VOLATILIDAD
# ============================================================

def score_volatility(
    atr_percent: float | None,
    volatility_percent: float | None,
) -> float:
    """
    Evalúa la calidad de las condiciones de volatilidad.

    La volatilidad NO determina por sí sola la dirección.

    Volatilidad demasiado alta = mayor riesgo.
    """

    atr = _safe_float(
        atr_percent
    )

    historical = _safe_float(
        volatility_percent
    )

    values = [
        value
        for value in (
            atr,
            historical,
        )
        if value is not None
        and value >= 0
    ]

    if not values:
        return SCORE_NEUTRAL

    current_volatility = (
        sum(values)
        / len(values)
    )

    # --------------------------------------------------------
    # MUY BAJA
    # --------------------------------------------------------

    if current_volatility < 1.0:
        return 48.0

    # --------------------------------------------------------
    # NORMAL
    # --------------------------------------------------------

    if current_volatility < 2.0:
        return 60.0

    # --------------------------------------------------------
    # ELEVADA
    # --------------------------------------------------------

    if current_volatility < 4.0:
        return 58.0

    # --------------------------------------------------------
    # MUY ELEVADA
    # --------------------------------------------------------

    if current_volatility < 7.0:
        return 42.0

    # --------------------------------------------------------
    # EXTREMA
    # --------------------------------------------------------

    return 25.0


# ============================================================
# SCORE TÉCNICO PRINCIPAL
# ============================================================

def calculate_technical_score(
    indicators: Mapping[str, Any],
    structure: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Calcula el score técnico principal del Radar.

    El resultado contiene:

        technical_score
        trend_score
        momentum_score
        structure_score
        volume_score
        volatility_score
        confidence
        data_completeness
        directional_consistency
        bias
        signal
        quality
        components

    IMPORTANTE:

        technical_score != confidence

    technical_score:
        representa el sesgo técnico.

    confidence:
        representa la calidad y consistencia de la lectura.
    """

    if not isinstance(
        indicators,
        Mapping,
    ):
        raise TypeError(
            "indicators debe ser un Mapping."
        )

    # ========================================================
    # 1. TENDENCIA
    # ========================================================

    trend_score = score_trend(
        indicators.get("trend")
    )

    # ========================================================
    # 2. MOMENTUM
    # ========================================================

    momentum_score = score_momentum_component(
        rsi_value=indicators.get(
            "rsi14"
        ),
        momentum_value=indicators.get(
            "momentum10"
        ),
    )

    # ========================================================
    # 3. ESTRUCTURA
    # ========================================================

    structure_score = score_structure(
        structure
    )

    # ========================================================
    # 4. DIRECCIÓN
    # ========================================================

    candle_direction = indicators.get(
        "candle_direction"
    )

    # Si no existe dirección de vela utilizamos
    # la tendencia como contexto.
    if candle_direction is None:
        candle_direction = indicators.get(
            "trend"
        )

    # ========================================================
    # 5. VOLUMEN
    # ========================================================

    volume_score = score_volume(
        relative_volume=indicators.get(
            "relative_volume20"
        ),
        price_direction=candle_direction,
    )

    # ========================================================
    # 6. VOLATILIDAD
    # ========================================================

    volatility_score = score_volatility(
        atr_percent=indicators.get(
            "atr_percent"
        ),
        volatility_percent=indicators.get(
            "volatility20"
        ),
    )

    # ========================================================
    # 7. SCORE PONDERADO
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
    # 8. PROTECCIÓN DE DIRECCIÓN
    # ========================================================
    #
    # Si la tendencia y momentum son claramente bajistas,
    # el score no debe terminar artificialmente en neutral
    # por componentes secundarios.
    #
    # Lo mismo para una tendencia alcista claramente confirmada.
    #

    trend_text = _normalize_text(
        indicators.get("trend")
    )

    if (
        trend_text in {
            "BEARISH",
            "BEARISH_STRONG",
        }
        and momentum_score <= 40.0
        and technical_score > 44.0
    ):
        technical_score = 44.0

    if (
        trend_text in {
            "BULLISH",
            "BULLISH_STRONG",
        }
        and momentum_score >= 60.0
        and technical_score < 56.0
    ):
        technical_score = 56.0

    technical_score = _clamp(
        technical_score
    )

    # ========================================================
    # 9. COMPLETITUD DE DATOS
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
    # 10. VELA CERRADA
    # ========================================================

    last_candle_closed = indicators.get(
        "last_candle_closed"
    )

    if last_candle_closed is True:
        closed_factor = 1.00

    elif last_candle_closed is False:
        # Una vela abierta todavía puede cambiar.
        closed_factor = 0.70

    else:
        closed_factor = 0.85

    # ========================================================
    # 11. CONSISTENCIA DIRECCIONAL
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
    # 12. CONFIANZA
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
    # 13. BIAS
    # ========================================================

    if technical_score >= 65.0:
        bias = "BULLISH"

    elif technical_score <= 35.0:
        bias = "BEARISH"

    else:
        bias = "NEUTRAL"

    # ========================================================
    # 14. CALIDAD
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
    # 15. SEÑAL
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

    # ========================================================
    # 16. RESULTADO
    # ========================================================

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
# ALIAS PÚBLICO
# ============================================================

def score_indicators(
    indicators: Mapping[str, Any],
    structure: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Alias semántico de calculate_technical_score().
    """

    return calculate_technical_score(
        indicators=indicators,
        structure=structure,
    )