from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


class DecisionError(Exception):
    """Error base del motor de decisiones."""


# ============================================================
# DECISIONES
# ============================================================

DECISION_BUY = "BUY"
DECISION_ACCUMULATE = "ACCUMULATE"
DECISION_WAIT = "WAIT_CONFIRMATION"
DECISION_SPECULATIVE = "SPECULATIVE"
DECISION_AVOID = "AVOID"


# ============================================================
# REGÍMENES DE MERCADO
# ============================================================

REGIME_RISK_ON = "RISK_ON"
REGIME_NEUTRAL = "NEUTRAL"
REGIME_RISK_OFF = "RISK_OFF"
REGIME_HIGH_RISK = "HIGH_RISK"


# ============================================================
# RESULTADO
# ============================================================

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


# ============================================================
# UTILIDADES
# ============================================================

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

    if number == float("inf"):
        return default

    if number == float("-inf"):
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
    value = data.get("last_candle_closed")

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


# ============================================================
# MULTI-TIMEFRAME ALIGNMENT
# ============================================================

def calculate_timeframe_alignment(
    timeframes: Mapping[str, Any],
) -> float:

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

    available: list[tuple[float, float]] = []

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


# ============================================================
# CALIDAD DE TENDENCIA
# ============================================================

def calculate_trend_quality(
    timeframes: Mapping[str, Any],
) -> float:

    if not isinstance(timeframes, Mapping):
        raise TypeError(
            "timeframes debe ser un Mapping."
        )

    biases: list[str] = []

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
        dominant / len(biases)
    ) * 100.0

    return _clamp(consistency)


# ============================================================
# RÉGIMEN DE MERCADO
# ============================================================

def determine_market_regime(
    technical_score: float,
    confidence: float,
    trend_quality: float,
    volatility_score: float = 50.0,
) -> str:

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

    # Volatilidad extrema tiene prioridad.
    if volatility <= 25.0:
        return REGIME_HIGH_RISK

    # Mercado claramente deteriorado.
    if (
        score <= 35.0
        and trend <= 50.0
    ):
        return REGIME_RISK_OFF

    # Mercado alcista de calidad.
    if (
        score >= 65.0
        and trend >= 70.0
        and confidence_value >= 60.0
    ):
        return REGIME_RISK_ON

    return REGIME_NEUTRAL


# ============================================================
# CONFIRMACIONES
# ============================================================

def calculate_confirmation_score(
    strategy: Mapping[str, Any],
    risk: Mapping[str, Any] | None = None,
) -> float:

    if not isinstance(strategy, Mapping):
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

    elif risk_data.get("valid") is False:
        score -= 20.0

    return _clamp(score)


# ============================================================
# NIVEL DE RIESGO
# ============================================================

def determine_risk_level(
    risk: Mapping[str, Any] | None,
    strategy: Mapping[str, Any],
    market_regime: str,
) -> str:

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


# ============================================================
# RIESGO / BENEFICIO
# ============================================================

def _risk_reward_ok(
    risk: Mapping[str, Any] | None,
) -> bool:

    if not isinstance(
        risk,
        Mapping,
    ):
        return False

    rr = _number(
        risk.get("risk_reward_tp2")
    )

    if rr is None:
        return False

    return rr >= 1.5


# ============================================================
# MOTOR PRINCIPAL
# ============================================================

