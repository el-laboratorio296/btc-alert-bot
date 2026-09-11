from __future__ import annotations

import time
from typing import Any

import requests


class CoinGeckoProviderError(Exception):
    """Error general del proveedor CoinGecko."""


class CoinGeckoProvider:
    """
    Proveedor de inteligencia de mercado de CoinGecko.

    Se utiliza para:
    - Precio de mercado
    - Market Cap
    - Volumen 24h
    - Cambios 1h / 24h / 7d
    - Universo de mercado
    - Datos globales del mercado

    No calcula indicadores técnicos ni genera señales.
    """

    FREE_BASE_URL = "https://api.coingecko.com/api/v3"

    PRO_BASE_URL = "https://pro-api.coingecko.com/api/v3"

    MARKETS_ENDPOINT = "/coins/markets"

    GLOBAL_ENDPOINT = "/global"

    DEFAULT_TIMEOUT = 20

    def __init__(
        self,
        api_key: str | None = None,
        timeout: int = DEFAULT_TIMEOUT,
        session: requests.Session | None = None,
    ) -> None:

        if timeout <= 0:
            raise ValueError(
                "timeout debe ser mayor que cero."
            )

        self.api_key = api_key
        self.timeout = timeout

        self.session = (
            session
            if session is not None
            else requests.Session()
        )

        self.session.headers.update(
            {
                "User-Agent": (
                    "El-Laboratorio-Radar/5.0"
                ),
                "Accept": "application/json",
            }
        )

    # ============================================================
    # BASE URL
    # ============================================================

    @property
    def base_url(self) -> str:
        """
        Selecciona API gratuita o Pro según exista API key.
        """

        if self.api_key:
            return self.PRO_BASE_URL

        return self.FREE_BASE_URL

    # ============================================================
    # REQUEST
    # ============================================================

    def _request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        attempts: int = 3,
    ) -> Any:

        if attempts <= 0:
            raise ValueError(
                "attempts debe ser mayor que cero."
            )

        request_params = dict(
            params or {}
        )

        headers = {}

        if self.api_key:
            headers["x-cg-pro-api-key"] = (
                self.api_key
            )

        last_error: Exception | None = None

        for attempt in range(attempts):

            url = (
                f"{self.base_url}"
                f"{endpoint}"
            )

            try:

                response = self.session.get(
                    url,
                    params=request_params,
                    headers=headers,
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
                            30,
                        )

                    time.sleep(
                        max(
                            1,
                            delay,
                        )
                    )

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

        if last_error is not None:

            raise CoinGeckoProviderError(
                "No se pudo consultar CoinGecko: "
                f"{last_error}"
            ) from last_error

        raise CoinGeckoProviderError(
            "CoinGecko no respondió con datos válidos."
        )

    # ============================================================
    # MERCADOS
    # ============================================================

    def get_markets(
        self,
        limit: int = 100,
        page: int = 1,
    ) -> list[dict[str, Any]]:

        if limit <= 0:
            raise ValueError(
                "limit debe ser mayor que cero."
            )

        if page <= 0:
            raise ValueError(
                "page debe ser mayor que cero."
            )

        limit = min(
            limit,
            250,
        )

        params = {
            "vs_currency": "usd",
            "order": "volume_desc",
            "per_page": limit,
            "page": page,
            "sparkline": "false",
            "price_change_percentage": (
                "1h,24h,7d"
            ),
            "locale": "en",
        }

        data = self._request(
            endpoint=self.MARKETS_ENDPOINT,
            params=params,
        )

        if not isinstance(data, list):
            raise CoinGeckoProviderError(
                "Respuesta de mercados inválida."
            )

        return data

    # ============================================================
    # BUSCAR ACTIVO
    # ============================================================

    def get_asset_market(
        self,
        symbol: str,
    ) -> dict[str, Any] | None:
        """
        Busca información de mercado para un símbolo.

        Nota:
        CoinGecko utiliza IDs de monedas y no garantiza que
        el símbolo sea único. Por eso primero obtenemos un
        universo razonable y después hacemos una coincidencia
        controlada.
        """

        if not symbol or not symbol.strip():
            raise ValueError(
                "symbol no puede estar vacío."
            )

        target = symbol.strip().lower()

        markets = self.get_markets(
            limit=250,
            page=1,
        )

        matches = [
            coin
            for coin in markets
            if str(
                coin.get("symbol", "")
            ).lower()
            == target
        ]

        if not matches:
            return None

        # Preferimos coincidencia por símbolo
        # con mayor capitalización.
        matches.sort(
            key=lambda coin: float(
                coin.get(
                    "market_cap",
                    0,
                )
                or 0
            ),
            reverse=True,
        )

        coin = matches[0]

        return {
            "id": coin.get("id"),
            "name": coin.get("name"),
            "symbol": str(
                coin.get(
                    "symbol",
                    symbol,
                )
            ).upper(),
            "price": float(
                coin.get(
                    "current_price",
                    0,
                )
                or 0
            ),
            "market_cap": float(
                coin.get(
                    "market_cap",
                    0,
                )
                or 0
            ),
            "volume_24h": float(
                coin.get(
                    "total_volume",
                    0,
                )
                or 0
            ),
            "change_1h": float(
                coin.get(
                    "price_change_percentage_1h_in_currency",
                    0,
                )
                or 0
            ),
            "change_24h": float(
                coin.get(
                    "price_change_percentage_24h",
                    0,
                )
                or 0
            ),
            "change_7d": float(
                coin.get(
                    "price_change_percentage_7d_in_currency",
                    0,
                )
                or 0
            ),
            "market_cap_rank": coin.get(
                "market_cap_rank"
            ),
        }

    # ============================================================
    # MERCADO GLOBAL
    # ============================================================

    def get_global_market(
        self,
    ) -> dict[str, Any]:

        data = self._request(
            endpoint=self.GLOBAL_ENDPOINT,
        )

        if not isinstance(data, dict):
            raise CoinGeckoProviderError(
                "Respuesta global inválida."
            )

        market_data = data.get(
            "data"
        )

        if not isinstance(
            market_data,
            dict,
        ):
            raise CoinGeckoProviderError(
                "CoinGecko no devolvió "
                "market data global."
            )

        total_market_cap = (
            market_data.get(
                "total_market_cap",
                {},
            )
        )

        total_volume = (
            market_data.get(
                "total_volume",
                {},
            )
        )

        market_cap_percentage = (
            market_data.get(
                "market_cap_percentage",
                {},
            )
        )

        return {
            "total_market_cap_usd": float(
                total_market_cap.get(
                    "usd",
                    0,
                )
                or 0
            ),
            "total_volume_usd": float(
                total_volume.get(
                    "usd",
                    0,
                )
                or 0
            ),
            "btc_dominance": float(
                market_cap_percentage.get(
                    "btc",
                    0,
                )
                or 0
            ),
            "eth_dominance": float(
                market_cap_percentage.get(
                    "eth",
                    0,
                )
                or 0
            ),
            "active_cryptocurrencies": int(
                market_data.get(
                    "active_cryptocurrencies",
                    0,
                )
                or 0
            ),
            "markets": int(
                market_data.get(
                    "markets",
                    0,
                )
                or 0
            ),
        }