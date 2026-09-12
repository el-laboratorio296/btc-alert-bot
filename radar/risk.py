from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Mapping


class RiskError(Exception):
    """Error base del motor de riesgo."""


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


def _number(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number != number:
        return default
    if number in (float("inf"), float("-inf")):
        return default
    return number


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
        raise RiskError(f"{name} es obligatorio.")
    if value <= 0:
        raise RiskError(f"{name} debe ser mayor que cero.")


def _is_operable(decision: str) -> bool:
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
    _validate_positive(price, "price")
    _validate_positive(atr, "atr")

    if atr_multiplier <= 0:
        raise RiskError(
            "atr_multiplier debe ser mayor que cero."
        )

    atr_stop = price - atr * atr_multiplier

    candidates = [atr_stop]

    support_value = _number(support)

    if (
        support_value is not None
        and 0 < support_value < price
    ):
        support_stop = support_value - atr * 0.20
        candidates.append(support_stop)

    valid = [
        value
        for value in candidates
        if 0 < value < price
    ]

    if not valid:
        raise RiskError(
            "No fue posible calcular un stop válido."
        )

    return min(valid)


def calculate_targets(
    entry: float,
    risk_per_unit: float,
    resistance: float | None = None,
) -> tuple[float, float, float]:
    _validate_positive(entry, "entry")
    _validate_positive(
        risk_per_unit,
        "risk_per_unit",
    )

    tp1 = entry + risk_per_unit * 1.5
    tp2 = entry + risk_per_unit * 2.0
    tp3 = entry + risk_per_unit * 3.0

    resistance_value = _number(resistance)

    if (
        resistance_value is not None
        and entry < resistance_value < tp1
    ):
        tp1 = resistance_value

    if tp1 <= entry:
        tp1 = entry + risk_per_unit

    if tp2 <= tp1:
        tp2 = tp1 + risk_per_unit * 0.25

    if tp3 <= tp2:
        tp3 = tp2 + risk_per_unit * 0.25

    return tp1, tp2, tp3


def calculate_risk_reward(
    entry: float,
    stop: float,
    target: float,
) -> float:
    _validate_positive(entry, "entry")
    _validate_positive(stop, "stop")
    _validate_positive(target, "target")

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
    _validate_positive(capital, "capital")
    _validate_positive(entry, "entry")
    _validate_positive(stop, "stop")

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
        capital * risk_percent / 100.0
    )

    position_size = (
        capital_at_risk / risk_per_unit
    )

    return position_size, capital_at_risk


def calculate_risk_plan(
    strategy: Mapping[str, Any],
    indicators: Mapping[str, Any],
    structure: Mapping[str, Any] | None = None,
    capital: float | None = None,
    risk_percent: float = 1.0,
) -> dict[str, Any]:

    if not isinstance(strategy, Mapping):
        raise TypeError(
            "strategy debe ser un Mapping."
        )

    if not isinstance(indicators, Mapping):
        raise TypeError(
            "indicators debe ser un Mapping."
        )

    if structure is None:
        structure = {}

    if not isinstance(structure, Mapping):
        raise TypeError(
            "structure debe ser un Mapping."
        )

    decision = str(
        strategy.get("decision", "")
    ).strip().upper()

    if not _is_operable(decision):
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
            warnings=("No crear posición.",),
        ).to_dict()

    price = _first_number(
        indicators,
        ("price", "close"),
    )

    atr = _first_number(
        indicators,
        ("atr14", "atr"),
    )

    _validate_positive(price, "price")
    _validate_positive(atr, "atr")

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

    entry = price

    entry_low = max(
        price - atr * 0.25,
        price * 0.50,
    )

    entry_high = price + atr * 0.10

    stop = calculate_stop(
        price=entry,
        atr=atr,
        support=support,
    )

    invalidation = stop

    risk_per_unit = entry - stop

    if risk_per_unit <= 0:
        raise RiskError(
            "Riesgo por unidad inválido."
        )

    tp1, tp2, tp3 = calculate_targets(
        entry=entry,
        risk_per_unit=risk_per_unit,
        resistance=resistance,
    )

    rr1 = calculate_risk_reward(
        entry=entry,
        stop=stop,
        target=tp1,
    )

    rr2 = calculate_risk_reward(
        entry=entry,
        stop=stop,
        target=tp2,
    )

    rr3 = calculate_risk_reward(
        entry=entry,
        stop=stop,
        target=tp3,
    )

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

    position_size = None
    capital_at_risk = None
    final_risk_percent = None

    if capital is not None:
        (
            position_size,
            capital_at_risk,
        ) = calculate_position_size(
            capital=capital,
            risk_percent=risk_percent,
            entry=entry,
            stop=stop,
        )

        final_risk_percent = float(
            risk_percent
        )

    return RiskPlan(
        valid=True,
        decision=decision,
        entry_low=round(entry_low, 8),
        entry_high=round(entry_high, 8),
        entry_reference=round(entry, 8),
        stop=round(stop, 8),
        invalidation=round(invalidation, 8),
        tp1=round(tp1, 8),
        tp2=round(tp2, 8),
        tp3=round(tp3, 8),
        risk_per_unit=round(
            risk_per_unit,
            8,
        ),
        reward_to_tp1=round(
            tp1 - entry,
            8,
        ),
        reward_to_tp2=round(
            tp2 - entry,
            8,
        ),
        reward_to_tp3=round(
            tp3 - entry,
            8,
        ),
        risk_reward_tp1=round(
            rr1,
            4,
        ),
        risk_reward_tp2=round(
            rr2,
            4,
        ),
        risk_reward_tp3=round(
            rr3,
            4,
        ),
        position_size=(
            round(position_size, 8)
            if position_size is not None
            else None
        ),
        capital_at_risk=(
            round(capital_at_risk, 8)
            if capital_at_risk is not None
            else None
        ),
        risk_percent=final_risk_percent,
        reason=(
            "Plan de riesgo generado "
            "a partir de precio, ATR y estructura."
        ),
        warnings=tuple(warnings),
    ).to_dict()


def risk_plan(
    strategy: Mapping[str, Any],
    indicators: Mapping[str, Any],
    structure: Mapping[str, Any] | None = None,
    capital: float | None = None,
    risk_percent: float = 1.0,
) -> dict[str, Any]:
    return calculate_risk_plan(
        strategy=strategy,
        indicators=indicators,
        structure=structure,
        capital=capital,
        risk_percent=risk_percent,
    )