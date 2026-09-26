from __future__ import annotations

import math
import time
from typing import Any

import requests

from radar.models import Candle


class BinanceProviderError(Exception):
    """Error base del proveedor Binance."""


class BinanceProvider:
    """
    Proveedor profesional de datos OHLCV para Radar
    El Laboratorio.

    Fuente:
        Binance Public Data API

    Endpoint:
        https://data-api.binance.vision

    Timeframes utilizados por Radar:

        15m -> entrada / timing
        1h  -> momentum
        4h  -> estructura
        1d  -> tendencia

    Este proveedor NO realiza operaciones.
    Solamente obtiene y normaliza datos de mercado.
    """

    BASE_URL = "https://data-api.binance.vision"
    KLINES_ENDPOINT = "/api/v3/klines"

    DEFAULT_TIMEOUT = 20
    DEFAULT_RETRIES = 3

    MAX_LIMIT = 1000

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

    RETRYABLE_STATUS_CODES = {
        418,
        429,
        500,
        502,
        503,
        504,
    }

    # ============================================================
    # CONSTRUCTOR
    # ============================================================

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

        self.session = (
            session
            if session is not None
            else requests.Session()
        )

        self.timeout = int(timeout)
        self.max_retries = int(max_retries)

        self.session.headers.update(
            {
                "User-Agent": (
                    "Radar-El-Laboratorio/5.0"
                ),
                "Accept": "application/json",
            }
        )

    # ============================================================
    # NORMALIZACIÓN DE SYMBOL
    # ============================================================

    @staticmethod
    def normalize_symbol(
        symbol: str,
    ) -> str:

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
    # VALIDACIÓN DE INTERVALO
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
                "Intervalo no soportado: "
                f"{interval}"
            )

        return interval

    # ============================================================
    # VALIDACIÓN LIMIT
    # ============================================================

    @classmethod
    def validate_limit(
        cls,
        limit: int,
    ) -> int:

        if isinstance(limit, bool):
            raise ValueError(
                "limit debe ser un entero."
            )

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
                f"limit no puede superar "
                f"{cls.MAX_LIMIT}."
            )

        return limit

    # ============================================================
    # VALIDACIÓN NUMÉRICA
    # ============================================================

    @staticmethod
    def _finite(
        value: float,
        name: str,
    ) -> float:

        if not math.isfinite(value):
            raise BinanceProviderError(
                f"{name} contiene un valor "
                "no finito."
            )

        return value

    # ============================================================
    # HTTP
    # ============================================================

    def _request(
        self,
        endpoint: str,
        params: dict[str, Any],
    ) -> Any:

        url = (
            f"{self.BASE_URL}"
            f"{endpoint}"
        )

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
                # RATE LIMIT / ERRORES TEMPORALES
                # ------------------------------------------------

                if status in self.RETRYABLE_STATUS_CODES:

                    if (
                        attempt
                        >= self.max_retries
                    ):

                        raise BinanceProviderError(
                            "Binance respondió HTTP "
                            f"{status} después de "
                            f"{self.max_retries} "
                            "intentos."
                        )

                    retry_after = (
                        response.headers.get(
                            "Retry-After"
                        )
                    )

                    delay: float

                    if retry_after:

                        try:

                            delay = float(
                                retry_after
                            )

                        except (
                            TypeError,
                            ValueError,
                        ):

                            delay = (
                                2
                                ** (
                                    attempt - 1
                                )
                            )

                    else:

                        delay = (
                            2
                            ** (
                                attempt - 1
                            )
                        )

                    delay = min(
                        max(delay, 0.5),
                        8.0,
                    )

                    print(
                        "Binance temporal error "
                        f"HTTP {status}. "
                        f"Reintento "
                        f"{attempt}/"
                        f"{self.max_retries} "
                        f"en {delay:.1f}s."
                    )

                    time.sleep(
                        delay
                    )

                    continue

                # ------------------------------------------------
                # ERRORES HTTP DEFINITIVOS
                # ------------------------------------------------

                if status >= 400:

                    body = (
                        response.text[:500]
                        .strip()
                    )

                    raise BinanceProviderError(
                        "Binance respondió HTTP "
                        f"{status}."
                        + (
                            f" Detalle: {body}"
                            if body
                            else ""
                        )
                    )

                # ------------------------------------------------
                # JSON
                # ------------------------------------------------

                try:

                    return response.json()

                except ValueError as exc:

                    raise BinanceProviderError(
                        "Binance devolvió "
                        "JSON inválido."
                    ) from exc

            except (
                requests.Timeout,
                requests.ConnectionError,
            ) as exc:

                last_error = exc

                if (
                    attempt
                    < self.max_retries
                ):

                    delay = min(
                        2
                        ** (
                            attempt - 1
                        ),
                        8.0,
                    )

                    print(
                        "Error de conexión con "
                        "Binance. "
                        f"Reintento "
                        f"{attempt}/"
                        f"{self.max_retries} "
                        f"en {delay}s."
                    )

                    time.sleep(
                        delay
                    )

                    continue

                break

            except requests.RequestException as exc:

                last_error = exc
                break

            except BinanceProviderError:

                raise

        if last_error is not None:

            raise BinanceProviderError(
                "No se pudo consultar Binance: "
                f"{last_error}"
            ) from last_error

        raise BinanceProviderError(
            "No se pudo consultar Binance."
        )

    # ============================================================
    # PARSEAR VELA
    # ============================================================

    @classmethod
    def _parse_candle(
        cls,
        raw: list[Any],
        now_ms: int,
    ) -> Candle:

        if not isinstance(
            raw,
            list,
        ):

            raise BinanceProviderError(
                "La vela Binance no es "
                "una lista."
            )

        # Binance devuelve 12 campos.
        # Radar necesita como mínimo:
        #
        # 0 open time
        # 1 open
        # 2 high
        # 3 low
        # 4 close
        # 5 volume
        # 6 close time

        if len(raw) < 7:

            raise BinanceProviderError(
                "La vela Binance no contiene "
                "los campos necesarios."
            )

        try:

            timestamp = int(
                raw[0]
            )

            open_price = float(
                raw[1]
            )

            high_price = float(
                raw[2]
            )

            low_price = float(
                raw[3]
            )

            close_price = float(
                raw[4]
            )

            volume = float(
                raw[5]
            )

            close_time = int(
                raw[6]
            )

        except (
            TypeError,
            ValueError,
        ) as exc:

            raise BinanceProviderError(
                "No se pudo convertir la "
                "vela Binance a valores "
                "numéricos."
            ) from exc

        # --------------------------------------------------------
        # VALIDACIÓN FINITA
        # --------------------------------------------------------

        timestamp = int(timestamp)
        close_time = int(close_time)

        open_price = cls._finite(
            open_price,
            "open",
        )

        high_price = cls._finite(
            high_price,
            "high",
        )

        low_price = cls._finite(
            low_price,
            "low",
        )

        close_price = cls._finite(
            close_price,
            "close",
        )

        volume = cls._finite(
            volume,
            "volume",
        )

        # --------------------------------------------------------
        # VALIDACIÓN DE TIMESTAMPS
        # --------------------------------------------------------

        if timestamp < 0:

            raise BinanceProviderError(
                "Timestamp inválido."
            )

        if close_time < timestamp:

            raise BinanceProviderError(
                "Close time inválido."
            )

        # --------------------------------------------------------
        # VALIDACIÓN OHLC
        # --------------------------------------------------------

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

        if high_price < max(
            open_price,
            close_price,
        ):

            raise BinanceProviderError(
                "High no contiene "
                "Open/Close."
            )

        if low_price > min(
            open_price,
            close_price,
        ):

            raise BinanceProviderError(
                "Low no contiene "
                "Open/Close."
            )

        if high_price < low_price:

            raise BinanceProviderError(
                "High no puede ser menor "
                "que Low."
            )

        # --------------------------------------------------------
        # ESTADO DE CIERRE
        # --------------------------------------------------------

        is_closed = (
            close_time <= now_ms
        )

        return Candle(
            timestamp=timestamp,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
            is_closed=is_closed,
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

        if not isinstance(
            raw_data,
            list,
        ):

            raise BinanceProviderError(
                "La respuesta Binance no es "
                "una lista de velas."
            )

        now_ms = int(
            time.time() * 1000
        )

        candles: list[Candle] = []

        for index, raw in enumerate(
            raw_data
        ):

            try:

                candle = (
                    self._parse_candle(
                        raw,
                        now_ms,
                    )
                )

            except BinanceProviderError as exc:

                raise BinanceProviderError(
                    f"Vela inválida en "
                    f"posición {index}: "
                    f"{exc}"
                ) from exc

            candles.append(
                candle
            )

        # --------------------------------------------------------
        # ORDEN CRONOLÓGICO
        # --------------------------------------------------------

        candles.sort(
            key=lambda candle:
            candle.timestamp
        )

        # --------------------------------------------------------
        # VALIDAR DUPLICADOS
        # --------------------------------------------------------

        previous_timestamp: int | None = None

        for candle in candles:

            if (
                previous_timestamp
                is not None
                and candle.timestamp
                <= previous_timestamp
            ):

                raise BinanceProviderError(
                    "Binance devolvió "
                    "timestamps duplicados "
                    "o fuera de orden."
                )

            previous_timestamp = (
                candle.timestamp
            )

        return candles

    # ============================================================
    # OBTENER MÚLTIPLES TIMEFRAMES
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
                "Debe existir al menos "
                "un timeframe."
            )

        # Eliminar duplicados conservando
        # el orden solicitado.

        normalized_intervals: list[str] = []

        for interval in intervals:

            interval = (
                self.validate_interval(
                    interval
                )
            )

            if (
                interval
                not in normalized_intervals
            ):

                normalized_intervals.append(
                    interval
                )

        result: dict[
            str,
            list[Candle],
        ] = {}

        for interval in (
            normalized_intervals
        ):

            result[interval] = (
                self.get_klines(
                    symbol=symbol,
                    interval=interval,
                    limit=limit,
                )
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
                f"No hay una vela cerrada "
                f"para {symbol} {interval}."
            )

        return closed[-1]

    # ============================================================
    # SOLO VELAS CERRADAS
    # ============================================================

    def get_closed_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 200,
    ) -> list[Candle]:

        candles = self.get_klines(
            symbol=symbol,
            interval=interval,
            limit=limit,
        )

        return [
            candle
            for candle in candles
            if candle.is_closed
        ]

    # ============================================================
    # ESTADO DEL PROVEEDOR
    # ============================================================

    def ping(self) -> bool:

        endpoint = "/api/v3/ping"

        try:

            result = self._request(
                endpoint,
                {},
            )

            return isinstance(
                result,
                dict,
            )

        except BinanceProviderError:

            return False