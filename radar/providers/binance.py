from __future__ import annotations

import time
from typing import Any

import requests

from radar.models import Candle


class BinanceProviderError(Exception):
    """Error base del proveedor Binance."""


class BinanceProvider:
    """
    Proveedor de datos técnicos de Binance.

    Utiliza exclusivamente el endpoint público de datos de Binance
    para evitar depender de los endpoints tradicionales que pueden
    devolver HTTP 451 en determinados entornos/regiones.

    Fuente:
        https://data-api.binance.vision

    Endpoint:
        /api/v3/klines
    """

    BASE_URL = "https://data-api.binance.vision"

    KLINES_ENDPOINT = "/api/v3/klines"

    DEFAULT_TIMEOUT = 20

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

    def __init__(
        self,
        session: requests.Session | None = None,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = 3,
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
                    "Radar-El-Laboratorio/5.0 "
                    "(market-data-client)"
                ),
                "Accept": "application/json",
            }
        )

    # ============================================================
    # NORMALIZACIÓN
    # ============================================================

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        """
        Convierte símbolos comunes al formato Spot USDT.

        Ejemplos:
            BTC      -> BTCUSDT
            BTCUSDT  -> BTCUSDT
            ETH      -> ETHUSDT
            ethusdt  -> ETHUSDT
        """

        if not isinstance(symbol, str):
            raise ValueError(
                "symbol debe ser un texto."
            )

        normalized = symbol.strip().upper()

        if not normalized:
            raise ValueError(
                "symbol no puede estar vacío."
            )

        if normalized.endswith("USDT"):
            return normalized

        return f"{normalized}USDT"

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
                f"Intervalo Binance no soportado: {interval}. "
                f"Permitidos: "
                f"{', '.join(sorted(cls.SUPPORTED_INTERVALS))}"
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
        """
        Ejecuta una petición HTTP contra Binance.

        Reintenta errores temporales:
        - HTTP 429
        - HTTP 418
        - HTTP 500
        - HTTP 502
        - HTTP 503
        - HTTP 504
        - errores de conexión/timeout

        No intenta ocultar errores 4xx permanentes.
        """

        url = f"{self.BASE_URL}{endpoint}"

        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):

            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.timeout,
                )

                status = response.status_code

                # --------------------------------------------
                # RATE LIMIT
                # --------------------------------------------

                if status in {418, 429}:

                    retry_after = response.headers.get(
                        "Retry-After"
                    )

                    if retry_after:
                        try:
                            delay = float(retry_after)
                        except ValueError:
                            delay = 2.0
                    else:
                        delay = min(
                            2 ** (attempt - 1),
                            8.0,
                        )

                    if attempt < self.max_retries:
                        time.sleep(delay)
                        continue

                    raise BinanceProviderError(
                        "Binance respondió con "
                        f"HTTP {status} después de "
                        f"{self.max_retries} intentos."
                    )

                # --------------------------------------------
                # ERRORES TEMPORALES DEL SERVIDOR
                # --------------------------------------------

                if status in {
                    500,
                    502,
                    503,
                    504,
                }:

                    if attempt < self.max_retries:
                        delay = min(
                            2 ** (attempt - 1),
                            8.0,
                        )

                        time.sleep(delay)
                        continue

                    raise BinanceProviderError(
                        "Binance respondió con "
                        f"HTTP {status} después de "
                        f"{self.max_retries} intentos."
                    )

                # --------------------------------------------
                # OTROS ERRORES HTTP
                # --------------------------------------------

                response.raise_for_status()

                # --------------------------------------------
                # JSON
                # --------------------------------------------

                try:
                    return response.json()
                except ValueError as exc:
                    raise BinanceProviderError(
                        "Binance devolvió una respuesta "
                        "que no es JSON válido."
                    ) from exc

            except (
                requests.Timeout,
                requests.ConnectionError,
            ) as exc:

                last_error = exc

                if attempt < self.max_retries:
                    delay = min(
                        2 ** (attempt - 1),
                        8.0,
                    )

                    time.sleep(delay)
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
            "No se pudo consultar Binance por "
            "un error desconocido."
        )

    # ============================================================
    # PARSEO DE VELAS
    # ============================================================

    @staticmethod
    def _parse_candle(
        raw: list[Any],
        now_ms: int,
    ) -> Candle:
        """
        Convierte una fila Binance Kline a Candle.

        Estructura relevante Binance:

        0  open time
        1  open
        2  high
        3  low
        4  close
        5  volume
        6  close time
        """

        if not isinstance(raw, list):
            raise BinanceProviderError(
                "Una vela Binance no tiene formato de lista."
            )

        if len(raw) < 7:
            raise BinanceProviderError(
                "Una vela Binance no contiene "
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
                "No se pudo convertir una vela "
                "Binance a valores numéricos."
            ) from exc

        # --------------------------------------------------------
        # VALIDACIÓN OHLCV
        # --------------------------------------------------------

        values = (
            open_price,
            high_price,
            low_price,
            close_price,
            volume,
        )

        for value in values:
            if value != value:
                raise BinanceProvider