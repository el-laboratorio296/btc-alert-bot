from __future__ import annotations

import pytest

from radar.market import MarketDataError, MarketService
from radar.models import Candle, TimeframeData


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

        result = {}

        for timeframe in intervals:
            result[timeframe] = TimeframeData(
                timeframe=timeframe,
                candles=[
                    Candle(
                        timestamp=1700000000000,
                        open=100.0,
                        high=105.0,
                        low=95.0,
                        close=102.0,
                        volume=1000.0,
                        is_closed=True,
                    )
                ],
            )

        return result


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


def make_service(
    binance=None,
    coingecko=None,
):
    return MarketService(
        binance=binance or FakeBinance(),
        coingecko=coingecko or FakeCoinGecko(),
    )


def test_market_service_can_be_created():
    service = make_service()

    assert service is not None


def test_market_service_requires_binance():
    with pytest.raises(TypeError):
        MarketService(
            binance=None,
            coingecko=FakeCoinGecko(),
        )


def test_market_service_requires_coingecko():
    with pytest.raises(TypeError):
        MarketService(
            binance=FakeBinance(),
            coingecko=None,
        )


def test_empty_symbol_is_rejected():
    service = make_service()

    with pytest.raises(ValueError):
        service.get_asset("")


def test_whitespace_symbol_is_rejected():
    service = make_service()

    with pytest.raises(ValueError):
        service.get_asset("   ")


def test_symbol_without_usdt_is_normalized():
    service = make_service()

    result = service.get_asset("BTC")

    assert result.symbol == "BTCUSDT"


def test_symbol_with_usdt_is_preserved():
    service = make_service()

    result = service.get_asset("BTCUSDT")

    assert result.symbol == "BTCUSDT"


def test_symbol_is_case_insensitive():
    service = make_service()

    result = service.get_asset("btcusdt")

    assert result.symbol == "BTCUSDT"


def test_binance_receives_normalized_symbol():
    binance = FakeBinance()

    service = make_service(
        binance=binance,
    )

    service.get_asset("btc")

    assert binance.calls
    assert binance.calls[0]["symbol"] == "BTCUSDT"


def test_coingecko_receives_base_symbol():
    coingecko = FakeCoinGecko()

    service = make_service(
        coingecko=coingecko,
    )

    service.get_asset("BTCUSDT")

    assert coingecko.calls == ["BTC"]


def test_default_timeframes_are_requested():
    binance = FakeBinance()

    service = make_service(
        binance=binance,
    )

    service.get_asset("BTC")

    assert binance.calls[0]["intervals"] == (
        "15m",
        "1h",
        "4h",
        "1d",
    )


def test_custom_timeframes_are_forwarded():
    binance = FakeBinance()

    service = make_service(
        binance=binance,
    )

    service.get_asset(
        "BTC",
        intervals=("1h", "4h"),
    )

    assert binance.calls[0]["intervals"] == (
        "1h",
        "4h",
    )


def test_custom_limit_is_forwarded():
    binance = FakeBinance()

    service = make_service(
        binance=binance,
    )

    service.get_asset(
        "BTC",
        limit=100,
    )

    assert binance.calls[0]["limit"] == 100


def test_zero_limit_is_rejected():
    service = make_service()

    with pytest.raises(ValueError):
        service.get_asset(
            "BTC",
            limit=0,
        )


def test_negative_limit_is_rejected():
    service = make_service()

    with pytest.raises(ValueError):
        service.get_asset(
            "BTC",
            limit=-1,
        )


def test_non_integer_limit_is_rejected():
    service = make_service()

    with pytest.raises(ValueError):
        service.get_asset(
            "BTC",
            limit="200",
        )


def test_empty_intervals_are_rejected():
    service = make_service()

    with pytest.raises(ValueError):
        service.get_asset(
            "BTC",
            intervals=(),
        )


def test_none_intervals_are_rejected():
    service = make_service()

    with pytest.raises(ValueError):
        service.get_asset(
            "BTC",
            intervals=None,
        )


def test_non_string_timeframe_is_rejected():
    service = make_service()

    with pytest.raises(ValueError):
        service.get_asset(
            "BTC",
            intervals=(1,),
        )


def test_empty_timeframe_is_rejected():
    service = make_service()

    with pytest.raises(ValueError):
        service.get_asset(
            "BTC",
            intervals=("1h", ""),
        )


def test_duplicate_timeframes_are_rejected():
    service = make_service()

    with pytest.raises(ValueError):
        service.get_asset(
            "BTC",
            intervals=("1h", "1h"),
        )


