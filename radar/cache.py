from __future__ import annotations

import time
from typing import Any

from radar.cache import MarketCache
from radar.models import (
    AssetMarketData,
    Candle,
    DataQuality,
    MarketTicker,
    TimeframeData,
)
from radar.providers.binance import BinanceProvider
from radar.providers.coingecko import CoinGeckoProvider


class MarketDataError(Exception):
    """Error general de la capa de datos de mercado."""


class MarketData:
    """
    Orquestador principal de datos del Radar.

    Responsabilidades:
    - Obtener datos técnicos desde Binance.
    - Obtener información de mercado desde CoinGecko.
    - Utilizar caché para reducir llamadas innecesarias.
    - Validar velas antes de entregarlas al motor.
    - Mantener separadas las responsabilidades de cada proveedor.

    Binance:
        OHLCV técnico.

    CoinGecko:
        Precio, capitalización, volumen, cambios y universo de mercado.
    """

    # ============================================================
    # CONFIGURACIÓN
    # ============================================================

    TIMEFRAME_TTL = {
        "15m": 90,
        "1h": 300,
        "4h": 900,
        "1d": 3600,
    }

    # Cantidad mínima de velas que necesitamos para trabajar
    MIN_CANDLES = {
        "15m": 100,
        "1h": 100,
        "4h": 100,
        "1d": 100,
    }

    # Máximo de velas que conservaremos en memoria del objeto.
    MAX_CANDLES = {
        "15m": 500,
        "1h": 500,
        "4h": 500,
        "1d": 500,
    }

    SUPPORTED_TIMEFRAMES = (
        "15m",
        "1h",
        "4h",
        "1d",
    )

    def __init__(
        self,
        binance: BinanceProvider | None = None,
        coingecko: CoinGeckoProvider | None = None,
        cache: MarketCache | None = None,
    ) -> None:
        self.binance = binance or BinanceProvider()
        self.coingecko = coingecko or CoinGeckoProvider()
        self.cache = cache or MarketCache()

    # ============================================================
    # NORMALIZACIÓN
    # ============================================================

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        """
        Normaliza símbolos recibidos por el Radar.

        Ejemplos:
            BTC       -> BTC
            btc       -> BTC
            BTCUSDT   -> BTC
            ETHUSDT   -> ETH
        """

        if not symbol or not symbol.strip():
            raise ValueError("El símbolo no puede estar vacío.")

        normalized = symbol.strip().upper()

        if normalized.endswith("USDT"):
            normalized = normalized[:-4]

        return normalized

    @staticmethod
    def cache_key(
        symbol: str,
        timeframe: str,
    ) -> str:
        """
        Genera una clave única para el caché.
        """

        normalized = MarketData.normalize_symbol(symbol)

        return f"binance:{normalized}:{timeframe}"

    # ============================================================
    # VALIDACIÓN
    # ============================================================

    def validate_candles(
        self,
        candles: list[Candle],
        timeframe: str,
    ) -> tuple[bool, str]:
        """
        Valida una serie de velas antes de permitir que llegue
        al motor de análisis.

        No genera señales.
        """

        if timeframe not in self.SUPPORTED_TIMEFRAMES:
            return False, f"Timeframe no soportado: {timeframe}"

        minimum = self.MIN_CANDLES[timeframe]

        if len(candles) < minimum:
            return (
                False,
                f"Datos insuficientes: {len(candles)}/{minimum}",
            )

        previous_timestamp: int | None = None

        for candle in candles:

            # ----------------------------------------------------
            # Valores básicos
            # ----------------------------------------------------

            if candle.open <= 0:
                return False, "Open inválido."

            if candle.high <= 0:
                return False, "High inválido."

            if candle.low <= 0:
                return False, "Low inválido."

            if candle.close <= 0:
                return False, "Close inválido."

            if candle.volume < 0:
                return False, "Volume inválido."

            # ----------------------------------------------------
            # Estructura OHLC
            # ----------------------------------------------------

            if candle.high < candle.low:
                return False, "High menor que Low."

            if candle.high < candle.open:
                return False, "High menor que Open."

            if candle.high < candle.close:
                return False, "High menor que Close."

            if candle.low > candle.open:
                return False, "Low mayor que Open."

            if candle.low > candle.close:
                return False, "Low mayor que Close."

            # ----------------------------------------------------
            # Orden cronológico
            # ----------------------------------------------------

            if previous_timestamp is not None:
                if candle.timestamp <= previous_timestamp:
                    return False, "Velas fuera de orden cronológico."

            previous_timestamp = candle.timestamp

        return True, "OK"

    # ============================================================
    # CONVERSIÓN
    # ============================================================

    @staticmethod
    def candles_to_payload(
        candles: list[Candle],
    ) -> dict[str, Any]:
        """
        Convierte objetos Candle en JSON compatible con el caché.
        """

        return {
            "candles": [
                {
                    "timestamp": candle.timestamp,
                    "open": candle.open,
                    "high": candle.high,
                    "low": candle.low,
                    "close": candle.close,
                    "volume": candle.volume,
                    "is_closed": candle.is_closed,
                }
                for candle in candles
            ]
        }

    @staticmethod
    def payload_to_candles(
        payload: dict[str, Any],
    ) -> list[Candle]:
        """
        Reconstruye objetos Candle desde el caché.
        """

        raw_candles = payload.get("candles")

        if not isinstance(raw_candles, list):
            return []

        candles: list[Candle] = []

        for item in raw_candles:

            if not isinstance(item, dict):
                continue

            try:
                candle = Candle(
                    timestamp=int(item["timestamp"]),
                    open=float(item["open"]),
                    high=float(item["high"]),
                    low=float(item["low"]),
                    close=float(item["close"]),
                    volume=float(item["volume"]),
                    is_closed=bool(
                        item.get("is_closed", True)
                    ),
                )

                candles.append(candle)

            except (
                KeyError,
                TypeError,
                ValueError,
            ):
                continue

        return candles

    # ============================================================
    # OBTENER VELAS
    # ============================================================

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 500,
    ) -> TimeframeData | None:
        """
        Obtiene velas de un activo.

        Flujo:

        1. Revisar caché.
        2. Si está fresco, utilizarlo.
        3. Si no existe, consultar Binance.
        4. Validar.
        5. Guardar en caché.
        6. Devolver TimeframeData.
        """

        normalized_symbol = self.normalize_symbol(symbol)

        if timeframe not in self.SUPPORTED_TIMEFRAMES:
            raise ValueError(
                f"Timeframe no soportado: {timeframe}"
            )

        limit = max(
            self.MIN_CANDLES[timeframe],
            min(limit, self.MAX_CANDLES[timeframe]),
        )

        key = self.cache_key(
            normalized_symbol,
            timeframe,
        )

        ttl = self.TIMEFRAME_TTL[timeframe]

        # ========================================================
        # 1. CACHE
        # ========================================================

        cached_payload = self.cache.get(
            key=key,
            max_age_seconds=ttl,
        )

        if cached_payload is not None:

            candles = self.payload_to_candles(
                cached_payload
            )

            candles = candles[-limit:]

            valid, message = self.validate_candles(
                candles,
                timeframe,
            )

            if valid:

                quality = self.build_quality(
                    candles=candles,
                    source="cache/binance",
                )

                return TimeframeData(
                    timeframe=timeframe,
                    candles=candles,
                    quality=quality,
                )

            # Si el caché está corrupto o inválido,
            # lo eliminamos y continuamos con Binance.
            self.cache.delete(key)

        # ========================================================
        # 2. BINANCE
        # ========================================================

        try:
            raw_candles = self.binance.get_klines(
                symbol=normalized_symbol,
                interval=timeframe,
                limit=limit,
            )

        except Exception as exc:
            raise MarketDataError(
                f"Error obteniendo "
                f"{normalized_symbol} {timeframe}: {exc}"
            ) from exc

        if not raw_candles:
            raise MarketDataError(
                f"Binance no devolvió datos para "
                f"{normalized_symbol} {timeframe}."
            )

        candles = self.normalize_binance_candles(
            raw_candles
        )

        valid, message = self.validate_candles(
            candles,
            timeframe,
        )

        if not valid:
            raise MarketDataError(
                f"Datos inválidos para "
                f"{normalized_symbol} {timeframe}: "
                f"{message}"
            )

        # ========================================================
        # 3. GUARDAR CACHE
        # ========================================================

        payload = self.candles_to_payload(
            candles
        )

        self.cache.set(
            key=key,
            payload=payload,
            source="binance",
        )

        # ========================================================
        # 4. QUALITY
        # ========================================================

        quality = self.build_quality(
            candles=candles,
            source="binance",
        )

        return TimeframeData(
            timeframe=timeframe,
            candles=candles,
            quality=quality,
        )

    # ============================================================
    # NORMALIZAR RESPUESTA BINANCE
    # ============================================================

    @staticmethod
    def normalize_binance_candles(
        raw_candles: list[Any],
    ) -> list[Candle]:
        """
        Convierte la respuesta normalizada del provider Binance
        a objetos Candle.

        El provider debe entregar una estructura compatible
        con Candle o con diccionarios equivalentes.
        """

        candles: list[Candle] = []

        for item in raw_candles:

            if isinstance(item, Candle):
                candles.append(item)
                continue

            if isinstance(item, dict):

                try:
                    candles.append(
                        Candle(
                            timestamp=int(
                                item["timestamp"]
                            ),
                            open=float(
                                item["open"]
                            ),
                            high=float(
                                item["high"]
                            ),
                            low=float(
                                item["low"]
                            ),
                            close=float(
                                item["close"]
                            ),
                            volume=float(
                                item["volume"]
                            ),
                            is_closed=bool(
                                item.get(
                                    "is_closed",
                                    True,
                                )
                            ),
                        )
                    )

                except (
                    KeyError,
                    TypeError,
                    ValueError,
                ):
                    continue

        return candles

    # ============================================================
    # DATA QUALITY
    # ============================================================

    def build_quality(
        self,
        candles: list[Candle],
        source: str,
    ) -> DataQuality:
        """
        Construye información de calidad de datos.

        La calidad acompaña a los datos y posteriormente será
        utilizada por el motor de señales para impedir señales
        basadas en información deficiente.
        """

        now = time.time()

        if not candles:
            return DataQuality(
                source=source,
                fetched_at=now,
                latest_candle_timestamp=0,
                is_complete=False,
                is_closed=False,
                age_seconds=0,
                message="Sin velas.",
            )

        latest = candles[-1]

        age_seconds = max(
            0,
            now - (
                latest.timestamp / 1000
                if latest.timestamp > 10_000_000_000
                else latest.timestamp
            ),
        )

        all_closed = all(
            candle.is_closed
            for candle in candles
        )

        return DataQuality(
            source=source,
            fetched_at=now,
            latest_candle_timestamp=latest.timestamp,
            is_complete=True,
            is_closed=all_closed,
            age_seconds=age_seconds,
            message="Datos válidos.",
        )

    # ============================================================
    # OBTENER ACTIVO COMPLETO
    # ============================================================

    def get_asset(
        self,
        symbol: str,
        timeframes: tuple[str, ...] | None = None,
    ) -> AssetMarketData:

        normalized_symbol = self.normalize_symbol(
            symbol
        )

        if timeframes is None:
            timeframes = self.SUPPORTED_TIMEFRAMES

        for timeframe in timeframes:
            if timeframe not in self.SUPPORTED_TIMEFRAMES:
                raise ValueError(
                    f"Timeframe no soportado: {timeframe}"
                )

        # ========================================================
        # TECHNICAL DATA
        # ========================================================

        timeframe_data: dict[
            str,
            TimeframeData,
        ] = {}

        for timeframe in timeframes:

            data = self.get_candles(
                symbol=normalized_symbol,
                timeframe=timeframe,
                limit=self.MAX_CANDLES[timeframe],
            )

            if data is None:
                raise MarketDataError(
                    f"No se pudieron obtener datos "
                    f"para {normalized_symbol} "
                    f"{timeframe}."
                )

            timeframe_data[timeframe] = data

        # ========================================================
        # MARKET TICKER
        # ========================================================

        ticker = self._get_ticker(
            normalized_symbol
        )

        if ticker is None:
            raise MarketDataError(
                f"No se pudo obtener ticker para "
                f"{normalized_symbol}."
            )

        # ========================================================
        # ASSET
        # ========================================================

        return AssetMarketData(
            symbol=normalized_symbol,
            ticker=ticker,
            timeframes=timeframe_data,
        )

    # ============================================================
    # TICKER
    # ============================================================

    def _get_ticker(
        self,
        symbol: str,
    ) -> MarketTicker | None:

        try:
            data = self.coingecko.get_asset_market(
                symbol=symbol
            )

        except Exception:
            return None

        if not data:
            return None

        if isinstance(data, MarketTicker):
            return data

        if not isinstance(data, dict):
            return None

        try:
            return MarketTicker(
                symbol=symbol,
                price=float(
                    data.get(
                        "price",
                        0,
                    )
                ),
                market_cap=float(
                    data.get(
                        "market_cap",
                        0,
                    )
                ),
                volume_24h=float(
                    data.get(
                        "volume_24h",
                        0,
                    )
                ),
                change_1h=float(
                    data.get(
                        "change_1h",
                        0,
                    )
                ),
                change_24h=float(
                    data.get(
                        "change_24h",
                        0,
                    )
                ),
                change_7d=float(
                    data.get(
                        "change_7d",
                        0,
                    )
                ),
            )

        except (
            TypeError,
            ValueError,
        ):
            return None

    # ============================================================
    # UNIVERSO DE MERCADO
    # ============================================================

    def get_market_universe(
        self,
        limit: int = 100,
    ) -> list[dict[str, Any]]:

        if limit <= 0:
            raise ValueError(
                "limit debe ser mayor que cero."
            )

        try:
            markets = self.coingecko.get_markets(
                limit=limit
            )
        except Exception as exc:
            raise MarketDataError(
                f"No se pudo obtener el universo "
                f"de mercado: {exc}"
            ) from exc

        if not markets:
            return []

        return markets

    # ============================================================
    # MERCADO GLOBAL
    # ============================================================

    def get_global_market(
        self,
    ) -> dict[str, Any]:

        try:
            data = self.coingecko.get_global_market()

        except Exception as exc:
            raise MarketDataError(
                f"No se pudo obtener el mercado global: "
                f"{exc}"
            ) from exc

        if not data:
            raise MarketDataError(
                "CoinGecko devolvió datos globales vacíos."
            )

        return data