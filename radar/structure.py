from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from radar.models import Candle


class StructureError(Exception):
    """Error base del módulo de estructura de mercado."""


# ============================================================
# CONSTANTES
# ============================================================

VALID_STRUCTURE_STATES = {
    "BULLISH",
    "BEARISH",
    "RANGE",
    "NEUTRAL",
    "INSUFFICIENT_DATA",
}

VALID_BREAKOUT_STATES = {
    "NONE",
    "BREAKOUT",
    "BREAKDOWN",
    "POTENTIAL_BREAKOUT",
    "POTENTIAL_BREAKDOWN",
}


# ============================================================
# MODELOS
# ============================================================

@dataclass(frozen=True)
class SwingPoint:
    """
    Punto estructural del mercado.

    index:
        Posición de la vela dentro de la serie.

    timestamp:
        Timestamp de la vela.

    price:
        Precio del swing.

    kind:
        SWING_HIGH o SWING_LOW.

    confirmed:
        Indica si existe suficiente información a ambos lados
        del punto para considerarlo swing confirmado.
    """

    index: int
    timestamp: int
    price: float
    kind: str
    confirmed: bool = True


@dataclass(frozen=True)
class StructureLevels:
    """
    Niveles estructurales principales.
    """

    support: float | None
    resistance: float | None
    previous_support: float | None = None
    previous_resistance: float | None = None


@dataclass(frozen=True)
class StructureResult:
    """
    Resultado completo del análisis estructural.
    """

    state: str
    swing_highs: tuple[SwingPoint, ...]
    swing_lows: tuple[SwingPoint, ...]
    levels: StructureLevels
    breakout: str
    breakout_level: float | None
    price: float
    candle_closed: bool
    confidence: float


# ============================================================
# VALIDACIÓN
# ============================================================

def _validate_candles(
    candles: Sequence[Candle],
    minimum: int = 1,
) -> list[Candle]:
    """
    Valida una serie de velas antes de analizarla.
    """

    if candles is None:
        raise ValueError("candles no puede ser None.")

    data = list(candles)

    if len(data) < minimum:
        raise StructureError(
            f"Se necesitan al menos {minimum} velas; "
            f"se recibieron {len(data)}."
        )

    for candle in data:
        if not isinstance(candle, Candle):
            raise TypeError(
                "Todos los elementos deben ser objetos Candle."
            )

        values = (
            candle.open,
            candle.high,
            candle.low,
            candle.close,
            candle.volume,
        )

        for value in values:
            if not math.isfinite(float(value)):
                raise StructureError(
                    "Las velas contienen valores no finitos."
                )

        high = float(candle.high)
        low = float(candle.low)
        open_price = float(candle.open)
        close = float(candle.close)
        volume = float(candle.volume)

        if high < low:
            raise StructureError(
                "Una vela contiene high menor que low."
            )

        if high < open_price or high < close:
            raise StructureError(
                "El high de una vela no puede ser menor "
                "que open o close."
            )

        if low > open_price or low > close:
            raise StructureError(
                "El low de una vela no puede ser mayor "
                "que open o close."
            )

        if volume < 0:
            raise StructureError(
                "El volumen no puede ser negativo."
            )

    return data


def _validate_window(window: int) -> int:
    """
    Valida la ventana utilizada para detectar swings.
    """

    if not isinstance(window, int):
        raise ValueError("window debe ser un entero.")

    if window < 1:
        raise ValueError(
            "window debe ser mayor o igual que 1."
        )

    return window


def _validate_price(price: float) -> float:
    """
    Valida un precio.
    """

    value = float(price)

    if not math.isfinite(value):
        raise ValueError(
            "price debe ser un número finito."
        )

    if value <= 0:
        raise ValueError(
            "price debe ser mayor que cero."
        )

    return value


# ============================================================
# SWINGS
# ============================================================

