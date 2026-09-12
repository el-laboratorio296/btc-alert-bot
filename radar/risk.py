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

    if not number == number:
        return default

    if number in (
        float("inf"),
        float("-inf"),
    ):
        return default

    return number


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


def _is_operable_decision(
    decision: str,
) -> bool:
    return decision in {
        DECISION_BUY,
        DECISION_ACCUMULATE,
        DECISION_SPECULATIVE,
    }


def calculate_stop(
    price: float,
    atr: float,
    support: float | None = None,
    atr_multiplier: float = 1.5,
) -> float:
    """
    Calcula un stop técnico para una posición LONG.

    Se utiliza ATR como referencia de volatilidad.
    Si existe soporte válido, se coloca un margen
    adicional debajo del soporte.

    El stop siempre debe quedar por debajo del precio.
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

    support_value = _number(
        support
    )

    if (
        support_value is not None
        and support_value > 0
        and support_value < price
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

    return min(candidates)


def calculate_targets(
    entry: float,
    risk_per_unit: float,
    resistance: float | None = None,
) -> tuple[float, float, float]:
    """
    Calcula objetivos LONG utilizando múltiplos de riesgo.

    TP1 = 1.5R
    TP2 = 2.0R
    TP3 = 3.0R
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
        and resistance_value < tp1
    ):
        tp1 = resistance_value

    if tp1 <= entry:
        tp1 = entry + risk_per_unit

    if tp2 <= tp1:
        tp2 = tp1 + (
            risk_per_unit * 0.25
        )

    if tp3 <= tp2:
        tp3 = tp2 + (
            risk_per_unit * 0.25
        )

    return (
        tp1,
        tp2,
        tp3,
    )


def calculate_risk_reward(
    entry: float,
    stop: float,
    target: float,
) -> float:
    """Calcula reward/risk para una posición LONG."""

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


def calculate_position_size(
    capital: float,
    risk_percent: float,
    entry: float,
    stop: float,
) -> tuple[float, float]:
    """
    Calcula el tamaño de posición según el capital
    que estamos dispuestos a arriesgar.
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
            "risk_percent debe estar entre 0 y 100."
        )

    risk_per_unit = entry - stop

    if risk_per_unit <= 0:
        raise RiskError(
            "El stop debe estar por debajo de la entrada."
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


def calculate_risk_plan(
    strategy: Mapping[str, Any],
    indicators: Mapping[str, Any],
    structure: Mapping[str, Any] | None = None,
    capital: float | None = None,
    risk_percent: float = 1.0,
) -> dict[str, Any]:
    """
    Genera un plan de riesgo para una operación LONG.

    WAIT_CONFIRMATION y AVOID nunca generan una posición.
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

    # ========================================================
    # DECISIÓN NO OPERABLE
    # ========================================================

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
                "