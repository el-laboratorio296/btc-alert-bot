from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from radar.models import (
    AssetMarketData,
    Candle,
    MarketTicker,
    TimeframeData,
)


class MarketDataError(Exception):
    """Error controlado en la capa de datos de mercado."""


class MarketService:
    """
    Orquestador principal de datos de mercado.

    Binance:
        Fuente principal para OHLCV y análisis técnico.

    CoinGecko:
        Fuente principal para precio, capitalización,
        volumen y métricas generales de mercado.

    Regla importante:
        No se mezclan velas de diferentes proveedores.
        Binance alimenta exclusivamente las temporalidades.
        CoinGecko alimenta exclusivamente los datos de mercado.
    """

    DEFAULT_INTERVALS = (
        "15m",
        "1h",
        "4h",
        "1d",
    )

    MAX_LIMIT = 1000

    ALLOWED_INTERVALS = {
        "1m",
        "3m",
        "5m",
        "15m",
        "30m",
        "1h",
        "2h",
        "4h",
        "6h",
        "8h",
        "12h",
        "1d",
        "3d",
        "1w",
        "1M",
    }

    def __init__(
        self,
        binance: Any,
        coingecko: Any,
    ) -> None:
        if binance is None:
            raise TypeError(
                "binance no puede ser None."
            )

        if coingecko is None:
            raise TypeError(
                "coingecko no puede ser None."
            )

        self.binance = binance
        self.coingecko = coingecko

    # =========================================================
    # VALIDACIÓN
    # =========================================================

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        if not isinstance(symbol, str):
            raise ValueError(
                "symbol debe ser una cadena."
            )

        cleaned = symbol.strip().upper()

        if not cleaned:
            raise ValueError(
                "symbol no puede estar vacío."
            )

        if cleaned.endswith("USDT"):
            return cleaned

        return f"{cleaned}USDT"

    @staticmethod
    def _base_symbol(symbol: str) -> str:
        normalized = MarketService._normalize_symbol(
            symbol
        )

        if normalized.endswith("USDT"):
            return normalized[:-4]

        return normalized

    @classmethod
    def _validate_intervals(
        cls,
        intervals: Sequence[str],
    ) -> tuple[str, ...]:
        if intervals is None:
            raise ValueError(
                "intervals no puede ser None."
            )

        if isinstance(intervals, str):
            raise ValueError(
                "intervals debe ser una secuencia de temporalidades."
            )

        try:
            values = tuple(intervals)
        except TypeError as exc:
            raise ValueError(
                "intervals debe ser iterable."
            ) from exc

        if not values:
            raise ValueError(
                "Debe existir al menos una temporalidad."
            )

        normalized: list[str] = []

        for interval in values:
            if not isinstance(interval, str):
                raise ValueError(
                    "Cada temporalidad debe ser una cadena."
                )

            value = interval.strip()

            if not value:
                raise ValueError(
                    "Una temporalidad no puede estar vacía."
                )

            if value not in cls.ALLOWED_INTERVALS:
                raise ValueError(
                    f"Temporalidad no soportada: {value}"
                )

            if value in normalized:
                raise ValueError(
                    f"Temporalidad duplicada: {value}"
                )

            normalized.append(value)

        return tuple(normalized)

    @classmethod
    def _validate_limit(
        cls,
        limit: int,
    ) -> int:
        if isinstance(limit, bool):
            raise ValueError(
                "limit debe ser un entero positivo."
            )

        if not isinstance(limit, int):
            raise ValueError(
                "limit debe ser un entero."
            )

        if limit <= 0:
            raise ValueError(
                "limit debe ser mayor que cero."
            )

        if limit > cls.MAX_LIMIT:
            raise ValueError(
                f"limit no puede superar {cls.MAX_LIMIT}."
            )

        return limit

    # =========================================================
    # VALIDACIÓN NUMÉRICA
    # =========================================================

    @staticmethod
    def _finite_number(
        value: Any,
        field_name: str,
        *,
        allow_zero: bool = True,
    ) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise MarketDataError(
                f"{field_name} no es numérico."
            ) from exc

        if number != number:
            raise MarketDataError(
                f"{field_name} contiene NaN."
            )

        if number in (
            float("inf"),
            float("-inf"),
        ):
            raise MarketDataError(
                f"{field_name} contiene infinito."
            )

        if not allow_zero and number <= 0:
            raise MarketDataError(
                f"{field_name} debe ser mayor que cero."
            )

        return number

    # =========================================================
    # VALIDACIÓN DE TICKER
    # =========================================================

    @classmethod
    def _build_ticker(
        cls,
        symbol: str,
        raw: Mapping[str, Any],
    ) -> MarketTicker:
        if not isinstance(raw, Mapping):
            raise MarketDataError(
                "CoinGecko no devolvió un objeto de mercado válido."
            )

        if "price" not in raw:
            raise MarketDataError(
                "Falta price en los datos de mercado."
            )

        price = cls._finite_number(
            raw.get("price"),
            "price",
            allow_zero=False,
        )

        market_cap = cls._finite_number(
            raw.get("market_cap", 0.0),
            "market_cap",
        )

        volume_24h = cls._finite_number(
            raw.get("volume_24h", 0.0),
            "volume_24h",
        )

        change_1h = cls._finite_number(
            raw.get("change_1h", 0.0),
            "change_1h",
        )

        change_24h = cls._finite_number(
            raw.get("change_24h", 0.0),
            "change_24h",
        )

        change_7d = cls._finite_number(
            raw.get("change_7d", 0.0),
            "change_7d",
        )

        return MarketTicker(
            symbol=symbol,
            price=price,
            market_cap=market_cap,
            volume_24h=volume_24h,
            change_1h=change_1h,
            change_24h=change_24h,
            change_7d=change_7d,
        )

    # =========================================================
    # VALIDACIÓN DE VELAS
    # =========================================================

    @classmethod
    def _validate_candle(
        cls,
        candle: Any,
        timeframe: str,
    ) -> Candle:
        if not isinstance(candle, Candle):
            raise MarketDataError(
                f"Vela inválida en {timeframe}."
            )

        if not isinstance(
            candle.timestamp,
            int,
        ):
            raise MarketDataError(
                f"Timestamp inválido en {timeframe}."
            )

        if candle.timestamp <= 0:
            raise MarketDataError(
                f"Timestamp inválido en {timeframe}."
            )

        open_price = cls._finite_number(
            candle.open,
            f"{timeframe}.open",
            allow_zero=False,
        )

        high_price = cls._finite_number(
            candle.high,
            f"{timeframe}.high",
            allow_zero=False,
        )

        low_price = cls._finite_number(
            candle.low,
            f"{timeframe}.low",
            allow_zero=False,
        )

        close_price = cls._finite_number(
            candle.close,
            f"{timeframe}.close",
            allow_zero=False,
        )

        volume = cls._finite_number(
            candle.volume,
            f"{timeframe}.volume",
        )

        if high_price < low_price:
            raise MarketDataError(
                f"High menor que low en {timeframe}."
            )

        if not (
            low_price
            <= open_price
            <= high_price
        ):
            raise MarketDataError(
                f"Open fuera del rango de la vela en {timeframe}."
            )

        if not (
            low_price
            <= close_price
            <= high_price
        ):
            raise MarketDataError(
                f"Close fuera del rango de la vela en {timeframe}."
            )

        return Candle(
            timestamp=candle.timestamp,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
            is_closed=bool(
                candle.is_closed
            ),
        )

    @classmethod
    def _validate_timeframe(
        cls,
        timeframe: str,
        data: Any,
    ) -> TimeframeData:
        if not isinstance(
            data,
            TimeframeData,
        ):
            raise MarketDataError(
                f"Datos inválidos para {timeframe}."
            )

        candles = data.candles

        if not isinstance(
            candles,
            list,
        ):
            try:
                candles = list(candles)
            except TypeError as exc:
                raise MarketDataError(
                    f"Las velas de {timeframe} no son válidas."
                ) from exc

        if not candles:
            raise MarketDataError(
                f"Binance no devolvió velas para {timeframe}."
            )

        validated: list[Candle] = []

        previous_timestamp: int | None = None

        for candle in candles:
            validated_candle = cls._validate_candle(
                candle,
                timeframe,
            )

            if (
                previous_timestamp is not None
                and validated_candle.timestamp
                <= previous_timestamp
            ):
                raise MarketDataError(
                    f"Velas fuera de orden en {timeframe}."
                )

            validated.append(
                validated_candle
            )

            previous_timestamp = (
                validated_candle.timestamp
            )

        return TimeframeData(
            timeframe=timeframe,
            candles=validated,
            quality=data.quality,
        )

    # =========================================================
    # OBTENER ACTIVO
    # =========================================================

    def get_asset(
        self,
        symbol: str,
        intervals: Sequence[str] | None = None,
        limit: int = 200,
    ) -> AssetMarketData:
        normalized_symbol = self._normalize_symbol(
            symbol
        )

        base_symbol = self._base_symbol(
            normalized_symbol
        )

        if intervals is None:
    raise ValueError(
        "intervals no puede ser None."
    )

