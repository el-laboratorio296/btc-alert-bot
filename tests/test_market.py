from __future__ import annotations

import time

import pytest

from radar.market import (
    MarketDataError,
    MarketService,
)


class FakeBinance:
    def __init__(self):
        self.calls = []

    def get_multi_timeframe(
        self,
        symbol,
        intervals=("15m", "1h", "4h", "1d"),
        limit=200,
    ):
        self.calls.append(
            {
                "symbol": symbol,
                "intervals": intervals,
                "limit": limit,
            }
        )

        return {
            timeframe: {
                "candles": [
                    {
                        "timestamp": 1700000000000,
                        "open": 100.0,
                        "high": 105.0,
                        "low": 95.0,
                        "close": 102.0,
                        "volume": 1000.0,
                        "is_closed": True,
                    }
                ]
            }
            for timeframe in intervals
        }


class FakeCoinGecko:
    def __init__(self):
        self.calls = []

    def get_asset_market(self, symbol):
        self.calls.append(symbol)

        return {
            "id": symbol.lower(),
            "name": symbol,
            "symbol": symbol.lower(),
            "price": 102.0,
            "market_cap": 1_000_000.0,
            "volume_24h": 50_000.0,
            "change_1h": 0.5,
            "change_24h": 2.0,
            "change_7d": 5.0,
            "rank": 1,
        }


def test_market_service_can_be_created():
    service = MarketService(
        binance=FakeBinance(),
        coingecko=FakeCoinGecko(),
    )

    assert service is not None


def test_market_service_rejects_missing_binance():
    with pytest.raises(TypeError):
        MarketService(
            binance=None,
            coingecko=FakeCoinGecko(),
        )


def test_market_service_rejects_missing_coingecko():
    with pytest.raises(TypeError):
        MarketService(
            binance=FakeBinance(),
            coingecko=None,
        )


def test_symbol_is_normalized():
    service = MarketService(
        binance=FakeBinance(),
        coingecko=FakeCoinGecko(),
    )

    result = service.get_asset(
        "btcusdt"
    )

    assert result.symbol == "BTCUSDT"


def test_symbol_without_usdt_is_normalized():
    service = MarketService(
        binance=FakeBinance(),
        coingecko=FakeCoinGecko(),
    )

    result = service.get_asset(
        "BTC"
    )

    assert result.symbol == "BTCUSDT"


def test_empty_symbol_is_rejected():
    service = MarketService(
        binance=FakeBinance(),
        coingecko=FakeCoinGecko(),
    )

    with pytest.raises(ValueError):
        service.get_asset("")


def test_whitespace_symbol_is_rejected():
    service = MarketService(
        binance=FakeBinance(),
        coingecko=FakeCoinGecko(),
    )

    with pytest.raises(ValueError):
        service.get_asset("   ")


def test_get_asset_returns_market_data():
    service = MarketService(
        binance=FakeBinance(),
        coingecko=FakeCoinGecko(),
    )

    result = service.get_asset(
        "BTCUSDT"
    )

    assert result.symbol == "BTCUSDT"
    assert result.price == 102.0
    assert result.ticker.price == 102.0


def test_coin_gecko_is_called_with_base_symbol():
    coingecko = FakeCoinGecko()

    service = MarketService(
        binance=FakeBinance(),
        coingecko=coingecko,
    )

    service.get_asset(
        "BTCUSDT"
    )

    assert coingecko.calls == [
        "BTC"
    ]


def test_binance_receives_usdt_symbol():
    binance = FakeBinance()

    service = MarketService(
        binance=binance,
        coingecko=FakeCoinGecko(),
    )

    service.get_asset(
        "BTC"
    )

    assert binance.calls[0]["symbol"] == (
        "BTCUSDT"
    )


def test_default_timeframes_are_requested():
    binance = FakeBinance()

    service = MarketService(
        binance=binance,
        coingecko=FakeCoinGecko(),
    )

    service.get_asset(
        "BTCUSDT"
    )

    assert binance.calls[0]["intervals"] == (
        "15m",
        "1h",
        "4h",
        "1d",
    )


def test_custom_timeframes_are_supported():
    binance = FakeBinance()

    service = MarketService(
        binance=binance,
        coingecko=FakeCoinGecko(),
    )

    service.get_asset(
        "BTCUSDT",
        intervals=(
            "1h",
            "4h",
        ),
    )

    assert binance.calls[0]["intervals"] == (
        "1h",
        "4h",
    )


def test_custom_limit_is_forwarded():
    binance = FakeBinance()

    service = MarketService(
        binance=binance,
        coingecko=FakeCoinGecko(),
    )

    service.get_asset(
        "BTCUSDT",
        limit=100,
    )

    assert binance.calls[0]["limit"] == 100


