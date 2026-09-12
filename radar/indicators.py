from __future__ import annotations

import math
from typing import Any, Sequence

from radar.models import Candle


class IndicatorError(Exception):
    """Error base del módulo de indicadores."""


# ============================================================
# VALIDACIÓN GENERAL
# ============================================================


def _validate_period(
    period: int,
    name: str = "period",
) -> int:
    if not isinstance(period, int):
        raise ValueError(
            f"{name} debe ser un entero."
        )

    if isinstance(period, bool):
        raise ValueError(
            f"{name} debe ser un entero."
        )

    if period < 1:
        raise ValueError(
            f"{name} debe ser mayor que cero."
        )

    return period


def _validate_values(
    values: Sequence[float],
    name: str = "values",
) -> list[float]:
    if values is None:
        raise ValueError(
            f"{name} no puede ser None."
        )

    data = list(values)

    if not data:
        raise ValueError(
            f"{name} no puede estar vacío."
        )

    result: list[float] = []

    for value in data:
        try:
            numeric = float(value)
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                f"{name} contiene un valor no numérico."
            ) from exc

        if not math.isfinite(numeric):
            raise ValueError(
                f"{name} contiene un valor no finito."
            )

        result.append(numeric)

    return result


def _validate_candles(
    candles: Sequence[Candle],
    minimum: int = 1,
) -> list[Candle]:
    if candles is None:
        raise ValueError(
            "candles no puede ser None."
        )

    data = list(candles)

    if len(data) < minimum:
        raise IndicatorError(
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
                raise IndicatorError(
                    "Las velas contienen valores no finitos."
                )

        if candle.high < candle.low:
            raise IndicatorError(
                "Una vela contiene high menor que low."
            )

        if candle.high < candle.open:
            raise IndicatorError(
                "Una vela contiene high menor que open."
            )

        if candle.high < candle.close:
            raise IndicatorError(
                "Una vela contiene high menor que close."
            )

        if candle.low > candle.open:
            raise IndicatorError(
                "Una vela contiene low mayor que open."
            )

        if candle.low > candle.close:
            raise IndicatorError(
                "Una vela contiene low mayor que close."
            )

        if candle.volume < 0:
            raise IndicatorError(
                "El volumen no puede ser negativo."
            )

    return data


# ============================================================
# EMA
# ============================================================


def ema(
    values: Sequence[float],
    period: int,
) -> list[float | None]:
    """
    Calcula EMA utilizando SMA como valor inicial.

    Devuelve una lista de igual longitud que values.

    Las posiciones sin datos suficientes contienen None.
    """

    period = _validate_period(
        period,
        "period",
    )

    data = _validate_values(
        values,
        "values",
    )

    result: list[float | None] = [
        None
    ] * len(data)

    if len(data) < period:
        return result

    initial_sma = (
        sum(data[:period]) / period
    )

    result[period - 1] = initial_sma

    multiplier = (
        2.0 / (period + 1.0)
    )

    previous = initial_sma

    for index in range(
        period,
        len(data),
    ):
        current = (
            (
                data[index] - previous
            )
            * multiplier
            + previous
        )

        result[index] = current
        previous = current

    return result


# ============================================================
# RSI
# ============================================================


def rsi(
    values: Sequence[float],
    period: int = 14,
) -> list[float | None]:
    """
    RSI utilizando el suavizado de Wilder.

    Referencias:

        < 30  -> sobreventa
        30-70 -> zona neutral
        > 70  -> sobrecompra
    """

    period = _validate_period(
        period,
        "period",
    )

    data = _validate_values(
        values,
        "values",
    )

    result: list[float | None] = [
        None
    ] * len(data)

    if len(data) <= period:
        return result

    gains: list[float] = []
    losses: list[float] = []

    for index in range(
        1,
        len(data),
    ):
        change = (
            data[index]
            - data[index - 1]
        )

        gains.append(
            max(change, 0.0)
        )

        losses.append(
            max(-change, 0.0)
        )

    average_gain = (
        sum(gains[:period])
        / period
    )

    average_loss = (
        sum(losses[:period])
        / period
    )

    def calculate_rsi(
        gain: float,
        loss: float,
    ) -> float:

        if loss == 0:

            if gain == 0:
                return 50.0

            return 100.0

        relative_strength = (
            gain / loss
        )

        value = 100.0 - (
            100.0
            / (
                1.0
                + relative_strength
            )
        )

        return max(
            0.0,
            min(100.0, value),
        )

    result[period] = calculate_rsi(
        average_gain,
        average_loss,
    )

    for index in range(
        period + 1,
        len(data),
    ):

        gain = gains[index - 1]
        loss = losses[index - 1]

        average_gain = (
            (
                average_gain
                * (period - 1)
            )
            + gain
        ) / period

        average_loss = (
            (
                average_loss
                * (period - 1)
            )
            + loss
        ) / period

        result[index] = calculate_rsi(
            average_gain,
            average_loss,
        )

    return result


# ============================================================
# TRUE RANGE
# ============================================================


def true_range(
    candles: Sequence[Candle],
) -> list[float]:
    """
    Calcula True Range para cada vela.

    Primera vela:

        high - low

    Velas siguientes:

        max(
            high - low,
            abs(high - previous_close),
            abs(low - previous_close)
        )
    """

    data = _validate_candles(
        candles
    )

    result: list[float] = []

    previous_close: float | None = None

    for candle in data:

        high = float(
            candle.high
        )

        low = float(
            candle.low
        )

        if previous_close is None:

            current_tr = (
                high - low
            )

        else:

            current_tr = max(
                high - low,
                abs(
                    high
                    - previous_close
                ),
                abs(
                    low
                    - previous_close
                ),
            )

        result.append(
            current_tr
        )

        previous_close = float(
            candle.close
        )

    return result


# ============================================================
# ATR
# ============================================================


def atr(
    candles: Sequence[Candle],
    period: int = 14,
) -> list[float | None]:
    """
    Average True Range usando suavizado de Wilder.
    """

    period = _validate_period(
        period,
        "period",
    )

    data = _validate_candles(
        candles,
        minimum=period,
    )

    ranges = true_range(
        data
    )

    result: list[float | None] = [
        None
    ] * len(data)

    if len(ranges) < period:
        return result

    initial_atr = (
        sum(ranges[:period])
        / period
    )

    result[period - 1] = (
        initial_atr
    )

    previous_atr = initial_atr

    for index in range(
        period,
        len(ranges),
    ):

        current_atr = (
            (
                previous_atr
                * (period - 1)
            )
            + ranges[index]
        ) / period

        result[index] = (
            current_atr
        )

        previous_atr = (
            current_atr
        )

    return result


# ============================================================
# VOLATILIDAD
# ============================================================


def volatility(
    values: Sequence[float],
    period: int = 20,
) -> list[float | None]:
    """
    Volatilidad histórica aproximada basada en retornos
    porcentuales simples.

    El resultado representa la desviación estándar
    de los retornos de la ventana, expresada en porcentaje.
    """

    period = _validate_period(
        period,
        "period",
    )

    data = _validate_values(
        values,
        "values",
    )

    result: list[float | None] = [
        None
    ] * len(data)

    if len(data) <= period:
        return result

    returns: list[float] = []

    for index in range(
        1,
        len(data),
    ):

        previous = data[
            index - 1
        ]

        current = data[
            index
        ]

        if previous == 0:

            returns.append(
                0.0
            )

        else:

            returns.append(
                (
                    (
                        current
                        / previous
                    )
                    - 1.0
                )
                * 100.0
            )

    for index in range(
        period,
        len(data),
    ):

        window = returns[
            index - period:index
        ]

        if not window:
            continue

        mean = (
            sum(window)
            / len(window)
        )

        variance = (
            sum(
                (
                    value - mean
                ) ** 2
                for value in window
            )
            / len(window)
        )

        result[index] = math.sqrt(
            variance
        )

    return result


# ============================================================
# MOMENTUM
# ============================================================


def momentum(
    values: Sequence[float],
    period: int = 10,
) -> list[float | None]:
    """
    Momentum porcentual.

    Fórmula:

        ((precio_actual / precio_hace_N) - 1) * 100
    """

    period = _validate_period(
        period,
        "period",
    )

    data = _validate_values(
        values,
        "values",
    )

    result: list[float | None] = [
        None
    ] * len(data)

    if len(data) <= period:
        return result

    for index in range(
        period,
        len(data),
    ):

        previous = data[
            index - period
        ]

        current = data[
            index
        ]

        if previous == 0:

            result[index] = None

        else:

            result[index] = (
                (
                    current
                    / previous
                )
                - 1.0
            ) * 100.0

    return result


# ============================================================
# VOLUMEN RELATIVO
# ============================================================


def relative_volume(
    candles: Sequence[Candle],
    period: int = 20,
) -> list[float | None]:
    """
    Volumen actual dividido por el volumen promedio
    de las N velas anteriores.

    > 1.0 = volumen superior al promedio.
    < 1.0 = volumen inferior al promedio.

    El volumen actual NO forma parte de su propia referencia.
    """

    period = _validate_period(
        period,
        "period",
    )

    data = _validate_candles(
        candles,
        minimum=period + 1,
    )

    result: list[float | None] = [
        None
    ] * len(data)

    for index in range(
        period,
        len(data),
    ):

        previous_volumes = [
            float(candle.volume)
            for candle in data[
                index - period:index
            ]
        ]

        average_volume = (
            sum(previous_volumes)
            / period
        )

        current_volume = float(
            data[index].volume
        )

        if average_volume <= 0:

            result[index] = None

        else:

            result[index] = (
                current_volume
                / average_volume
            )

    return result


# ============================================================
# TENDENCIA EMA
# ============================================================


def trend_from_emas(
    price: float,
    ema20: float | None,
    ema50: float | None,
    ema200: float | None,
) -> str:
    """
    Clasificación preliminar de tendencia basada en precio
    y medias exponenciales.

    No sustituye el análisis de estructura de mercado.
    """

    try:
        price_value = float(
            price
        )
    except (
        TypeError,
        ValueError,
    ) as exc:

        raise ValueError(
            "price debe ser numérico."
        ) from exc

    if not math.isfinite(
        price_value
    ):
        raise ValueError(
            "price debe ser un número finito."
        )

    if ema20 is None or ema50 is None:
        return "INSUFFICIENT_DATA"

    ema20_value = float(
        ema20
    )

    ema50_value = float(
        ema50
    )

    if not math.isfinite(
        ema20_value
    ):
        raise ValueError(
            "ema20 debe ser finito."
        )

    if not math.isfinite(
        ema50_value
    ):
        raise ValueError(
            "ema50 debe ser finito."
        )

    ema200_value: float | None

    if ema200 is None:

        ema200_value = None

    else:

        ema200_value = float(
            ema200
        )

        if not math.isfinite(
            ema200_value
        ):
            raise ValueError(
                "ema200 debe ser finito."
            )

    if (
        price_value
        > ema20_value
        > ema50_value
    ):

        if (
            ema200_value is not None
            and ema50_value
            > ema200_value
        ):
            return "BULLISH"

        return "BULLISH_WEAK"

    if (
        price_value
        < ema20_value
        < ema50_value
    ):

        if (
            ema200_value is not None
            and ema50_value
            < ema200_value
        ):
            return "BEARISH"

        return "BEARISH_WEAK"

    if (
        ema20_value >= ema50_value
        and price_value >= ema50_value
    ):
        return "NEUTRAL_BULLISH"

    if (
        ema20_value <= ema50_value
        and price_value <= ema50_value
    ):
        return "NEUTRAL_BEARISH"

    return "NEUTRAL"


# ============================================================
# RESUMEN DE INDICADORES
# ============================================================


def compute_indicators(
    candles: Sequence[Candle],
) -> dict[str, Any]:
    """
    Calcula el conjunto principal de indicadores.

    Incluye:

        EMA 20
        EMA 50
        EMA 200
        RSI 14
        ATR 14
        volatilidad 20
        momentum 10
        volumen relativo 20
        tendencia EMA

    El último valor puede pertenecer a una vela abierta.
    El consumidor debe consultar Candle.is_closed.
    """

    data = _validate_candles(
        candles
    )

    closes = [
        float(candle.close)
        for candle in data
    ]

    ema20_values = ema(
        closes,
        period=20,
    )

    ema50_values = ema(
        closes,
        period=50,
    )

    ema200_values = ema(
        closes,
        period=200,
    )

    rsi_values = rsi(
        closes,
        period=14,
    )

    atr_values = atr(
        data,
        period=14,
    )

    volatility_values = volatility(
        closes,
        period=20,
    )

    momentum_values = momentum(
        closes,
        period=10,
    )

    if len(data) >= 21:

        relative_volume_values = (
            relative_volume(
                data,
                period=20,
            )
        )

    else:

        relative_volume_values = [
            None
        ] * len(data)

    price = closes[-1]

    ema20_current = (
        ema20_values[-1]
    )

    ema50_current = (
        ema50_values[-1]
    )

    ema200_current = (
        ema200_values[-1]
    )

    rsi_current = (
        rsi_values[-1]
    )

    atr_current = (
        atr_values[-1]
    )

    volatility_current = (
        volatility_values[-1]
    )

    momentum_current = (
        momentum_values[-1]
    )

    relative_volume_current = (
        relative_volume_values[-1]
    )

    trend = trend_from_emas(
        price=price,
        ema20=ema20_current,
        ema50=ema50_current,
        ema200=ema200_current,
    )

    atr_percent: float | None = None

    if (
        atr_current is not None
        and price > 0
    ):

        atr_percent = (
            atr_current
            / price
        ) * 100.0

    return {
        "price": price,

        "ema20": ema20_current,
        "ema50": ema50_current,
        "ema200": ema200_current,

        "rsi14": rsi_current,

        "atr14": atr_current,
        "atr_percent": atr_percent,

        "volatility20": (
            volatility_current
        ),

        "momentum10": (
            momentum_current
        ),

        "relative_volume20": (
            relative_volume_current
        ),

        "trend": trend,

        "candles_count": len(data),

        "last_candle_timestamp": (
            data[-1].timestamp
        ),

        "last_candle_closed": (
            data[-1].is_closed
        ),
    }


# ============================================================
# UTILIDADES
# ============================================================


def latest_value(
    values: Sequence[float | None],
) -> float | None:
    """
    Devuelve el último valor válido de una serie.
    """

    for value in reversed(values):

        if value is not None:

            numeric = float(
                value
            )

            if math.isfinite(
                numeric
            ):
                return numeric

    return None


def indicator_snapshot(
    candles: Sequence[Candle],
) -> dict[str, Any]:
    """
    Alias semántico para obtener el snapshot actual.
    """

    return compute_indicators(
        candles
    )