selected_intervals = self._validate_intervals(
    intervals
)

      

        # -----------------------------------------------------
        # 1. CoinGecko
        # -----------------------------------------------------

        try:
            raw_market = (
                self.coingecko.get_asset_market(
                    base_symbol
                )
            )
        except Exception as exc:
            raise MarketDataError(
                f"No se pudo obtener mercado de {base_symbol} "
                f"desde CoinGecko: {exc}"
            ) from exc

        if not raw_market:
            raise MarketDataError(
                f"CoinGecko no devolvió datos para {base_symbol}."
            )

        ticker = self._build_ticker(
            normalized_symbol,
            raw_market,
        )

        # -----------------------------------------------------
        # 2. Binance
        # -----------------------------------------------------

        try:
            raw_timeframes = (
                self.binance.get_multi_timeframe(
                    normalized_symbol,
                    intervals=selected_intervals,
                    limit=validated_limit,
                )
            )
        except TypeError:
            # Compatibilidad con implementaciones que
            # utilizan argumentos posicionales.
            try:
                raw_timeframes = (
                    self.binance.get_multi_timeframe(
                        normalized_symbol,
                        selected_intervals,
                        validated_limit,
                    )
                )
            except Exception as exc:
                raise MarketDataError(
                    f"No se pudo obtener OHLCV de "
                    f"{normalized_symbol} desde Binance: {exc}"
                ) from exc

        except Exception as exc:
            raise MarketDataError(
                f"No se pudo obtener OHLCV de "
                f"{normalized_symbol} desde Binance: {exc}"
            ) from exc

        if not isinstance(
            raw_timeframes,
            Mapping,
        ):
            raise MarketDataError(
                "Binance no devolvió un mapa de temporalidades válido."
            )

        # -----------------------------------------------------
        # 3. Verificar que no falte ninguna temporalidad
        # -----------------------------------------------------

        missing = [
            timeframe
            for timeframe in selected_intervals
            if timeframe not in raw_timeframes
        ]

        if missing:
            raise MarketDataError(
                "Binance no devolvió las temporalidades requeridas: "
                + ", ".join(missing)
            )

        # -----------------------------------------------------
        # 4. Validar todas las velas
        # -----------------------------------------------------

        validated_timeframes: dict[
            str,
            TimeframeData,
        ] = {}

        for timeframe in selected_intervals:
            validated_timeframes[timeframe] = (
                self._validate_timeframe(
                    timeframe,
                    raw_timeframes[timeframe],
                )
            )

        # -----------------------------------------------------
        # 5. Construir objeto final
        # -----------------------------------------------------

        return AssetMarketData(
            symbol=normalized_symbol,
            ticker=ticker,
            timeframes=validated_timeframes,
        )

    # =========================================================
    # MÉTODOS DE CONVENIENCIA
    # =========================================================

    def get_price(
        self,
        symbol: str,
    ) -> float:
        return self.get_asset(
            symbol,
            intervals=("1h",),
            limit=2,
        ).price

    def get_timeframes(
        self,
        symbol: str,
        intervals: Sequence[str] | None = None,
        limit: int = 200,
    ) -> dict[str, TimeframeData]:
        asset = self.get_asset(
            symbol,
            intervals=intervals,
            limit=limit,
        )

        return asset.timeframes

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 200,
    ) -> list[Candle]:
        normalized_intervals = self._validate_intervals(
            (timeframe,)
        )

        asset = self.get_asset(
            symbol,
            intervals=normalized_intervals,
            limit=limit,
        )

        data = asset.get_timeframe(
            normalized_intervals[0]
        )

        if data is None:
            raise MarketDataError(
                f"No existen datos para {timeframe}."
            )

        return list(data.candles)

    def get_last_candle(
        self,
        symbol: str,
        timeframe: str,
    ) -> Candle:
        candles = self.get_candles(
            symbol,
            timeframe,
            limit=2,
        )

        if not candles:
            raise MarketDataError(
                f"No existe última vela para {timeframe}."
            )

        return candles[-1]

    # =========================================================
    # HEALTH CHECK
    # =========================================================

    def health_check(
        self,
        symbol: str = "BTC",
    ) -> dict[str, Any]:
        try:
            asset = self.get_asset(
                symbol,
                intervals=("15m", "1h"),
                limit=10,
            )

            return {
                "ok": True,
                "symbol": asset.symbol,
                "price": asset.price,
                "timeframes": list(
                    asset.timeframes.keys()
                ),
                "message": "Market data OK",
            }

        except Exception as exc:
            return {
                "ok": False,
                "symbol": symbol,
                "price": None,
                "timeframes": [],
                "message": str(exc),
            }