def test_asset_returns_market_data():
    service = make_service()

    result = service.get_asset("BTC")

    assert result.symbol == "BTCUSDT"
    assert result.price == 102.0


def test_market_price_matches_ticker():
    service = make_service()

    result = service.get_asset("BTC")

    assert result.price == result.ticker.price


def test_market_metadata_is_preserved():
    service = make_service()

    result = service.get_asset("BTC")

    assert result.ticker.market_cap == 1_000_000.0
    assert result.ticker.volume_24h == 50_000.0
    assert result.ticker.change_1h == 0.5
    assert result.ticker.change_24h == 2.0
    assert result.ticker.change_7d == 5.0


def test_all_default_timeframes_are_present():
    service = make_service()

    result = service.get_asset("BTC")

    assert set(result.timeframes.keys()) == {
        "15m",
        "1h",
        "4h",
        "1d",
    }


def test_requested_timeframes_are_present():
    service = make_service()

    result = service.get_asset(
        "ETH",
        intervals=("1h", "4h"),
    )

    assert set(result.timeframes.keys()) == {
        "1h",
        "4h",
    }


def test_timeframe_contains_candles():
    service = make_service()

    result = service.get_asset("BTC")

    timeframe = result.get_timeframe("1h")

    assert timeframe is not None
    assert len(timeframe.candles) == 1


def test_candle_values_are_preserved():
    service = make_service()

    result = service.get_asset("BTC")

    candle = result.get_timeframe("1h").candles[0]

    assert candle.timestamp == 1700000000000
    assert candle.open == 100.0
    assert candle.high == 105.0
    assert candle.low == 95.0
    assert candle.close == 102.0
    assert candle.volume == 1000.0
    assert candle.is_closed is True


def test_open_candle_is_preserved():
    class OpenCandleBinance(FakeBinance):
        def get_multi_timeframe(
            self,
            symbol,
            intervals=("15m", "1h", "4h", "1d"),
            limit=200,
        ):
            result = {}

            for timeframe in intervals:
                result[timeframe] = TimeframeData(
                    timeframe=timeframe,
                    candles=[
                        Candle(
                            timestamp=1700000000000,
                            open=100.0,
                            high=105.0,
                            low=95.0,
                            close=102.0,
                            volume=1000.0,
                            is_closed=False,
                        )
                    ],
                )

            return result

    service = make_service(
        binance=OpenCandleBinance(),
    )

    result = service.get_asset("BTC")

    for timeframe in result.timeframes.values():
        assert timeframe.candles[0].is_closed is False


def test_binance_failure_becomes_market_error():
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

    service = make_service(
        binance=BrokenBinance(),
    )

    with pytest.raises(MarketDataError):
        service.get_asset("BTC")


def test_coingecko_failure_becomes_market_error():
    class BrokenCoinGecko:
        def get_asset_market(self, symbol):
            raise RuntimeError(
                "CoinGecko unavailable"
            )

    service = make_service(
        coingecko=BrokenCoinGecko(),
    )

    with pytest.raises(MarketDataError):
        service.get_asset("BTC")


def test_missing_coingecko_data_is_rejected():
    class EmptyCoinGecko:
        def get_asset_market(self, symbol):
            return None

    service = make_service(
        coingecko=EmptyCoinGecko(),
    )

    with pytest.raises(MarketDataError):
        service.get_asset("BTC")


def test_empty_coingecko_data_is_rejected():
    class EmptyCoinGecko:
        def get_asset_market(self, symbol):
            return {}

    service = make_service(
        coingecko=EmptyCoinGecko(),
    )

    with pytest.raises(MarketDataError):
        service.get_asset("BTC")


def test_missing_binance_data_is_rejected():
    class EmptyBinance:
        def get_multi_timeframe(
            self,
            symbol,
            intervals,
            limit,
        ):
            return {}

    service = make_service(
        binance=EmptyBinance(),
    )

    with pytest.raises(MarketDataError):
        service.get_asset("BTC")


def test_none_binance_data_is_rejected():
    class EmptyBinance:
        def get_multi_timeframe(
            self,
            symbol,
            intervals,
            limit,
        ):
            return None

    service = make_service(
        binance=EmptyBinance(),
    )

    with pytest.raises(MarketDataError):
        service.get_asset("BTC")