def test_invalid_limit_is_rejected():
    service = MarketService(
        binance=FakeBinance(),
        coingecko=FakeCoinGecko(),
    )

    with pytest.raises(ValueError):
        service.get_asset(
            "BTCUSDT",
            limit=0,
        )


def test_negative_limit_is_rejected():
    service = MarketService(
        binance=FakeBinance(),
        coingecko=FakeCoinGecko(),
    )

    with pytest.raises(ValueError):
        service.get_asset(
            "BTCUSDT",
            limit=-1,
        )


def test_empty_intervals_are_rejected():
    service = MarketService(
        binance=FakeBinance(),
        coingecko=FakeCoinGecko(),
    )

    with pytest.raises(ValueError):
        service.get_asset(
            "BTCUSDT",
            intervals=(),
        )


def test_empty_timeframe_is_rejected():
    service = MarketService(
        binance=FakeBinance(),
        coingecko=FakeCoinGecko(),
    )

    with pytest.raises(ValueError):
        service.get_asset(
            "BTCUSDT",
            intervals=(
                "1h",
                "",
            ),
        )


def test_duplicate_timeframes_are_rejected():
    service = MarketService(
        binance=FakeBinance(),
        coingecko=FakeCoinGecko(),
    )

    with pytest.raises(ValueError):
        service.get_asset(
            "BTCUSDT",
            intervals=(
                "1h",
                "1h",
            ),
        )


def test_timeframe_data_is_populated():
    service = MarketService(
        binance=FakeBinance(),
        coingecko=FakeCoinGecko(),
    )

    result = service.get_asset(
        "BTCUSDT"
    )

    assert "15m" in result.timeframes
    assert "1h" in result.timeframes
    assert "4h" in result.timeframes
    assert "1d" in result.timeframes


def test_timeframe_candles_are_populated():
    service = MarketService(
        binance=FakeBinance(),
        coingecko=FakeCoinGecko(),
    )

    result = service.get_asset(
        "BTCUSDT"
    )

    timeframe = result.get_timeframe(
        "1h"
    )

    assert timeframe is not None
    assert len(
        timeframe.candles
    ) == 1


def test_candle_values_are_normalized():
    service = MarketService(
        binance=FakeBinance(),
        coingecko=FakeCoinGecko(),
    )

    result = service.get_asset(
        "BTCUSDT"
    )

    candle = result.get_timeframe(
        "1h"
    ).candles[0]

    assert candle.open == 100.0
    assert candle.high == 105.0
    assert candle.low == 95.0
    assert candle.close == 102.0
    assert candle.volume == 1000.0
    assert candle.is_closed is True


def test_latest_price_matches_market_ticker():
    service = MarketService(
        binance=FakeBinance(),
        coingecko=FakeCoinGecko(),
    )

    result = service.get_asset(
        "BTCUSDT"
    )

    assert result.price == 102.0
    assert result.ticker.price == 102.0


def test_market_metadata_is_preserved():
    service = MarketService(
        binance=FakeBinance(),
        coingecko=FakeCoinGecko(),
    )

    result = service.get_asset(
        "BTCUSDT"
    )

    assert result.ticker.market_cap == (
        1_000_000.0
    )

    assert result.ticker.volume_24h == (
        50_000.0
    )

    assert result.ticker.change_1h == 0.5
    assert result.ticker.change_24h == 2.0
    assert result.ticker.change_7d == 5.0


def test_binance_failure_raises_market_error():
    class BrokenBinance:
        def get_multi_timeframe(
            self,
            symbol,
            intervals,
            limit,
        ):
            raise RuntimeError(
                "Binance unavailable"
            )

    service = MarketService(
        binance=BrokenBinance(),
        coingecko=FakeCoinGecko(),
    )

    with pytest.raises(
        MarketDataError
    ):
        service.get_asset(
            "BTCUSDT"
        )


def test_coingecko_failure_raises_market_error():
    class BrokenCoinGecko:
        def get_asset_market(
            self,
            symbol,
        ):
            raise RuntimeError(
                "CoinGecko unavailable"
            )

    service = MarketService(
        binance=FakeBinance(),
        coingecko=BrokenCoinGecko(),
    )

    with pytest.raises(
        MarketDataError
    ):
        service.get_asset(
            "BTCUSDT"
        )


