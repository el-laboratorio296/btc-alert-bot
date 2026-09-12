from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Mapping


class RiskError(Exception):
    """Error base del motor de gestión de riesgo."""


DECISION_BUY = "BUY"
DECISION_ACCUMULATE = "ACCUMULATE"
DECISION_SPECULATIVE = "SPECULATIVE"
DECISION_WAIT = "WAIT_CONFIRMATION"
DECISION_AVOID = "AVOID"


@dataclass(frozen=True)
class RiskPlan:
    valid: bool
    decision: str
    entry_low: float | None
    entry_high: float | None
    entry_reference: float | None
    stop: float | None
    invalidation: float | None
    tp1: float | None
    tp2: float | None
    tp3: float | None
    risk_per_unit: float | None
    reward_to_tp1: float | None
    reward_to_tp2: float | None
    reward_to_tp3: float | None
    risk_reward_tp1: float | None
    risk_reward_tp2: float | None
    risk_reward_tp3: float | None
    position_size: float | None
    capital_at_risk: float | None
    risk_percent: float | None
    reason: str
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

    if number in {
        float("inf"),
        float("-inf"),
    }:
        return default

    return number


def _clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    return max(
        minimum,
        min(maximum, value),
    )


def _normalize(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip().upper()


def _first_number(
    data: Mapping[str, Any],
    names: tuple[str, ...],
) -> float | None:
    for name in names:
        value = _number(data.get(name))

        if value is not None:
            return value

    return None


# ============================================================
# VALIDACIÓN
# ============================================================

def _validate_positive(
    value: float | None,
    name: str,
) -> None:
    if value is None:
        raise RiskError(
            f"{name} es obligatorio."
        )

    if value <= 0:
        raise RiskError(
            f"{name} debe ser mayor que cero."
        )


# ============================================================
# DECISIONES OPERABLES
# ============================================================

def _is_operable_decision(
    decision: str,
) -> bool:
    return decision in {
        DECISION_BUY,
        DECISION_ACCUMULATE,
        DECISION_SPECULATIVE,
    }


# ============================================================
# CÁLCULO DEL STOP
# ============================================================

def calculate_stop(
    price: float,
    atr: float,
    support: float | None = None,
    atr_multiplier: float = 1.5,
) -> float:
    """
    Calcula un stop técnico para una posición LONG.

    Prioridad:

    1. Soporte válido con margen ATR.
    2. Precio - ATR * multiplicador.

    Nunca devuelve un stop por encima o igual al precio.
    """

    _validate_positive(
        price,
        "price",
    )

    _validate_positive(
        atr,
        "atr",
    )

    if atr_multiplier <= 0:
        raise RiskError(
            "atr_multiplier debe ser mayor que cero."
        )

    atr_stop = price - (
        atr * atr_multiplier
    )

    support_stop = None

    if support is not None:
        support_value = _number(
            support
        )

        if (
            support_value is not None
            and 0 < support_value < price
        ):
            support_stop = support_value - (
                atr * 0.20
            )

    candidates = [
        value
        for value in (
            atr_stop,
            support_stop,
        )
        if value is not None
        and value > 0
        and value < price
    ]

    if not candidates:
        raise RiskError(
            "No fue posible calcular un stop válido."
        )

    # Elegimos el stop más conservador:
    # el nivel más alejado del precio.
    return min(candidates)


# ============================================================
# OBJETIVOS
# ============================================================

def calculate_targets(
    entry: float,
    risk_per_unit: float,
    resistance: float | None = None,
) -> tuple[float, float, float]:
    """
    Calcula tres objetivos LONG utilizando múltiplos
    de riesgo.

    TP1 = 1.5R
    TP2 = 2.0R
    TP3 = 3.0R

    Si existe una resistencia cercana, TP1 se adapta
    para no ignorar una zona técnica importante.
    """

    _validate_positive(
        entry,
        "entry",
    )

    _validate_positive(
        risk_per_unit,
        "risk_per_unit",
    )

    tp1 = entry + (
        risk_per_unit * 1.5
    )

    tp2 = entry + (
        risk_per_unit * 2.0
    )

    tp3 = entry + (
        risk_per_unit * 3.0
    )

    resistance_value = _number(
        resistance
    )

    if (
        resistance_value is not None
        and resistance_value > entry
    ):
        # Si la resistencia está antes de TP1,
        # no colocamos TP1 artificialmente por encima
        # de la primera barrera técnica.
        if resistance_value < tp1:
            tp1 = resistance_value

        # Garantizamos que TP1 siga siendo una ganancia.
        if tp1 <= entry:
            tp1 = entry + (
                risk_per_unit * 1.0
            )

    # Garantizamos orden lógico.
    tp2 = max(
        tp2,
        tp1 + (
            risk_per_unit * 0.25
        ),
    )

    tp3 = max(
        tp3,
        tp2 + (
            risk_per_unit * 0.25
        ),
    )

    return (
        tp1,
        tp2,
        tp3,
    )


# ============================================================
# RELACIÓN RIESGO / BENEFICIO
# ============================================================

def calculate_risk_reward(
    entry: float,
    stop: float,
    target: float,
) -> float:
    _validate_positive(
        entry,
        "entry",
    )

    _validate_positive(
        stop,
        "stop",
    )

    _validate_positive(
        target,
        "target",
    )

    risk = entry - stop
    reward = target - entry

    if risk <= 0:
        raise RiskError(
            "El stop debe estar por debajo de la entrada."
        )

    if reward <= 0:
        raise RiskError(
            "El objetivo debe estar por encima de la entrada."
        )

    return reward / risk


# ============================================================
# TAMAÑO DE POSICIÓN
# ============================================================

def calculate_position_size(
    capital: float,
    risk_percent: float,
    entry: float,
    stop: float,
) -> tuple[float, float]:
    """
    Calcula tamaño de posición para una operación LONG.

    capital_at_risk = capital * risk_percent / 100

    position_size = capital_at_risk /
                    abs(entry - stop)
    """

    _validate_positive(
        capital,
        "capital",
    )

    _validate_positive(
        entry,
        "entry",
    )

    _validate_positive(
        stop,
        "stop",
    )

    if not 0 < risk_percent <= 100:
        raise RiskError(
            "risk_percent debe estar entre "
            "0 y 100."
        )

    risk_per_unit = entry - stop

    if risk_per_unit <= 0:
        raise RiskError(
            "El stop debe estar por debajo "
            "de la entrada."
        )

    capital_at_risk = (
        capital
        * risk_percent
        / 100.0
    )

    position_size = (
        capital_at_risk
        / risk_per_unit
    )

    return (
        position_size,
        capital_at_risk,
    )


# ============================================================
# PLAN COMPLETO
# ============================================================

def calculate_risk_plan(
    strategy: Mapping[str, Any],
    indicators: Mapping[str, Any],
    structure: Mapping[str, Any] | None = None,
    capital: float | None = None,
    risk_percent: float = 1.0,
) -> dict[str, Any]:
    """
    Genera un plan de riesgo para una operación LONG.

    El motor NO crea una operación si Strategy indica:

    WAIT_CONFIRMATION
    AVOID

    Requiere:

    - price
    - ATR
    - decisión de Strategy

    Puede utilizar:

    - support
    - resistance
    - capital
    - risk_percent
    """

    if not isinstance(
        strategy,
        Mapping,
    ):
        raise TypeError(
            "strategy debe ser un Mapping."
        )

    if not isinstance(
        indicators,
        Mapping,
    ):
        raise TypeError(
            "indicators debe ser un Mapping."
        )

    if structure is None:
        structure = {}

    if not isinstance(
        structure,
        Mapping,
    ):
        raise TypeError(
            "structure debe ser un Mapping."
        )

    decision = _normalize(
        strategy.get(
            "decision"
        )
    )

    # --------------------------------------------------------
    # NO OPERABLE
    # --------------------------------------------------------

    if not _is_operable_decision(
        decision
    ):
        return RiskPlan(
            valid=False,
            decision=decision,
            entry_low=None,
            entry_high=None,
            entry_reference=None,
            stop=None,
            invalidation=None,
            tp1=None,
            tp2=None,
            tp3=None,
            risk_per_unit=None,
            reward_to_tp1=None,
            reward_to_tp2=None,
            reward_to_tp3=None,
            risk_reward_tp1=None,
            risk_reward_tp2=None,
            risk_reward_tp3=None,
            position_size=None,
            capital_at_risk=None,
            risk_percent=None,
            reason=(
                "La decisión de Strategy "
                "no permite abrir una operación."
            ),
            warnings=(
                "No crear posición.",
            ),
        ).to_dict()

    # --------------------------------------------------------
    # PRECIO
    # --------------------------------------------------------

    price = _first_number(
        indicators,
        (
            "price",
            "close",
        ),
    )

    _validate_positive(
        price,
        "price",
    )

    # --------------------------------------------------------
    # ATR
    # --------------------------------------------------------

    atr = _first_number(
        indicators,
        (
            "atr14",
            "atr",
        ),
    )

    _validate_positive(
        atr,
        "atr14",
    )

    # --------------------------------------------------------
    # ESTRUCTURA
    # --------------------------------------------------------

    support = _first_number(
        structure,
        (
            "support",
            "nearest_support",
            "support_level",
        ),
    )

    resistance = _first_number(
        structure,
        (
            "resistance",
            "nearest_resistance",
            "resistance_level",
        ),
    )

    # --------------------------------------------------------
    # ZONA DE ENTRADA
    # --------------------------------------------------------

    entry_reference = price

    entry_low = price - (
        atr * 0.25
    )

    entry_high = price + (
        atr * 0.10
    )

    # Nunca permitimos entrada negativa.
    entry_low = max(
        entry_low,
        price * 0.50,
    )

    # --------------------------------------------------------
    # STOP
    # --------------------------------------------------------

    stop = calculate_stop(
        price=entry_reference,
        atr=atr,
        support=support,
    )

    invalidation = stop

    risk_per_unit = (
        entry_reference - stop
    )

    if risk_per_unit <= 0:
        raise RiskError(
            "Riesgo por unidad inválido."
        )

    # --------------------------------------------------------
    # OBJETIVOS
    # --------------------------------------------------------

    tp1, tp2, tp3 = calculate_targets(
        entry=entry_reference,
        risk_per_unit=risk_per_unit,
        resistance=resistance,
    )

    # --------------------------------------------------------
    # R:R
    # --------------------------------------------------------

    rr1 = calculate_risk_reward(
        entry=entry_reference,
        stop=stop,
        target=tp1,
    )

    rr2 = calculate_risk_reward(
        entry=entry_reference,
        stop=stop,
        target=tp2,
    )

    rr3 = calculate_risk_reward(
        entry=entry_reference,
        stop=stop,
        target=tp3,
    )

    # --------------------------------------------------------
    # ADVERTENCIAS
    # --------------------------------------------------------

    warnings: list[str] = []

    if rr1 < 1.0:
        warnings.append(
            "TP1 tiene R:R inferior a 1:1."
        )

    if rr2 < 1.5:
        warnings.append(
            "TP2 tiene R:R inferior a 1:1.5."
        )

    if decision == DECISION_SPECULATIVE:
        warnings.append(
            "Operación especulativa: riesgo elevado."
        )

    if resistance is None:
        warnings.append(
            "No se proporcionó resistencia estructural."
        )

    if support is None:
        warnings.append(
            "No se proporcionó soporte estructural."
        )

    # --------------------------------------------------------
    # TAMAÑO DE POSICIÓN
    # --------------------------------------------------------

    position_size = None
    capital_at_risk = None
    normalized_risk_percent = None

    if capital is not None:
        (
            position_size,
            capital_at_risk,
        ) = calculate_position_size(
            capital=capital,
            risk_percent=risk_percent,
            entry=entry_reference,
            stop=stop,
        )

        normalized_risk_percent = (
            float(risk_percent)
        )

    # --------------------------------------------------------
    # RESULTADO
    # --------------------------------------------------------

    return RiskPlan(
        valid=True,
        decision=decision,
        entry_low=round(
            entry_low,
            8,
        ),
        entry_high=round(
            entry_high,
            8,
        ),
        entry_reference=round(
            entry_reference,
            8,
        ),
        stop=round(
            stop,
            8,
        ),
        invalidation=round(
            invalidation,
            