def find_swing_highs(
    candles: Sequence[Candle],
    window: int = 2,
) -> list[SwingPoint]:
    """
    Detecta Swing Highs confirmados.

    Un máximo se considera swing high cuando su high es
    mayor o igual que los highs de las 'window' velas
    anteriores y posteriores.

    La última zona sin suficientes velas posteriores
    no se considera confirmada.

    Esto es deliberado:
    no queremos utilizar información futura inexistente
    para crear una señal falsa.
    """

    window = _validate_window(window)

    data = _validate_candles(
        candles,
        minimum=(window * 2) + 1,
    )

    swings: list[SwingPoint] = []

    start = window
    end = len(data) - window

    for index in range(start, end):
        current_high = float(data[index].high)

        left_highs = [
            float(data[position].high)
            for position in range(
                index - window,
                index,
            )
        ]

        right_highs = [
            float(data[position].high)
            for position in range(
                index + 1,
                index + window + 1,
            )
        ]

        if (
            current_high >= max(left_highs)
            and current_high >= max(right_highs)
        ):
            swings.append(
                SwingPoint(
                    index=index,
                    timestamp=data[index].timestamp,
                    price=current_high,
                    kind="SWING_HIGH",
                    confirmed=True,
                )
            )

    return swings


def find_swing_lows(
    candles: Sequence[Candle],
    window: int = 2,
) -> list[SwingPoint]:
    """
    Detecta Swing Lows confirmados.

    Un mínimo se considera swing low cuando su low es
    menor o igual que los lows de las 'window' velas
    anteriores y posteriores.
    """

    window = _validate_window(window)

    data = _validate_candles(
        candles,
        minimum=(window * 2) + 1,
    )

    swings: list[SwingPoint] = []

    start = window
    end = len(data) - window

    for index in range(start, end):
        current_low = float(data[index].low)

        left_lows = [
            float(data[position].low)
            for position in range(
                index - window,
                index,
            )
        ]

        right_lows = [
            float(data[position].low)
            for position in range(
                index + 1,
                index + window + 1,
            )
        ]

        if (
            current_low <= min(left_lows)
            and current_low <= min(right_lows)
        ):
            swings.append(
                SwingPoint(
                    index=index,
                    timestamp=data[index].timestamp,
                    price=current_low,
                    kind="SWING_LOW",
                    confirmed=True,
                )
            )

    return swings


# ============================================================
# ÚLTIMOS SWINGS
# ============================================================

def latest_swing_high(
    swings: Sequence[SwingPoint],
) -> SwingPoint | None:
    """
    Devuelve el Swing High confirmado más reciente.
    """

    for swing in reversed(swings):
        if swing.kind == "SWING_HIGH":
            return swing

    return None


def latest_swing_low(
    swings: Sequence[SwingPoint],
) -> SwingPoint | None:
    """
    Devuelve el Swing Low confirmado más reciente.
    """

    for swing in reversed(swings):
        if swing.kind == "SWING_LOW":
            return swing

    return None


# ============================================================
# CLASIFICACIÓN HH / HL / LH / LL
# ============================================================

def classify_highs(
    swing_highs: Sequence[SwingPoint],
) -> list[str | None]:
    """
    Clasifica máximos consecutivos como:

        HH = Higher High
        LH = Lower High

    El primer swing no puede clasificarse porque no tiene
    referencia anterior.
    """

    result: list[str | None] = [None] * len(swing_highs)

    previous_price: float | None = None

    for index, swing in enumerate(swing_highs):
        if swing.kind != "SWING_HIGH":
            continue

        if previous_price is None:
            result[index] = None
        elif swing.price > previous_price:
            result[index] = "HH"
        elif swing.price < previous_price:
            result[index] = "LH"
        else:
            result[index] = "EQUAL_HIGH"

        previous_price = swing.price

    return result


def classify_lows(
    swing_lows: Sequence[SwingPoint],
) -> list[str | None]:
    """
    Clasifica mínimos consecutivos como:

        HL = Higher Low
        LL = Lower Low
    """

    result: list[str | None] = [None] * len(swing_lows)

    previous_price: float | None = None

    for index, swing in enumerate(swing_lows):
        if swing.kind != "SWING_LOW":
            continue

        if previous_price is None:
            result[index] = None
        elif swing.price > previous_price:
            result[index] = "HL"
        elif swing.price < previous_price:
            result[index] = "LL"
        else:
            result[index] = "EQUAL_LOW"

        previous_price = swing.price

    return result