def test_missing_coin_gecko_data_is_rejected():
    class EmptyCoinGecko:
        def get_asset_market(
            self,
            symbol,
        ):
            return None

    service = MarketService(
        binance=FakeBinance(),
        coingecko=EmptyCoinGecko(),
    )

    with pytest.raises(
        MarketDataError
    ):
        service.get_asset(
            "BTCUSDT"
        )


def test_missing_binance_data_is_rejected():
    class EmptyBinance:
        def get_multi_timeframe(
            self,
            symbol,
            intervals,
            limit,
        ):
            return {}

    service = MarketService(
        binance=EmptyBinance(),
        coingecko=FakeCoinGecko(),
    )

    with pytest.raises(
        MarketDataError
    ):
        service.get_asset(
            "BTCUSDT"
        )


def test_none_binance_data_is_rejected():
    class EmptyBinance:
        def get_multi_timeframe(
            self,
            symbol,
            intervals,
            limit,
        ):
            return None

    service = MarketService(
        binance=EmptyBinance(),
        coingecko=FakeCoinGecko(),
    )

    with pytest.raises(
        MarketDataError
    ):
        service.get_asset(
            "BTCUSDT"
        )


def test_invalid_candle_data_is_rejected():
    class InvalidBinance:
        def get_multi_timeframe(
            self,
            symbol,
            intervals,
            limit,
        ):
            return {
                "1h": {
                    "candles": [
                        {
                            "timestamp": 1,
                            "open": -100.0,
                            "high": 105.0,
                            "low": 95.0,
                            "close": 102.0,
                            "volume": 1000.0,
                            "is_closed": True,
                        }
                    ]
                }
            }

    service = MarketService(
        binance=InvalidBinance(),
        coingecko=FakeCoinGecko(),
    )

    with pytest.raises(
        MarketDataError
    ):
        service.get_asset(
            "BTCUSDT"
        )


def test_open_candle_is_preserved():
    class OpenBinance:
        def get_multi_timeframe(
            self,
            symbol,
            intervals,
            limit,
        ):
            return {
                timeframe: {
                    "candles": [
                        {
                            "timestamp": 1700000000000,
                            "open": 100.0,
                            "high": 105.0,
                            "low": 95.0,
                            "close": 102.0,
                            "volume": 1000.0,
                            "is_closed": False,
                        }
                    ]
                }
                for timeframe in intervals
            }

    service = MarketService(
        binance=OpenBinance(),
        coingecko=FakeCoinGecko(),
    )

    result = service.get_asset(
        "BTCUSDT"
    )

    for timeframe in result.timeframes.values():
        assert (
            timeframe.candles[0].is_closed
            is False
        )


def test_service_does_not_mutate_provider_data():
    binance = FakeBinance()

    service = MarketService(
        binance=binance,
        coingecko=FakeCoinGecko(),
    )

    result = service.get_asset(
        "BTCUSDT"
    )

    result.timeframes[
        "1h"
    ].candles[0]

    assert binance.calls
    assert result is not None


def test_get_asset_is_repeatable():
    service = MarketService(
        binance=FakeBinance(),
        coingecko=FakeCoinGecko(),
    )

    first = service.get_asset(
        "BTCUSDT"
    )

    second = service.get_asset(
        "BTCUSDT"
    )

    assert first.symbol == second.symbol
    assert first.price == second.price
    assert set(
        first.timeframes.keys()
    ) == set(
        second.timeframes.keys()
    )


def test_service_clock_can_be_injected():
    service = MarketService(
        binance=FakeBinance(),
        coingecko=FakeCoinGecko(),
        clock=lambda: 1700001000.0,
    )

    result = service.get_asset(
        "BTCUSDT"
    )

    assert result is not None


def test_market_service_does_not_use_future_candles():
    class FutureBinance:
        def get_multi_timeframe(
            self,
            symbol,
            intervals,
            limit,
        ):
            return {
                "1h": {
                    "candles": [
                        {
                            "timestamp": 9999999999999,
                            "open": 100.0,
                            "high": 105.0,
                            "low": 95.0,
                            "close": 102.0,
                            "volume": 1000.0,
                            "is_closed": True,
                        }
                    ]
                }
            }

    service = MarketService(
        binance=FutureBinance(),
        coingecko=FakeCoinGecko(),
        clock=lambda: 1700001000.0,
    )

    with pytest.raises(
        MarketDataError
    ):
        service.get_asset(
            "BTCUSDT"
        )


def test_invalid_timeframe_type_is_rejected():
    service = MarketService(
        binance=FakeBinance(),
        coingecko=FakeCoinGecko(),
    )

    with pytest.raises(
        ValueError
    ):
        service.get_asset(
            "BTCUSDT",
            intervals=None,
        )


def test_non_string_timeframe_is_rejected():
    service =