def test_missing_requested_timeframe_is_rejected():
    class PartialBinance:
        def get_multi_timeframe(
            self,
            symbol,
            intervals,
            limit,
        ):
            return {
                "1h": TimeframeData(
                    timeframe="1h",
                    candles=[
                        Candle(
                            timestamp=1700000000000,
                            open=100.0,
                            high=105.0,
                            low=95.0,
                            close=102.0,
                            volume=1000.0,
                            is_closed=True,
                        )
                    ],
                )
            }

    service = make_service(
        binance=PartialBinance(),
    )

    with pytest.raises(MarketDataError):
        service.get_asset(
            "BTC",
            intervals=("1h", "4h"),
        )


def test_invalid_candle_price_is_rejected():
    class InvalidBinance:
        def get_multi_timeframe(
            self,
            symbol,
            intervals,
            limit,
        ):
            return {
                "1h": TimeframeData(
                    timeframe="1h",
                    candles=[
                        Candle(
                            timestamp=1700000000000,
                            open=-100.0,
                            high=105.0,
                            low=95.0,
                            close=102.0,
                            volume=1000.0,
                            is_closed=True,
                        )
                    ],
                )
            }

    service = make_service(
        binance=InvalidBinance(),
    )

    with pytest.raises(MarketDataError):
        service.get_asset("BTC")


def test_invalid_volume_is_rejected():
    class InvalidBinance:
        def get_multi_timeframe(
            self,
            symbol,
            intervals,
            limit,
        ):
            return {
                "1h": TimeframeData(
                    timeframe="1h",
                    candles=[
                        Candle(
                            timestamp=1700000000000,
                            open=100.0,
                            high=105.0,
                            low=95.0,
                            close=102.0,
                            volume=-1.0,
                            is_closed=True,
                        )
                    ],
                )
            }

    service = make_service(
        binance=InvalidBinance(),
    )

    with pytest.raises(MarketDataError):
        service.get_asset("BTC")


def test_high_below_low_is_rejected():
    class InvalidBinance:
        def get_multi_timeframe(
            self,
            symbol,
            intervals,
            limit,
        ):
            return {
                "1h": TimeframeData(
                    timeframe="1h",
                    candles=[
                        Candle(
                            timestamp=1700000000000,
                            open=100.0,
                            high=90.0,
                            low=95.0,
                            close=97.0,
                            volume=1000.0,
                            is_closed=True,
                        )
                    ],
                )
            }

    service = make_service(
        binance=InvalidBinance(),
    )

    with pytest.raises(MarketDataError):
        service.get_asset("BTC")


def test_close_outside_range_is_rejected():
    class InvalidBinance:
        def get_multi_timeframe(
            self,
            symbol,
            intervals,
            limit,
        ):
            return {
                "1h": TimeframeData(
                    timeframe="1h",
                    candles=[
                        Candle(
                            timestamp=1700000000000,
                            open=100.0,
                            high=105.0,
                            low=95.0,
                            close=110.0,
                            volume=1000.0,
                            is_closed=True,
                        )
                    ],
                )
            }

    service = make_service(
        binance=InvalidBinance(),
    )

    with pytest.raises(MarketDataError):
        service.get_asset("BTC")


def test_timestamp_must_be_positive():
    class InvalidBinance:
        def get_multi_timeframe(
            self,
            symbol,
            intervals,
            limit,
        ):
            return {
                "1h": TimeframeData(
                    timeframe="1h",
                    candles=[
                        Candle(
                            timestamp=0,
                            open=100.0,
                            high=105.0,
                            low=95.0,
                            close=102.0,
                            volume=1000.0,
                            is_closed=True,
                        )
                    ],
                )
            }

    service = make_service(
        binance=InvalidBinance(),
    )

    with pytest.raises(MarketDataError):
        service.get_asset("BTC")


def test_multiple_calls_are_supported():
    service = make_service()

    first = service.get_asset("BTC")
    second = service.get_asset("ETH")

    assert first.symbol == "BTCUSDT"
    assert second.symbol == "ETHUSDT"


def test_different_assets_keep_their_data_separate():
    service = make_service()

    btc = service.get_asset("BTC")
    eth = service.get_asset("ETH")

    assert btc.symbol != eth.symbol
    assert btc.symbol == "BTCUSDT"
    assert eth.symbol == "ETHUSDT"


def test_market_service_preserves_provider_timeframe_order():
    service = make_service()

    result = service.get_asset("BTC")

    assert list(result.timeframes.keys()) == [
        "15m",
        "1h",
        "4h",
        "1d",
    ]


def test_market_service_returns_same_price_as_market_provider():
    coingecko = FakeCoinGecko()

    service = make_service(
        coingecko=coingecko,
    )

    result = service.get_asset("BTC")

    assert result.ticker.price == 102.0