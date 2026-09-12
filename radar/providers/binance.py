from __future__ import annotations

import math
import time
from typing import Any

import requests

from radar.models import Candle


class BinanceProviderError(Exception):
    """Error del proveedor Binance."""


class BinanceProvider:
    """
    Proveedor de datos técnicos Binance para Radar El Laboratorio.

    Binance Data API:
        https://data-api.binance.vision

    Timeframes principales:
        15m -> entrada
        1h  -> momentum
        4h  -> estructura
        1d  -> tendencia
    """

    BASE_URL = "https://data-api.binance.vision"
    KLINES_ENDPOINT = "/api/v3/klines"

    DEFAULT_TIMEOUT = 20
    MAX_LIMIT = 1000
    DEFAULT_RETRIES = 3

    SUPPORTED_INTERVALS = {
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
        session: requests.Session | None = None,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_RETRIES,
    ) -> None:

        if timeout <= 0:
            raise ValueError(
                "timeout debe ser mayor que cero."
            )

        if max_retries < 1:
            raise ValueError(
                "max_retries debe ser al menos 1."
            )

        self.session = session or requests.Session()
        self.timeout = timeout
        self.max_retries = max_retries

        self.session.headers.update(
            {
                "User-Agent": (
                    "Radar-El-Laboratorio/5.0"
                ),
                "Accept": "application/json",
            }
        )

    # ============================================================
    # NORMALIZACIÓN
    # ============================================================

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        if not isinstance(symbol, str):
            raise ValueError(
                "symbol debe ser un texto."
            )

        symbol = symbol.strip().upper()

        if not symbol:
            raise ValueError(
                "symbol no puede estar vacío."
            )

        if symbol.endswith("USDT"):
            return symbol

        return f"{symbol}USDT"

    # ============================================================
    # VALIDACIONES
    # ============================================================

    @classmethod
    def validate_interval(
        cls,
        interval: str,
    ) -> str:

        if not isinstance(interval, str):
            raise ValueError(
                "interval debe ser un texto."
            )

        interval = interval.strip()

        if interval not in cls.SUPPORTED_INTERVALS:
            raise ValueError(
                f"Intervalo no soportado: {interval}"
            )

        return interval

    @classmethod
    def validate_limit(
        cls,
        limit: int,
    ) -> int:

        if not isinstance(limit, int):
            raise ValueError(
                "limit debe ser un entero."
            )

        if limit < 1:
            raise ValueError(
                "limit debe ser mayor que cero."
            )

        if limit > cls.MAX_LIMIT:
            raise ValueError(
                f"limit no puede superar {cls.MAX_LIMIT}."
            )

        return limit

    # ============================================================
    # HTTP
    # ============================================================

    def _request(
        self,
        endpoint: str,
        params: dict[str, Any],
    ) -> Any:

        url = f"{self.BASE_URL}{endpoint}"

        last_error: Exception | None = None

        for attempt in range(
            1,
            self.max_retries + 1,
        ):

            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.timeout,
                )

                status = response.status_code

                # ------------------------------------------------
                # RATE LIMIT
                # ------------------------------------------------

                if status in {418, 429}:

                    if attempt >= self.max_retries:
                        raise BinanceProviderError(
                            f"Binance respondió HTTP "
                            f"{status} después de "
                            f"{self.max_retries} intentos."
                        )

                    retry_after = response.headers.get(
                        "Retry-After"
                    )

                    try:
                        delay = (
                            float(retry_after)
                            if retry_after
                            else 2 ** (attempt - 1)
                        )
                    except ValueError:
                        delay = 2 ** (attempt - 1)

                    time.sleep(
                        min(delay, 8.0)
                    )

                    continue

                # ------------------------------------------------
                # ERRORES TEMPORALES
                # ------------------------------------------------

                if status in {
                    500,
                    502,
                    503,
                    504,
                }:

                    if attempt < self.max_retries:
                        time.sleep(
                            min(
                                2 ** (attempt - 1),
                                8.0,
                            )
                        )
                        continue

                    raise BinanceProviderError(
                        f"Binance respondió HTTP "
                        f"{status} después de "
                        f"{self.max_retries} intentos."
                    )

                # ------------------------------------------------
                # OTROS ERRORES HTTP
                # ------------------------------------------------

                response.raise_for_status()

                # ------------------------------------------------
                # JSON
                # ------------------------------------------------

                try:
                    return response.json()

                except ValueError as exc:
                    raise BinanceProviderError(
                        "Binance devolvió JSON inválido."
                    ) from exc

            except (
                requests.Timeout,
                requests.ConnectionError,
            ) as exc:

                last_error = exc

                if attempt < self.max_retries:
                    time.sleep(
                        min(
                            2 ** (attempt - 1),
                            8.0,
                        )
                    )
                    continue

                break

            except requests.RequestException as exc:

                last_error = exc
                break

        if last_error is not None:
            raise BinanceProviderError(
                f"No se pudo consultar Binance: "
                f"{last_error}"
            ) from last_error

        raise BinanceProviderError(
            "No se pudo consultar Binance."
        )

    # ============================================================
    # PARSEO DE VELAS
    # ============================================================

    @staticmethod
    def _parse_candle(
        raw: list[Any],
        now_ms: int,
    ) -> Candle:

        if not isinstance(raw, list):
            raise BinanceProviderError(
                "La vela Binance no es una lista."
            )

        if len(raw) < 7:
            raise BinanceProviderError(
                "La vela Binance no contiene "
                "los campos necesarios."
            )

        try:
            timestamp = int(raw[0])

            open_price = float(raw[1])
            high_price = float(raw[2])
            low_price = float(raw[3])
            close_price = float(raw[4])
            volume = float(raw[5])

            close_time = int(raw[6])

        except (
            TypeError,
            ValueError,
        ) as exc:

            raise BinanceProviderError(
                "No se pudo convertir la vela "
                "Binance a valores numéricos."
            ) from exc

        # --------------------------------------------------------
        # VALIDACIÓN NUMÉRICA
        # --------------------------------------------------------

        values = (
            open_price,
            high_price,
            low_price,
            close_price,
            volume,
        )

        if not all(
            math.isfinite(value)
            for value in values
        ):
            raise BinanceProviderError(
                "La vela contiene valores no finitos."
            )

        if open_price <= 0:
            raise BinanceProviderError(
                "Open inválido."
            )

        if high_price <= 0:
            raise BinanceProviderError(
                "High inválido."
            )

        if low_price <= 0:
            raise BinanceProviderError(
                "Low inválido."
            )

        if close_price <= 0:
            raise BinanceProviderError(
                "Close inválido."
            )

        if volume < 0:
            raise BinanceProviderError(
                "Volume inválido."
            )

        # --------------------------------------------------------
        # VALIDACIÓN OHLC
        # --------------------------------------------------------

        if high_price < max(
            open_price,
            close_price,
        ):
            raise BinanceProviderError(
                "High no contiene Open/Close."
            )

        if low_price > min(
            open_price,
            close_price,
        ):
            raise BinanceProviderError(
                "Low no contiene Open/Close."
            )

        if high_price < low_price:
            raise BinanceProviderError(
                "High no puede ser menor que Low."
            )

        if close_time < timestamp:
            raise BinanceProviderError(
                "Close time inválido."
            )

        return Candle(
            timestamp=timestamp,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
            is_closed=(
                close_time <= now_ms
            ),
        )

    # ============================================================
    # OBTENER KLINES
    # ============================================================

    def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 200,
    ) -> list[Candle]:

        symbol = self.normalize_symbol(
            symbol
        )

        interval = self.validate_interval(
            interval
        )

        limit = self.validate_limit(
            limit
        )

        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        }

        raw_data = self._request(
            self.KLINES_ENDPOINT,
            params,
        )

        if not isinstance(raw_data, list):
            raise BinanceProviderError(
                "La respuesta Binance no es "
                "una lista de velas."
            )

        now_ms = int(
            time.time() * 1000
        )

        candles: list[Candle] = []

        for raw in raw_data:

            candle = self._parse_candle(
                raw,
                now_ms,
            )

            candles.append(candle)

        # --------------------------------------------------------
        # ORDEN CRONOLÓGICO
        # --------------------------------------------------------

        candles.sort(
            key=lambda candle: candle.timestamp
        )

        # --------------------------------------------------------
        # TIMESTAMPS DUPLICADOS
        # --------------------------------------------------------

        timestamps = [
            candle.timestamp
            for candle in candles
        ]

        if len(timestamps) != len(
            set(timestamps)
        ):
            raise BinanceProviderError(
                "Binance devolvió timestamps duplicados."
            )

        return candles

    # ============================================================
    # MÚLTIPLES TIMEFRAMES
    # ============================================================

    def get_multi_timeframe(
        self,
        symbol: str,
        intervals: tuple[str, ...] = (
            "15m",
            "1h",
            "4h",
            "1d",
        ),
        limit: int = 200,
    ) -> dict[str, list[Candle]]:

        if not intervals:
            raise ValueError(
                "Debe existir al menos un timeframe."
            )

        result: dict[str, list[Candle]] = {}

        for interval in intervals:

            interval = self.validate_interval(
                interval
            )

            result[interval] = self.get_klines(
                symbol=symbol,
                interval=interval,
                limit=limit,
            )

        return result

    # ============================================================
    # ÚLTIMA VELA
    # ============================================================

    def get_last_candle(
        self,
        symbol: str,
        interval: str,
    ) -> Candle:

        candles = self.get_klines(
            symbol=symbol,
            interval=interval,
            limit=2,
        )

        if not candles:
            raise BinanceProviderError(
                f"No hay velas para "
                f"{symbol} {interval}."
            )

        return candles[-1]

    # ============================================================
    # ÚLTIMA VELA CERRADA
    # ============================================================

    def get_last_closed_candle(
        self,
        symbol: str,
        interval: str,
    ) -> Candle:

        candles = self.get_klines(
            symbol=symbol,
            interval=interval,
            limit=3,
        )

        closed = [
            candle
            for candle in candles
            if candle.is_closed
        ]

        if not closed:
            raise BinanceProviderError(
                f"No hay una vela cerrada para "
                f"{symbol} {interval}."
            )

        return closed[-1]