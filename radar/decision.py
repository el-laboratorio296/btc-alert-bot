from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Mapping


class DecisionError(Exception):
    """Error base del motor de decisión."""


DECISION_BUY = "BUY"
DECISION_ACCUMULATE = "ACCUMULATE"
DECISION_WAIT = "WAIT_CONFIRMATION"
DECISION_SPECULATIVE = "SPECULATIVE"
DECISION_AVOID = "AVOID"


REGIME_RISK_ON = "RISK_ON"
REGIME_NEUTRAL = "NEUTRAL"
REGIME_RISK_OFF = "RISK_OFF"
REGIME_HIGH_RISK = "HIGH_RISK"


@dataclass(frozen=True)
class DecisionResult:
    decision: str
    bias: str
    confidence: float
    market_regime: str
    technical_score: float
    trend_quality: float
    timeframe_alignment: float
    confirmation_score: float
    risk_level: str
    reason: str
    confirmations: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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

    if not (
        number == number
        and number != float("inf")
        and number != float("-inf")
    ):
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


def _text(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip().upper()


def _mapping(
    value: Any,
    name: str,
) -> Mapping[str, Any]:
    if value is None:
        return {}

    if not isinstance(value, Mapping):
        raise TypeError(
            f"{name} debe ser un Mapping."
        )

    return value


def _bullish(value: Any) -> bool:
    return _text(value) in {
        "BULLISH",
        "BULLISH_STRONG",
        "BULLISH_WEAK",
        "UPTREND",
        "ALCISTA",
        "UP",
        "LONG",
    }


def _bearish(value: Any) -> bool:
    return _text(value) in {
        "BEARISH",
        "BEARISH_STRONG",
        "BEARISH_WEAK",
        "DOWNTREND",
        "BAJISTA",
        "DOWN",
        "SHORT",
    }


def _closed(data: Mapping[str, Any]) -> bool:
    value = data.get(
        "last_candle_closed"
    )

    if value is None:
        return True

    return bool(value)


def _timeframe_bias(
    data: Mapping[str, Any],
) -> str:
    for key in (
        "bias",
        "trend",
        "signal",
    ):
        value = _text(data.get(key))

        if _bullish(value):
            return "BULLISH"

        if _bearish(value):
            return "BEARISH"

    return "NEUTRAL"


def calculate_timeframe_alignment(
    timeframes: Mapping[str, Any],
) -> float:
    """
    Calcula la alineación entre 1D, 4H, 1H y 15M.

    1D y 4H tienen mayor peso porque representan
    tendencia y estructura.

    1H y 15M tienen menor peso porque son más sensibles
    al ruido de corto plazo.
    """

    if not isinstance(timeframes, Mapping):
        raise TypeError(
            "timeframes debe ser un Mapping."
        )

    weights = {
        "1d": 0.35,
        "4h": 0.30,
        "1h": 0.20,
        "15m": 0.15,
    }

    available = []

    for timeframe, weight in weights.items():
        data = timeframes.get(timeframe)

        if not isinstance(data, Mapping):
            continue

        bias = _timeframe_bias(data)

        if bias == "BULLISH":
            available.append(
                (weight, 1.0)
            )
        elif bias == "BEARISH":
            available.append(
                (weight, -1.0)
            )
        else:
            available.append(
                (weight, 0.0)
            )

    if not available:
        return 50.0

    total_weight = sum(
        weight
        for weight, _ in available
    )

    if total_weight <= 0:
        return 50.0

    directional = sum(
        weight * direction
        for weight, direction in available
    )

    normalized = directional / total_weight

    return _clamp(
        50.0 + normalized * 50.0
    )


def calculate_trend_quality(
    timeframes: Mapping[str, Any],
) -> float:
    """
    Mide la consistencia direccional de las temporalidades.

    No mide simplemente si el mercado está alcista.
    Mide cuánto coinciden las temporalidades.
    """

    if not isinstance(timeframes, Mapping):
        raise TypeError(
            "timeframes debe ser un Mapping."
        )

    biases = []

    for timeframe in (
        "1d",
        "4h",
        "1h",
        "15m",
    ):
        data = timeframes.get(timeframe)

        if not isinstance(data, Mapping):
            continue

        bias = _timeframe_bias(data)

        if bias != "NEUTRAL":
            biases.append(bias)

    if not biases:
        return 50.0

    bullish_count = sum(
        1
        for bias in biases
        if bias == "BULLISH"
    )

    bearish_count = sum(
        1
        for bias in biases
        if bias == "BEARISH"
    )

    dominant = max(
        bullish_count,
        bearish_count,
    )

    consistency = (
        dominant
        / len(biases)
    ) * 100.0

    return _clamp(
        consistency
    )


def determine_market_regime(
    technical_score: float,
    confidence: float,
    trend_quality: float,
    volatility_score: float = 50.0,
) -> str:
    """
    Clasifica el entorno general.

    Prioridad de seguridad:

    1. Volatilidad extrema.
    2. Riesgo de mercado.
    3. Condiciones favorables.
    4. Neutralidad.

    Importante:
    una volatilidad extremadamente adversa puede activar
    HIGH_RISK aunque el score técnico sea elevado.
    """

    score = _clamp(
        technical_score
    )

    confidence_value = _clamp(
        confidence
    )

    trend = _clamp(
        trend_quality
    )

    volatility = _clamp(
        volatility_score
    )

    # --------------------------------------------------------
    # BLOQUEO DE SEGURIDAD POR VOLATILIDAD EXTREMA
    # --------------------------------------------------------

    if volatility <= 15.0:
        return REGIME_HIGH_RISK

    # Volatilidad muy elevada.
    # Se considera HIGH_RISK incluso con buen score técnico.
    if volatility <= 25.0:
        return REGIME_HIGH_RISK

    # --------------------------------------------------------
    # RISK OFF
    # --------------------------------------------------------

    if (
        score <= 35.0
        and trend <= 50.0
    ):
        return REGIME_RISK_OFF

    # --------------------------------------------------------
    # RISK ON
    # --------------------------------------------------------

    if (
        score >= 65.0
        and trend >= 70.0
        and confidence_value >= 60.0
    ):
        return REGIME_RISK_ON

    return REGIME_NEUTRAL


def calculate_confirmation_score(
    strategy: Mapping[str, Any],
    risk: Mapping[str, Any] | None = None,
) -> float:
    """
    Evalúa cuánto respaldo existe para ejecutar
    una operación.

    La puntuación no crea una señal por sí sola.
    """

    if not isinstance(
        strategy,
        Mapping,
    ):
        raise TypeError(
            "strategy debe ser un Mapping."
        )

    risk_data = _mapping(
        risk,
        "risk",
    )

    decision = _text(
        strategy.get("decision")
    )

    confirmations = strategy.get(
        "confirmations",
        (),
    )

    if not isinstance(
        confirmations,
        (list, tuple, set),
    ):
        confirmations = ()

    blockers = strategy.get(
        "blockers",
        (),
    )

    if not isinstance(
        blockers,
        (list, tuple, set),
    ):
        blockers = ()

    score = 50.0

    if decision == DECISION_BUY:
        score += 30.0

    elif decision == DECISION_ACCUMULATE:
        score += 20.0

    elif decision == DECISION_SPECULATIVE:
        score += 5.0

    elif decision == DECISION_WAIT:
        score -= 15.0

    elif decision == DECISION_AVOID:
        score -= 40.0

    score += min(
        len(confirmations) * 5.0,
        15.0,
    )

    score -= min(
        len(blockers) * 10.0,
        30.0,
    )

    if risk_data.get("valid") is True:
        score += 10.0

    if risk_data.get("valid") is False:
        score -= 20.0

    return _clamp(score)


def determine_risk_level(
    risk: Mapping[str, Any] | None,
    strategy: Mapping[str, Any],
    market_regime: str,
) -> str:
    """
    Clasifica riesgo operativo.

    EXTREME:
        riesgo estructural o de mercado muy elevado.

    HIGH:
        operación posible pero con condiciones adversas.

    MEDIUM:
        riesgo controlable.

    LOW:
        condiciones relativamente favorables.
    """

    risk_data = _mapping(
        risk,
        "risk",
    )

    strategy_data = _mapping(
        strategy,
        "strategy",
    )

    decision = _text(
        strategy_data.get("decision")
    )

    regime = _text(
        market_regime
    )

    warnings = risk_data.get(
        "warnings",
        (),
    )

    if not isinstance(
        warnings,
        (list, tuple, set),
    ):
        warnings = ()

    if regime == REGIME_HIGH_RISK:
        return "EXTREME"

    if decision == DECISION_AVOID:
        return "EXTREME"

    if decision == DECISION_SPECULATIVE:
        return "HIGH"

    if regime == REGIME_RISK_OFF:
        return "HIGH"

    if len(warnings) >= 3:
        return "HIGH"

    if decision == DECISION_WAIT:
        return "MEDIUM"

    if len(warnings) >= 1:
        return "MEDIUM"

    return "LOW"


def _risk_reward_ok(
    risk: Mapping[str, Any] | None,
) -> bool:
    if not isinstance(risk, Mapping):
        return False

    rr = _number(
        risk.get(
            "risk_reward_tp2"
        )
    )

    if rr is None:
        return False

    return rr >= 1.5


def build_decision(
    scoring: Mapping[str, Any],
    strategy: Mapping[str, Any],
    risk: Mapping[str, Any] | None = None,
    timeframes: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Motor central del Radar.

    Orden de prioridad:

    1. Seguridad.
    2. Régimen.
    3. Alineación temporal.
    4. Confirmación.
    5. Riesgo/recompensa.
    6. Decisión final.

    Una condición pelig