def build_decision(
    scoring: Mapping[str, Any],
    strategy: Mapping[str, Any],
    risk: Mapping[str, Any] | None = None,
    timeframes: Mapping[str, Any] | None = None,
) -> dict[str, Any]:

    if not isinstance(
        scoring,
        Mapping,
    ):
        raise TypeError(
            "scoring debe ser un Mapping."
        )

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

    timeframe_data = _mapping(
        timeframes,
        "timeframes",
    )

    technical_score = _number(
        scoring.get(
            "technical_score"
        ),
        50.0,
    )

    confidence = _number(
        scoring.get(
            "confidence"
        ),
        0.0,
    )

    volatility_score = _number(
        scoring.get(
            "volatility_score"
        ),
        50.0,
    )

    technical_score = _clamp(
        technical_score
    )

    confidence = _clamp(
        confidence
    )

    volatility_score = _clamp(
        volatility_score
    )

    # --------------------------------------------------------
    # ANÁLISIS MULTI-TIMEFRAME
    # --------------------------------------------------------

    timeframe_alignment = (
        calculate_timeframe_alignment(
            timeframe_data
        )
    )

    trend_quality = (
        calculate_trend_quality(
            timeframe_data
        )
    )

    # --------------------------------------------------------
    # RÉGIMEN
    # --------------------------------------------------------

    market_regime = (
        determine_market_regime(
            technical_score=technical_score,
            confidence=confidence,
            trend_quality=trend_quality,
            volatility_score=volatility_score,
        )
    )

    # --------------------------------------------------------
    # CONFIRMACIÓN
    # --------------------------------------------------------

    confirmation_score = (
        calculate_confirmation_score(
            strategy=strategy,
            risk=risk_data,
        )
    )

    # --------------------------------------------------------
    # RIESGO
    # --------------------------------------------------------

    risk_level = (
        determine_risk_level(
            risk=risk_data,
            strategy=strategy,
            market_regime=market_regime,
        )
    )

    confirmations: list[str] = []
    blockers: list[str] = []
    warnings: list[str] = []

    # --------------------------------------------------------
    # ALIGNMENT
    # --------------------------------------------------------

    if timeframe_alignment >= 70.0:

        confirmations.append(
            "Temporalidades alineadas al alza."
        )

    elif timeframe_alignment <= 30.0:

        blockers.append(
            "Temporalidades alineadas a la baja."
        )

    else:

        warnings.append(
            "Las temporalidades presentan conflicto."
        )

    # --------------------------------------------------------
    # TREND QUALITY
    # --------------------------------------------------------

    if trend_quality >= 75.0:

        confirmations.append(
            "Alta consistencia de tendencia."
        )

    elif trend_quality < 50.0:

        warnings.append(
            "Baja consistencia de tendencia."
        )

    # --------------------------------------------------------
    # CONFIRMACIONES DE STRATEGY
    # --------------------------------------------------------

    strategy_confirmations = strategy.get(
        "confirmations",
        (),
    )

    if isinstance(
        strategy_confirmations,
        (list, tuple, set),
    ):

        confirmations.extend(
            str(item)
            for item in strategy_confirmations
        )

    # --------------------------------------------------------
    # BLOQUEADORES DE STRATEGY
    # --------------------------------------------------------

    strategy_blockers = strategy.get(
        "blockers",
        (),
    )

    if isinstance(
        strategy_blockers,
        (list, tuple, set),
    ):

        blockers.extend(
            str(item)
            for item in strategy_blockers
        )

    # --------------------------------------------------------
    # VELAS ABIERTAS
    # --------------------------------------------------------

    open_candle = False

    for data in timeframe_data.values():

        if not isinstance(
            data,
            Mapping,
        ):
            continue

        if not _closed(data):

            open_candle = True
            break

    if open_candle:

        warnings.append(
            "Existe al menos una vela abierta."
        )

    # --------------------------------------------------------
    # DECISIÓN DE STRATEGY
    # --------------------------------------------------------

    strategy_decision = _text(
        strategy.get("decision")
    )

    if strategy_decision in {
        DECISION_BUY,
        DECISION_ACCUMULATE,
    }:

        if _risk_reward_ok(
            risk_data
        ):

            confirmations.append(
                "R:R de TP2 cumple el mínimo 1.5:1."
            )

        else:

            blockers.append(
                "R:R insuficiente para la operación."
            )

    # --------------------------------------------------------
    # DECISIÓN FINAL
    # --------------------------------------------------------

    final_decision = strategy_decision

    reason = (
        "La decisión se mantiene según Strategy."
    )

    # --------------------------------------------------------
    # AVOID
    # --------------------------------------------------------

    if strategy_decision == DECISION_AVOID:

        final_decision = DECISION_AVOID

        reason = (
            "Strategy bloquea la operación "
            "por condiciones adversas."
        )

    # --------------------------------------------------------
    # RIESGO EXTREMO
    # --------------------------------------------------------

    elif market_regime == REGIME_HIGH_RISK:

        final_decision = DECISION_AVOID

        reason = (
            "El régimen de mercado presenta "
            "riesgo extremo. La operación queda bloqueada."
        )

    # --------------------------------------------------------
    # BUY
    # --------------------------------------------------------

    elif strategy_decision == DECISION_BUY:

        if risk_level == "EXTREME":

            final_decision = DECISION_AVOID

            reason = (
                "La señal alcista queda anulada "
                "por riesgo extremo."
            )

        elif timeframe_alignment < 55.0:

            final_decision = DECISION_WAIT

            reason = (
                "La señal alcista carece de suficiente "
                "