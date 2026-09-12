
from __future__ import annotations

import time
from typing import Any

import requests

from radar.models import Candle


class BinanceProviderError(Exception):
    """Error general del proveedor Binance."""


class BinanceProvider:
    """
    Proveedor de datos técnicos de Binance.

    Binance se utiliza como fuente principal para:
        - OHLCV
        - 15m
        - 1h
        - 4h
        - 1d

    Este proveedor NO calcula indicadores ni genera señales.
    Su única responsabilidad es obtener y normalizar datos.
    """

    BASE_URLS = (
        "https://api.binance.com",
        "https://api-gcp.binance.com",
        "https://api1.binance.com",
        "https://api2.binance.com",
    )

    KLINES_ENDPOINT = "/api/v3/klines"

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

    DEFAULT_TIMEOUT = 20

    MAX_LIMIT = 1000

    USER_AGENT = (
        "El-Laboratorio-Radar/5.0"
    )

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        session: requests.Session | None = None,
    ) -> None:

        if timeout <= 0:
            raise ValueError(
                "timeout debe ser mayor que cero."
            )

        self.timeout = timeout

        self.session = (
            session
            if session is not None
            else requests.Session()
        )

        self.session.headers.update(
            {
                "User-Agent": self.USER_AGENT,
                "Accept": "application/json",
            }
        )

    # ============================================================
    # NORMALIZACIÓN
    # ============================================================

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        """
        Convierte un símbolo a formato Binance USDT.

        Ejemplos:

            BTC
            BTCUSDT
            btc
            btcusdt

        Todos terminan como:

            BTCUSDT
        """

        if not symbol or not symbol.strip():
            raise ValueError(
                "El símbolo no puede estar vacío."
            )

        normalized = symbol.strip().upper()

        if not normalized.endswith("USDT"):
            normalized += "USDT"

        return normalized

    # ============================================================
    # REQUEST
    # ============================================================

    def _request(
        self,
        endpoint: str,
        params: dict[str, Any],
        attempts: int = 3,
    ) -> Any:

        if attempts <= 0:
            raise ValueError(
                "attempts debe ser mayor que cero."
            )

        last_error: Exception | None = None

        for attempt in range(attempts):

            for base_url in self.BASE_URLS:

                url = f"{base_url}{endpoint}"

                try:

                    response = self.session.get(
                        url,
                        params=params,
                        timeout=self.timeout,
                    )

                    # ------------------------------------------------
                    # Rate limit
                    # ------------------------------------------------

                    if response.status_code == 429:

                        retry_after = response.headers.get(
                            "Retry-After"
                        )

                        try:
                            delay = float(
                                retry_after
                            )
                        except (
                            TypeError,
                            ValueError,
                        ):
                            delay = min(
                                2 ** attempt,
                                10,
                            )

                        time.sleep(
                            max(
                                1,
                                delay,
                            )
                        )

                        continue

                    # ------------------------------------------------
                    # IP temporalmente bloqueada
                    # ------------------------------------------------

                    if response.status_code == 418:

                        delay = min(
                            5 * (attempt + 1),
                            30,
                        )

                        time.sleep(delay)

                        continue

                    # ------------------------------------------------
                    # Errores temporales
                    # ------------------------------------------------

                    if response.status_code in {
                        500,
                        502,
                        503,
                        504,
                    }:

                        time.sleep(
                            min(
                                2 ** attempt,
                                10,
                            )
                        )

                        continue

                    # ------------------------------------------------
                    # Otros errores HTTP
                    # ------------------------------------------------

                    response.raise_for_status()

                    return response.json()

                except requests.RequestException as exc:

                    last_error = exc

                    time.sleep(
                        min(
                            2 ** attempt,
                            10,
                        )
                    )

                    continue

        if last_error is not None:

            raise BinanceProviderError(
                f"No se pudo consultar Binance: "
                f"{last_error}"
            ) from last_error

        raise BinanceProviderError(
            "Binance no respondió con datos válidos."
        )

    # ============================================================
    # KLINES
    # ============================================================

    def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
    ) -> list[Candle]:
        """
        Obtiene velas OHLCV de Binance.

        Devuelve objetos Candle normalizados.
        """

        normalized_symbol = (
            self.normalize_symbol(symbol)
        )

        if interval not in self.SUPPORTED_INTERVALS:
            raise ValueError(
                f"Intervalo no soportado: {interval}"
            )

        if limit <= 0:
            raise ValueError(
                "limit debe ser mayor que cero."
            )

        limit = min(
            limit,
            self.MAX_LIMIT,
        )

        params = {
            "symbol": normalized_symbol,
            "interval": interval,
            "limit": limit,
        }

        raw_data = self._request(
            endpoint=self.KLINES_ENDPOINT,
            params=params,
        )

        if not isinstance(
            raw_data,
            list,
        ):
            raise BinanceProviderError(
                "Respuesta de Binance inválida."
            )

        candles: list[Candle] = []

        now_ms = int(
            time.time() * 1000
        )

        for row in raw_data:

            if not isinstance(
                row,
                list,
            ):
                continue

            if len(row) < 7:
                continue

            try:

                open_time = int(row[0])
                open_price = float(row[1])
                high_price = float(row[2])
                low_price = float(row[3])
                close_price = float(row[4])
                volume = float(row[5])
                close_time = int(row[6])

            except (
                TypeError,
                ValueError,
            ):
                continue

            # --------------------------------------------------------
            # Validación básica
            # --------------------------------------------------------

            if open_time <= 0:
                continue

            if close_time <= 0:
                continue

            if (
                open_price <= 0
                or high_price <= 0
                or low_price <= 0
                or close_price <= 0
            ):
                continue

            if volume < 0:
                continue

            if high_price < low_price:
                continue

            if high_price < open_price:
                continue

            if high_price < close_price:
                continue

            if low_price > open_price:
                continue

            if low_price > close_price:
                continue

            # --------------------------------------------------------
            # Determinar si la vela está cerrada
            # --------------------------------------------------------

            is_closed = (
                close_time <= now_ms
            )

            candles.append(
                Candle(
                    timestamp=open_time,
                    open=open_price,
                    high=high_price,
                    low=low_price,
                    close=close_price,
                    volume=volume,
                    is_closed=is_closed,
                )
            )

        if not candles:
            raise BinanceProviderError(
                f"Binance no devolvió velas válidas "
                f"para {normalized_symbol} "
                f"{interval}."
            )

        # ------------------------------------------------------------
        # Orden cronológico
        # ------------------------------------------------------------

        candles.sort(
            key=lambda candle: candle.timestamp
        )

        return candles

    # ============================================================
    # MULTI-TIMEFRAME
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
        limit: int = 500,
    ) -> dict[str, list[Candle]]:
        """
        Obtiene múltiples timeframes de un activo.

        Ejemplo:

            {
                "15m": [...],
                "1h": [...],
                "4h": [...],
                "1d": [...]
            }
        """

        result: dict[
            str,
            list[Candle],
        ] = {}

        for interval in intervals:

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
                "No existe una última vela válida."
            )

        return candles[-1]