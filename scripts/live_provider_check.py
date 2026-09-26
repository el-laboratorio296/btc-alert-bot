from __future__ import annotations

import os
import sys
import time

from radar.market import MarketDataError, MarketService
from radar.models import DataQuality, TimeframeData
from radar.providers.binance import BinanceProvider
from radar.providers.coingecko import CoinGeckoProvider


# ============================================================
# CONFIGURACIÓN
# ============================================================

SYMBOL = "BTC"

TIMEFRAMES = (
    "15m",
    "1h",
    "4h",
    "1d",
)

LIMIT = 60


# ============================================================
# ADAPTADOR BINANCE
# ============================================================

class BinanceIntegrationAdapter:
    """
    Adaptador entre BinanceProvider y MarketService.

    BinanceProvider entrega:

        dict[str, list[Candle]]

    MarketService trabaja con:

        dict[str, TimeframeData]
    """

    def __init__(
        self,
        provider: BinanceProvider,
    ) -> None:

        self.provider = provider

    def get_multi_timeframe(
        self,
        symbol: str,
        intervals: tuple[str, ...],
        limit: int,
    ) -> dict[str, TimeframeData]:

        raw_data = self.provider.get_multi_timeframe(
            symbol=symbol,
            intervals=intervals,
            limit=limit,
        )

        now = time.time()

        result: dict[str, TimeframeData] = {}

        for timeframe, candles in raw_data.items():

            if not candles:
                raise RuntimeError(
                    f"Binance no devolvió velas "
                    f"para {timeframe}."
                )

            latest = candles[-1]

            quality = DataQuality(
                source="binance",
                fetched_at=now,
                latest_candle_timestamp=latest.timestamp,
                is_complete=len(candles) >= limit,
                is_closed=latest.is_closed,
                age_seconds=max(
                    0.0,
                    now - (
                        latest.timestamp / 1000.0
                    ),
                ),
                message=(
                    "Datos reales obtenidos "
                    "desde Binance Data API."
                ),
            )

            result[timeframe] = TimeframeData(
                timeframe=timeframe,
                candles=candles,
                quality=quality,
            )

        return result


# ============================================================
# PRUEBA BINANCE
# ============================================================

def check_binance(
    provider: BinanceProvider,
) -> None:

    print()
    print("=" * 60)
    print("PRUEBA REAL: BINANCE")
    print("=" * 60)

    for timeframe in TIMEFRAMES:

        print()
        print(f"→ BTC {timeframe}")

        candles = provider.get_klines(
            symbol=SYMBOL,
            interval=timeframe,
            limit=LIMIT,
        )

        if not candles:

            raise RuntimeError(
                f"Binance no devolvió velas "
                f"para {timeframe}."
            )

        print(
            f"  Velas recibidas: "
            f"{len(candles)}"
        )

        print(
            f"  Último cierre: "
            f"{candles[-1].close}"
        )

       