# ============================================================
# ESTRUCTURA DE MERCADO
# ============================================================

def market_structure(
    swing_highs: Sequence[SwingPoint],
    swing_lows: Sequence[SwingPoint],
) -> str:
    """
    Determina la estructura general utilizando los dos
    últimos máximos y mínimos confirmados.

    BULLISH:
        último máximo > máximo anterior
        y último mínimo > mínimo anterior.

    BEARISH:
        último máximo < máximo anterior
        y último mínimo < mínimo anterior.

    RANGE:
        estructura mixta o lateral.

    INSUFFICIENT_DATA:
        no existen suficientes swings.
    """

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return "INSUFFICIENT_DATA"

    previous_high = float(swing_highs[-2].price)
    latest_high = float(swing_highs[-1].price)

    previous_low = float(swing_lows[-2].price)
    latest_low = float(swing_lows[-1].price)

    higher_high = latest_high > previous_high
    lower_high = latest_high < previous_high

    higher_low = latest_low > previous_low
    lower_low = latest_low < previous_low

    if higher_high and higher_low:
        return "BULLISH"

    if lower_high and lower_low:
        return "BEARISH"

    if (
        latest_high == previous_high
        and latest_low == previous_low
    ):
        return "RANGE"

    return "NEUTRAL"


# ============================================================
# NIVELES
# ============================================================

def structure_levels(
    swing_highs: Sequence[SwingPoint],
    swing_lows: Sequence[SwingPoint],
) -> StructureLevels:
    """
    Obtiene soporte y resistencia a partir de swings
    confirmados.

    Se utilizan los swings más recientes.

    Importante:
    esto representa niveles estructurales, no liquidez real
    del libro de órdenes.
    """

    resistance_values = [
        float(swing.price)
        for swing in swing_highs
        if swing.kind == "SWING_HIGH"
    ]

    support_values = [
        float(swing.price)
        for swing in swing_lows
        if swing.kind == "SWING_LOW"
    ]

    resistance = (
        resistance_values[-1]
        if resistance_values
        else None
    )

    previous_resistance = (
        resistance_values[-2]
        if len(resistance_values) >= 2
        else None
    )

    support = (
        support_values[-1]
        if support_values
        else None
    )

    previous_support = (
        support_values[-2]
        if len(support_values) >= 2
        else None
    )

    return StructureLevels(
        support=support,
        resistance=resistance,
        previous_support=previous_support,
        previous_resistance=previous_resistance,
    )


# ============================================================
# BREAKOUT / BREAKDOWN
# ============================================================

def detect_breakout(
    price: float,
    support: float | None,
    resistance: float | None,
    candle_closed: bool = True,
) -> str:
    """
    Detecta ruptura de estructura.

    Regla conservadora:

    BREAKOUT:
        precio > resistencia
        y vela cerrada.

    BREAKDOWN:
        precio < soporte
        y vela cerrada.

    Si la vela todavía está abierta se devuelve una señal
    potencial, nunca una ruptura confirmada.
    """

    price = _validate_price(price)

    if support is not None:
        support = _validate_price(support)

    if resistance is not None:
        resistance = _validate_price(resistance)

    if (
        support is not None
        and resistance is not None
        and support > resistance
    ):
        raise StructureError(
            "support no puede ser mayor que resistance."
        )

    if resistance is not None and price > resistance:
        if candle_closed:
            return "BREAKOUT"
        return "POTENTIAL_BREAKOUT"

    if support is not None and price < support:
        if candle_closed:
            return "BREAKDOWN"
        return "POTENTIAL_BREAKDOWN"

    return "NONE"


# ============================================================
# CONFIANZA ESTRUCTURAL
# ============================================================

