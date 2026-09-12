from __future__ import annotations

from radar.market import MarketDataManager
from radar.models import Candle


class FakeBinance:
    def get_klines(self, symbol, interval, limit=500):
        candles = []

        for index in range(60):
            price = 100.0 + index

            candles.append(
                Candle(
                    timestamp=(index + 1) * 60_000,
                    open=price,
                    high=price + 2,
                    low=price - 2,
                    close=price + 1,
                    volume=1000.0 + index,
                    is_closed=True,
                )
            )

        return candles


class FakeCoinGecko:
    def get_asset_market(self, symbol):
        return {
            "id": symbol.lower(),
            "name": symbol,
            "symbol": symbol,
            "price": 101.0,
            "market_cap": 1_000_000_000.0,
            "volume_24h": 100_000_000.0,
            "change_1h": 1.0,
            "change_24h": 3.0,
            "change_7d": 5.0,
        }

    def get_global_market(self):
        return {
            "total_market_cap_usd": 2_000_000_000_000.0,
            "total_volume_usd": 100_000_000_000.0,
            "btc_dominance": 55.0,
            "eth_dominance": 18.0,
            "active_cryptocurrencies": 10_000,
            "markets": 500,
        }


def create_manager(tmp_path):
    from radar.cache import MarketCache

    cache = MarketCache(
        directory=tmp_path,
    )

    return MarketDataManager(
        binance=FakeBinance(),
        coingecko=FakeCoinGecko(),
        cache=cache,
    )


def test_market_manager_imports_and_builds_asset(tmp_path):
    manager = create_manager(tmp_path)

    asset = manager.get_asset(
        symbol="BTC",
        timeframes=("15m", "1h", "4h", "1d"),
        limit=60,
    )

    assert asset.symbol == "BTC"
    assert asset.price == 101.0

    assert "15m" in asset.timeframes
    assert "1h" in asset.timeframes
    assert "4h" in asset.timeframes
    assert "1d" in asset.timeframes

    for timeframe in ("15m", "1h", "4h", "1d"):
        data = asset.timeframes[timeframe]

        assert len(data.candles) == 60
        assert data.quality is not None
        assert data.quality.source == "binance"
        assert data.quality.is_complete is True
        assert data.quality.is_closed is True


def test_market_manager_validates_candles(tmp_path):
    manager = create_manager(tmp_path)

    candles = FakeBinance().get_klines(
        symbol="BTC",
        interval="1h",
        limit=60,
    )

    valid, message = manager._validate_candles(
        candles,
        "1h",
    )

    assert valid is True
    assert message == "Datos válidos."


def test_market_manager_rejects_bad_candles(tmp_path):
    manager = create_manager(tmp_path)

    candles = FakeBinance().get_klines(
        symbol="BTC",
        interval="1h",
        limit=60,
    )

    bad_candle = Candle(
        timestamp=999_999_999,
        open=100.0,
        high=90.0,
        low=80.0,
        close=85.0,
        volume=1000.0,
        is_closed=True,
    )

    candles[-1] = bad_candle

    valid, message = manager._validate_candles(
        candles,
        "1h",
    )

    assert valid is False
    assert "High menor que open" in message


def test_market_manager_uses_cache(tmp_path):
    manager = create_manager(tmp_path)

    first = manager.get_asset(
        symbol="BTC",
        timeframes=("1h",),
        limit=60,
    )

    assert first.timeframes["1h"].quality is not None
    assert first.timeframes["1h"].quality.source == "binance"

    second = manager.get_asset(
        symbol="BTC",
        timeframes=("1h",),
        limit=60,
    )

    assert second.timeframes["1h"].quality is not None
    assert second.timeframes["1h"].quality.source == "binance-cache"


def test_global_market_data(tmp_path):
    manager = create_manager(tmp_path)

    global_market = manager.get_global_market()

    assert global_market["total_market_cap_usd"] == 2_000_000_000_000.0
    assert global_market["total_volume_usd"] == 100_000_000_000.0
    assert global_market["btc_dominance"] == 55.0
    assert global_market["eth_dominance"] == 18.0