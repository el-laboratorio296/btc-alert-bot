from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class Candle:
    """
    Representa una vela OHLCV normalizada.

    timestamp:
        Tiempo de apertura de la vela en milisegundos Unix.

    is_closed:
        Indica si la vela ya terminó.
        El Radar no debe utilizar velas abiertas para confirmar señales.
    """

    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_closed: bool = True


@dataclass(frozen=True)
class DataQuality:
    """
    Describe la calidad y actualidad de un conjunto de datos.
    """

    source: str
    fetched_at: float
    latest_candle_timestamp: int
    is_complete: bool
    is_closed: bool
    age_seconds: float
    message: str = ""


@dataclass(frozen=True)
class MarketTicker:
    """
    Información de mercado de un activo.
    """

    symbol: str
    price: float

    market_cap: float = 0.0
    volume_24h: float = 0.0

    change_1h: float = 0.0
    change_24h: float = 0.0
    change_7d: float = 0.0


@dataclass
class TimeframeData:
    """
    Datos completos de un activo para un timeframe determinado.
    """

    timeframe: str
    candles: List[Candle] = field(default_factory=list)
    quality: DataQuality | None = None

    @property
    def closes(self) -> List[float]:
        """
        Devuelve únicamente los precios de cierre.
        """

        return [
            candle.close
            for candle in self.candles
        ]

    @property
    def volumes(self) -> List[float]:
        """
        Devuelve únicamente los volúmenes.
        """

        return [
            candle.volume
            for candle in self.candles
        ]

    @property
    def last_candle(self) -> Candle | None:
        """
        Devuelve la última vela disponible.
        """

        if not self.candles:
            return None

        return self.candles[-1]


@dataclass
class AssetMarketData:
    """
    Contenedor principal de datos de un activo.

    Ejemplo:

        BTC
        ├── ticker
        ├── 15m
        ├── 1h
        ├── 4h
        └── 1d
    """

    symbol: str
    ticker: MarketTicker

    timeframes: Dict[
        str,
        TimeframeData,
    ] = field(default_factory=dict)

    def get_timeframe(
        self,
        timeframe: str,
    ) -> TimeframeData | None:
        """
        Recupera los datos de un timeframe.
        """

        return self.timeframes.get(timeframe)

    @property
    def price(self) -> float:
        """
        Precio actual del activo.
        """

        return self.ticker.price