from __future__ import annotations

import time
from typing import Any

from radar.cache import MarketCache, CacheError
from radar.models import (
    AssetMarketData,
    Candle,
    DataQuality,
    MarketTicker,
    TimeframeData,
)
from radar.providers.binance import (
    BinanceProvider,
    BinanceProviderError,
)
from radar.providers.coingecko import (
    CoinGeckoProvider,
    CoinGeckoProviderError,
)


class MarketDataError(Exception):
    """Error general de la capa de datos de mercado."""


class MarketDataManager:
    """
    Capa central de datos del Radar El Laboratorio.

    Responsabilidades:

    1. Obtener datos técnicos desde Binance.
    2. Obtener información de mercado desde CoinGecko.
    3. Validar las velas recibidas.
    4. Separar claramente los proveedores.
    5. Utilizar caché para reducir llamadas innecesarias.
    6. Evitar utilizar datos técnicos incompletos.
    7. Convertir las respuestas de los proveedores a los modelos
       internos del Radar.

    Binance:
        - Velas OHLCV.
        - 15m
        - 1h
        - 4h
        - 1d

    CoinGecko:
        - Precio.
        - Market cap.
        - Volumen 24h.
        - Variaciones 1h / 24h / 7d.
        - Datos globales del mercado.
    """

    DEFAULT_TIMEFRAMES = ("15m", "1h", "4h", "1d")

    DEFAULT_CANDLE_LIMIT = 500

    # TTL de caché para cada timeframe.
    # Debe ser suficientemente corto para no trabajar
    # con información excesivamente vieja.
    CACHE_TTL = {
        "15m": 10 * 60,
        "1h": 30 * 60,
        "4h": 2 * 60 * 60,
        "1d": 6 * 60 * 60,
    }

    # Información de mercado de CoinGecko.
    MARKET_TTL = 5 * 60
    GLOBAL_TTL = 10 * 60

    def __init__(
        self,
        binance: BinanceProvider | None = None,
        coingecko: CoinGeckoProvider | None = None,
        cache: MarketCache | None = None,
        clock=time.time,
    ) -> None:
        self.binance = (
            binance
            if binance is not None
            else BinanceProvider()
        )

        self.coingecko = (
            coingecko
            if coingecko is not None
            else CoinGeckoProvider()
        )

        self.cache = (
            cache
            if cache is not None
            else MarketCache()
        )

        self.clock = clock

    # ============================================================
    # UTILIDADES
    # ============================================================

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        if not symbol or not symbol.strip():
            raise ValueError("El símbolo no puede estar vacío.")

        return symbol.strip().upper().replace(
            "USDT",
            "",
        )

    @staticmethod
    def _cache_key(
        symbol: str,
        timeframe: str,
    ) -> str:
        normalized = MarketDataManager._normalize_symbol(symbol)

        return (
            f"binance:"
            f"{normalized}:"
            f"{timeframe}"
        )

    @staticmethod
    def _candle_to_dict(candle: Candle) -> dict[str, Any]:
        return {
            "timestamp": candle.timestamp,
            "open": candle.open,
            "high": candle.high,
            "low": candle.low,
            "close": candle.close,
            "volume": candle.volume,
            "is_closed": candle.is_closed,
        }

    @staticmethod
    def _candle_from_dict(data: dict[str, Any]) -> Candle:
        return Candle(
            timestamp=int(data["timestamp"]),
            open=float(data["open"]),
            high=float(data["high"]),
            low=float(data["low"]),
            close=float(data["close"]),
            volume=float(data["volume"]),
            is_closed=bool(
                data.get("is_closed", True)
            ),
        )

    # ============================================================
    # VALIDACIÓN DE VELAS
    # ============================================================

    @staticmethod
    def _validate_candles(
        candles: list[Candle],
        timeframe: str,
    ) -> tuple[bool, str]:
        """
        Valida que las velas sean utilizables.

        No intenta decidir si el mercado está alcista o bajista.
        Solo determina si los datos son técnicamente razonables.
        """

        if not candles:
            return False, "No existen velas."

        if len(candles) < 50:
            return (
                False,
                f"Insuficientes velas: {len(candles)}.",
            )

        previous_timestamp: int | None = None

        for candle in candles:

            if candle.timestamp <= 0:
                return False, "Timestamp inválido."

            if candle.open <= 0:
                return False, "Precio open inválido."

            if candle.high <= 0:
                return False, "Precio high inválido."

            if candle.low <= 0:
                return False, "Precio low inválido."

            if candle.close <= 0:
                return False, "Precio close inválido."

            if candle.volume < 0:
                return False, "Volumen inválido."

            if candle.high < candle.low:
                return False, "High menor que low."

            if candle.high < candle.open:
                return False, "High menor que open."

            if candle.high < candle.close:
                return False, "High menor que close."

            if candle.low > candle.open:
                return False, "Low mayor que open."

            if candle.low > candle.close:
                return False, "Low mayor que close."

            if (
                previous_timestamp is not None
                and candle.timestamp <= previous_timestamp
            ):
                return (
                    False,
                    "Las velas no están ordenadas.",
                )

            previous_timestamp = candle.timestamp

        return True, "Datos válidos."

    # ============================================================
    # BINANCE
    # ============================================================

    def _load_binance_timeframe(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> TimeframeData:
        """
        Obtiene un timeframe desde Binance.

        Primero intenta utilizar caché fresco.
        Si no existe, consulta Binance.

        Nunca convierte datos de CoinGecko en velas técnicas.
        """

        if timeframe not in self.DEFAULT_TIMEFRAMES:
            raise ValueError(
                f"Timeframe no permitido: {timeframe}"
            )

        cache_key = self._cache_key(
            symbol,
            timeframe,
        )

        ttl = self.CACHE_TTL[timeframe]

        # --------------------------------------------------------
        # 1. Intentar caché
        # --------------------------------------------------------

        cached = self.cache.get(
            key=cache_key,
            max_age_seconds=ttl,
        )

        if cached is not None:

            try:
                candles_data = cached.get(
                    "candles",
                    [],
                )

                candles = [
                    self._candle_from_dict(item)
                    for item in candles_data
                    if isinstance(item, dict)
                ]

                valid, message = self._validate_candles(
                    candles,
                    timeframe,
                )

                if valid:

                    now = float(self.clock())

                    latest_timestamp = candles[-1].timestamp

                    quality = DataQuality(
                        source="binance-cache",
                        fetched_at=float(
                            cached.get(
                                "fetched_at",
                                now,
                            )
                        ),
                        latest_candle_timestamp=latest_timestamp,
                        is_complete=True,
                        is_closed=all(
                            candle.is_closed
                            for candle in candles[-2:]
                        ),
                        age_seconds=max(
                            0.0,
                            now
                            - float(
                                cached.get(
                                    "fetched_at",
                                    now,
                                )
                            ),
                        ),
                        message="Datos obtenidos desde caché.",
                    )

                    return TimeframeData(
                        timeframe=timeframe,
                        candles=candles,
                        quality=quality,
                    )

            except (
                KeyError,
                TypeError,
                ValueError,
            ):
                # Caché inválido: continuamos con Binance.
                pass

        # --------------------------------------------------------
        # 2. Consultar Binance
        # --------------------------------------------------------

        try:
            candles = self.binance.get_klines(
                symbol=symbol,
                interval=timeframe,
                limit=limit,
            )

        except BinanceProviderError as exc:

            # Intentamos recuperar datos stale solamente
            # para diagnóstico/control de continuidad.
            stale = self.cache.get(
                key=cache_key,
                max_age_seconds=24 * 60 * 60,
                allow_stale=True,
            )

            if stale is not None:

                try:
                    candles_data = stale.get(
                        "candles",
                        [],
                    )

                    stale_candles = [
                        self._candle_from_dict(item)
                        for item in candles_data
                        if isinstance(item, dict)
                    ]

                    valid, message = self._validate_candles(
                        stale_candles,
                        timeframe,
                    )

                    if valid:

                        now = float(self.clock())

                        fetched_at = float(
                            stale.get(
                                "fetched_at",
                                0,
                            )
                        )

                        age = max(
                            0.0,
                            now - fetched_at,
                        )

                        quality = DataQuality(
                            source="binance-cache-stale",
                            fetched_at=fetched_at,
                            latest_candle_timestamp=(
                                stale_candles[-1].timestamp
                            ),
                            is_complete=False,
                            is_closed=all(
                                candle.is_closed
                                for candle in stale_candles[-2:]
                            ),
                            age_seconds=age,
                            message=(
                                "Binance no respondió. "
                                "Datos antiguos disponibles "
                                "solo para diagnóstico; "
                                "no deben generar una nueva "
                                "señal operativa."
                            ),
                        )

                        return TimeframeData(
                            timeframe=timeframe,
                            candles=stale_candles,
                            quality=quality,
                        )

                except (
                    KeyError,
                    TypeError,
                    ValueError,
                ):
                    pass

            raise MarketDataError(
                f"No se pudieron obtener datos Binance "
                f"para {symbol} {timeframe}: {exc}"
            ) from exc

        # --------------------------------------------------------
        # 3. Validar datos recién obtenidos
        # --------------------------------------------------------

        valid, message = self._validate_candles(
            candles,
            timeframe,
        )

        if not valid:
            raise MarketDataError(
                f"Datos Binance inválidos para "
                f"{symbol} {timeframe}: {message}"
            )

        # --------------------------------------------------------
        # 4. Guardar caché
        # --------------------------------------------------------

        fetched_at = float(self.clock())

        payload = {
            "symbol": self._normalize_symbol(symbol),
            "timeframe": timeframe,
            "fetched_at": fetched_at,
            "candles": [
                self._candle_to_dict(candle)
                for candle in candles
            ],
        }

        try:
            self.cache.set(
                key=cache_key,
                payload=payload,
                source="binance",
                fetched_at=fetched_at,
            )

        except CacheError:
            # El fallo del caché no debe destruir una consulta
            # válida de mercado.
            pass

        # --------------------------------------------------------
        # 5. Calidad de datos
        # --------------------------------------------------------

        latest_timestamp = candles[-1].timestamp

        quality = DataQuality(
            source="binance",
            fetched_at=fetched_at,
            latest_candle_timestamp=latest_timestamp,
            is_complete=True,
            is_closed=all(
                candle.is_closed
                for candle in candles[-2:]
            ),
            age_seconds=0.0,
            message=message,
        )

        return TimeframeData(
            timeframe=timeframe,
            candles=candles,
            quality=quality,
        )

    # ============================================================
    # COINGECKO
    # ============================================================

    def _load_market_ticker(
        self,
        symbol: str,
    ) -> MarketTicker:
        """
        Obtiene información de mercado desde CoinGecko.

        CoinGecko se utiliza como inteligencia de mercado,
        no como fuente de las velas técnicas.
        """

        normalized = self._normalize_symbol(symbol)

        cache_key = (
            f"coingecko:"
            f"market:"
            f"{normalized}"
        )

        cached = self.cache.get(
            key=cache_key,
            max_age_seconds=self.MARKET_TTL,
        )

        if cached is not None:

            try:
                return MarketTicker(
                    symbol=normalized,
                    price=float(
                        cached["price"]
                    ),
                    market_cap=float(
                        cached.get(
                            "market_cap",
                            0,
                        )
                    ),
                    volume_24h=float(
                        cached.get(
                            "volume_24h",
                            0,
                        )
                    ),
                    change_1h=float(
                        cached.get(
                            "change_1h",
                            0,
                        )
                    ),
                    change_24h=float(
                        cached.get(
                            "change_24h",
                            0,
                        )
                    ),
                    change_7d=float(
                        cached.get(
                            "change_7d",
                            0,
                        )
                    ),
                )

            except (
                KeyError,
                TypeError,
                ValueError,
            ):
                pass

        try:
            data = self.coingecko.get_asset_market(
                normalized,
            )

        except CoinGeckoProviderError as exc:
            raise MarketDataError(
                f"No se pudo obtener información "
                f"de CoinGecko para {normalized}: {exc}"
            ) from exc

        if data is None:
            raise MarketDataError(
                f"CoinGecko no encontró información "
                f"para {normalized}."
            )

        try:
            ticker = MarketTicker(
                symbol=normalized,
                price=float(
                    data.get("price", 0)
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
        ) as exc:
            raise MarketDataError(
                f"Ticker CoinGecko inválido "
                f"para {normalized}."
            ) from exc

        if ticker.price <= 0:
            raise MarketDataError(
                f"Precio inválido de CoinGecko "
                f"para {normalized}."
            )

        payload = {
            "symbol": ticker.symbol,
            "price": ticker.price,
            "market_cap": ticker.market_cap,
            "volume_24h": ticker.volume_24h,
            "change_1h": ticker.change_1h,
            "change_24h": ticker.change_24h,
            "change_7d": ticker.change_7d,
        }

        try:
            self.cache.set(
                key=cache_key,
                payload=payload,
                source="coingecko",
                fetched_at=float(self.clock()),
            )

        except CacheError:
            pass

        return ticker

    # ============================================================
    # ACTIVO COMPLETO
    # ============================================================

    def get_asset(
        self,
        symbol: str,
        timeframes: tuple[str, ...] = DEFAULT_TIMEFRAMES,
        limit: int = DEFAULT_CANDLE_LIMIT,
    ) -> AssetMarketData:
        """
        Construye el conjunto completo de datos de un activo.

        Ejemplo:

            BTC
              ├── ticker CoinGecko
              ├── 15m Binance
              ├── 1h Binance
              ├── 4h Binance
              └── 1d Binance
        """

        normalized = self._normalize_symbol(symbol)

        if limit <= 0:
            raise ValueError(
                "limit debe ser mayor que cero."
            )

        if not timeframes:
            raise ValueError(
                "Debe existir al menos un timeframe."
            )

        invalid_timeframes = [
            timeframe
            for timeframe in timeframes
            if timeframe not in self.DEFAULT_TIMEFRAMES
        ]

        if invalid_timeframes:
            raise ValueError(
                "Timeframes no soportados: "
                + ", ".join(invalid_timeframes)
            )

        ticker = self._load_market_ticker(
            normalized,
        )

        timeframe_data: dict[str, TimeframeData] = {}

        for timeframe in timeframes:

            data = self._load_binance_timeframe(
                symbol=normalized,
                timeframe=timeframe,
                limit=limit,
            )

            timeframe_data[timeframe] = data

        return AssetMarketData(
            symbol=normalized,
            ticker=ticker,
            timeframes=timeframe_data,
        )

    # ============================================================
    # MERCADO GLOBAL
    # ============================================================

    def get_global_market(
        self,
    ) -> dict[str, Any]:
        """
        Obtiene el estado global del mercado desde CoinGecko.

        Posteriormente estos datos alimentarán el cálculo
        del régimen de mercado.
        """

        cache_key = "coingecko:global"

        cached = self.cache.get(
            key=cache_key,
            max_age_seconds=self.GLOBAL_TTL,
        )

        if cached is not None:
            return cached

        try:
            data = self.coingecko.get_global_market()

        except CoinGeckoProviderError as exc:
            raise MarketDataError(
                f"No se pudo obtener el mercado global: {exc}"
            ) from exc

        if not isinstance(data, dict):
            raise MarketDataError(
                "Datos globales inválidos."
            )

        fetched_at = float(self.clock())

        payload = {
            **data,
            "fetched_at": fetched_at,
        }

        try:
            self.cache.set(
                key=cache_key,
                payload=payload,
                source="coingecko",
                fetched_at=fetched_at,
            )

        except CacheError:
            pass

        return payload

    # ============================================================
    # VARIOS ACTIVOS
    # ============================================================

    def get_assets(
        self,
        symbols: list[str] | tuple[str, ...],
        timeframes: tuple[str, ...] = DEFAULT_TIMEFRAMES,
        limit: int = DEFAULT_CANDLE_LIMIT,
    ) -> dict[str, AssetMarketData]:
        """
        Obtiene varios activos.

        Si un activo falla, no se inventan datos.
        El error se propaga para que la capa superior
        pueda decidir cómo manejarlo.
        """

        if not symbols:
            raise ValueError(
                "Debe proporcionarse al menos un símbolo."
            )

        result: dict[str, AssetMarketData] = {}

        for symbol in symbols:

            normalized = self._normalize_symbol(
                symbol
            )

            result[normalized] = self.get_asset(
                symbol=normalized,
                timeframes=timeframes,
                limit=limit,
            )

        return result

    # ============================================================
    # RESUMEN DE CALIDAD
    # ============================================================

    @staticmethod
    def data_quality_summary(
        asset: AssetMarketData,
    ) -> dict[str, Any]:
        """
        Devuelve un resumen sencillo de la calidad de datos
        de un activo.

        Será útil para el sistema de alertas y para debugging.
        """

        summary: dict[str, Any] = {
            "symbol": asset.symbol,
            "price": asset.price,
            "timeframes": {},
        }

        for timeframe, data in asset.timeframes.items():

            quality = data.quality

            if quality is None:
                summary["timeframes"][timeframe] = {
                    "available": False,
                    "message": "Sin información de calidad.",
                }
                continue

            summary["timeframes"][timeframe] = {
                "available": bool(data.candles),
                "source": quality.source,
                "fetched_at": quality.fetched_at,
                "latest_candle_timestamp": (
                    quality.latest_candle_timestamp
                ),
                "is_complete": quality.is_complete,
                "is_closed": quality.is_closed,
                "age_seconds": quality.age_seconds,
                "message": quality.message,
                "candle_count": len(data.candles),
            }

        return summary