def structure_confidence(
    state: str,
    swing_high_count: int,
    swing_low_count: int,
    candle_closed: bool,
) -> float:
    """
    Calcula una confianza estructural conservadora de 0 a 100.

    No es probabilidad de ganar una operación.

    Es una medida de cuánto soporte tiene la clasificación
    estructural disponible.
    """

    if state not in VALID_STRUCTURE_STATES:
        raise ValueError(
            f"Estado estructural inválido: {state}"
        )

    if swing_high_count < 0 or swing_low_count < 0:
        raise ValueError(
            "Los conteos de swings no pueden ser negativos."
        )

    if state == "INSUFFICIENT_DATA":
        return 0.0

    score = 0.0

    # Base por existencia de swings.
    if swing_high_count >= 2:
        score += 30.0

    if swing_low_count >= 2:
        score += 30.0

    # Estructura claramente definida.
    if state in {"BULLISH", "BEARISH"}:
        score += 30.0
    elif state == "RANGE":
        score += 20.0
    else:
        score += 10.0

    # Confirmación de vela.
    if candle_closed:
        score += 10.0

    return min(100.0, max(0.0, score))


# ============================================================
# ANÁLISIS COMPLETO
# ============================================================

def analyze_structure(
    candles: Sequence[Candle],
    window: int = 2,
) -> StructureResult:
    """
    Ejecuta el análisis estructural completo.

    Este es el punto de entrada principal que utilizará
    market/scoring/strategy en las siguientes capas.
    """

    data = _validate_candles(
        candles,
        minimum=(window * 2) + 1,
    )

    swing_highs = find_swing_highs(
        data,
        window=window,
    )

    swing_lows = find_swing_lows(
        data,
        window=window,
    )

    state = market_structure(
        swing_highs=swing_highs,
        swing_lows=swing_lows,
    )

    levels = structure_levels(
        swing_highs=swing_highs,
        swing_lows=swing_lows,
    )

    latest_candle = data[-1]

    breakout = detect_breakout(
        price=float(latest_candle.close),
        support=levels.support,
        resistance=levels.resistance,
        candle_closed=latest_candle.is_closed,
    )

    breakout_level: float | None = None

    if breakout in {
        "BREAKOUT",
        "POTENTIAL_BREAKOUT",
    }:
        breakout_level = levels.resistance

    elif breakout in {
        "BREAKDOWN",
        "POTENTIAL_BREAKDOWN",
    }:
        breakout_level = levels.support

    confidence = structure_confidence(
        state=state,
        swing_high_count=len(swing_highs),
        swing_low_count=len(swing_lows),
        candle_closed=latest_candle.is_closed,
    )

    return StructureResult(
        state=state,
        swing_highs=tuple(swing_highs),
        swing_lows=tuple(swing_lows),
        levels=levels,
        breakout=breakout,
        breakout_level=breakout_level,
        price=float(latest_candle.close),
        candle_closed=latest_candle.is_closed,
        confidence=confidence,
    )


# ============================================================
# SNAPSHOT
# ============================================================

def structure_snapshot(
    candles: Sequence[Candle],
    window: int = 2,
) -> dict[str, object]:
    """
    Devuelve el análisis en formato serializable.

    Este formato será útil posteriormente para Telegram,
    logs, scoring y almacenamiento histórico.
    """

    result = analyze_structure(
        candles,
        window=window,
    )

    high_classification = classify_highs(
        result.swing_highs
    )

    low_classification = classify_lows(
        result.swing_lows
    )

    latest_high = latest_swing_high(
        result.swing_highs
    )

    latest_low = latest_swing_low(
        result.swing_lows
    )

    return {
        "state": result.state,

        "support": result.levels.support,
        "resistance": result.levels.resistance,

        "previous_support": (
            result.levels.previous_support
        ),

        "previous_resistance": (
            result.levels.previous_resistance
        ),

        "breakout": result.breakout,
        "breakout_level": result.breakout_level,

        "price": result.price,

        "candle_closed": result.candle_closed,

        "confidence": result.confidence,

        "swing_high_count": len(
            result.swing_highs
        ),

        "swing_low_count": len(
            result.swing_lows
        ),

        "latest_swing_high": (
            latest_high.price
            if latest_high is not None
            else None
        ),

        "latest_swing_low": (
            latest_low.price
            if latest_low is not None
            else None
        ),

        "high_structure": (
            high_classification[-1]
            if high_classification
            else None
        ),

        "low_structure": (
            low_classification[-1]
            if low_classification
            else None
        ),
    }