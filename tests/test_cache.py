from radar.cache import MarketCache


def test_cache_set_and_get(tmp_path):
    now = 1_000_000.0

    cache = MarketCache(
        directory=tmp_path,
        clock=lambda: now,
    )

    payload = {
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "candles": [
            {
                "open": 100,
                "high": 110,
                "low": 95,
                "close": 105,
                "volume": 1000,
            }
        ],
    }

    cache.set(
        key="binance:BTC:1h",
        payload=payload,
        source="binance",
    )

    result = cache.get(
        key="binance:BTC:1h",
        max_age_seconds=300,
    )

    assert result == payload


def test_cache_expires(tmp_path):
    current_time = [1_000_000.0]

    cache = MarketCache(
        directory=tmp_path,
        clock=lambda: current_time[0],
    )

    payload = {
        "symbol": "ETHUSDT",
    }

    cache.set(
        key="binance:ETH:1h",
        payload=payload,
        source="binance",
    )

    current_time[0] += 301

    result = cache.get(
        key="binance:ETH:1h",
        max_age_seconds=300,
    )

    assert result is None


def test_cache_allows_stale_data_when_requested(tmp_path):
    current_time = [1_000_000.0]

    cache = MarketCache(
        directory=tmp_path,
        clock=lambda: current_time[0],
    )

    payload = {
        "symbol": "BTCUSDT",
    }

    cache.set(
        key="binance:BTC:1h",
        payload=payload,
        source="binance",
    )

    current_time[0] += 1000

    result = cache.get(
        key="binance:BTC:1h",
        max_age_seconds=300,
        allow_stale=True,
    )

    assert result == payload


def test_cache_delete(tmp_path):
    cache = MarketCache(
        directory=tmp_path,
    )

    cache.set(
        key="binance:BTC:15m",
        payload={"symbol": "BTCUSDT"},
        source="binance",
    )

    assert cache.delete("binance:BTC:15m") is True
    assert cache.delete("binance:BTC:15m") is False


def test_cache_is_fresh(tmp_path):
    current_time = [1_000_000.0]

    cache = MarketCache(
        directory=tmp_path,
        clock=lambda: current_time[0],
    )

    cache.set(
        key="binance:SOL:4h",
        payload={"symbol": "SOLUSDT"},
        source="binance",
    )

    assert cache.is_fresh(
        key="binance:SOL:4h",
        max_age_seconds=300,
    )

    current_time[0] += 301

    assert not cache.is_fresh(
        key="binance:SOL:4h",
        max_age_seconds=300,
    )


def test_cache_clear(tmp_path):
    cache = MarketCache(
        directory=tmp_path,
    )

    cache.set(
        key="binance:BTC:1h",
        payload={"symbol": "BTCUSDT"},
        source="binance",
    )

    cache.set(
        key="binance:ETH:1h",
        payload={"symbol": "ETHUSDT"},
        source="binance",
    )

    assert cache.clear() == 2

    assert cache.stats()["entries"] == 0