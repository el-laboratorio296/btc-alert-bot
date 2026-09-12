from __future__ import annotations

import pytest
import requests

from radar.models import Candle
from radar.providers.binance import (
    BinanceProvider,
    BinanceProviderError,
)


# ============================================================
# RESPUESTA FALSA
# ============================================================

class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(
                f"HTTP {self.status_code}"
            )

    def json(self):
        return self._payload


# ============================================================
# SESIÓN FALSA
# ============================================================

class FakeSession:
    def __init__(self, response):
        self.response = response
        self.headers = {}
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append(
            {
                "url": url,
                "params": params,
                "timeout": timeout,
            }
        )

        return self.response


# ============================================================
# VELA BINANCE SIMULADA
# ============================================================

def make_kline(
    timestamp=1_700_000_000_000,
    open_price=100.0,
    high_price=110.0,
    low_price=95.0,
    close_price=105.0,
    volume=1000.0,
    close_time=None,
):
    if close_time is None:
        close_time = timestamp + 899_999

    return [
        timestamp,
        str(open_price),
        str(high_price),
        str(low_price),
        str(close_price),
        str(volume),
        close_time,
        "0",
        10,
        "0",
        "0",
        "0",
    ]


# ============================================================
# SÍMBOLOS
# ============================================================

def test_normalize_symbol():
    assert BinanceProvider.normalize_symbol("BTC") == "BTCUSDT"
    assert BinanceProvider.normalize_symbol("btc") == "BTCUSDT"
    assert BinanceProvider.normalize_symbol("BTCUSDT") == "BTCUSDT"
    assert BinanceProvider.normalize_symbol(" eth ") == "ETHUSDT"


def test_normalize_symbol_rejects_empty():
    with pytest.raises(ValueError):
        BinanceProvider.normalize_symbol("")


def test_normalize_symbol_rejects_non_string():
    with pytest.raises(ValueError):
        BinanceProvider.normalize_symbol(123)


# ============================================================
# INTERVALOS
# ============================================================

def test_validate_interval():
    assert BinanceProvider.validate_interval("15m") == "15m"
    assert BinanceProvider.validate_interval("1h") == "1h"
    assert BinanceProvider.validate_interval("4h") == "4h"
    assert BinanceProvider.validate_interval("1d") == "1d"


def test_validate_interval_rejects_invalid():
    with pytest.raises(ValueError):
        BinanceProvider.validate_interval("17m")


# ============================================================
# LIMIT
# ============================================================

def test_validate_limit():
    assert BinanceProvider.validate_limit(1) == 1
    assert BinanceProvider.validate_limit(60) == 60
    assert BinanceProvider.validate_limit(1000) == 1000


def test_validate_limit_rejects_zero():
    with pytest.raises(ValueError):
        BinanceProvider.validate_limit(0)


def test_validate_limit_rejects_above_maximum():
    with pytest.raises(ValueError):
        BinanceProvider.validate_limit(1001)


# ============================================================
# PARSEO DE VELAS
# ============================================================

def test_parse_candle_creates_candle():
    raw = make_kline(
        timestamp=1_700_000_000_000,
        open_price=100,
        high_price=110,
        low_price=95,
        close_price=105,
        volume=1000,
        close_time=1_700_000_899_999,
    )

    candle = BinanceProvider._parse_candle(
        raw,
        1_700_001_000_000,
    )

    assert isinstance(candle, Candle)
    assert candle.timestamp == 1_700_000_000_000
    assert candle.open == 100
    assert candle.high == 110
    assert candle.low == 95
    assert candle.close == 105
    assert candle.volume == 1000
    assert candle.is_closed is True


def test_parse_candle_detects_open_candle():
    raw = make_kline(
        timestamp=1_700_000_000_000,
        close_time=1_700_000_899_999,
    )

    candle = BinanceProvider._parse_candle(
        raw,
        1_700_000_500_000,
    )

    assert candle.is_closed is False


def test_parse_candle_rejects_bad_format():
    with pytest.raises(BinanceProviderError):
        BinanceProvider._parse_candle(
            "invalid",
            1_700_001_000_000,
        )


def test_parse_candle_rejects_missing_fields():
    with pytest.raises(BinanceProviderError):
        BinanceProvider._parse_candle(
            [1, 2, 3],
            1_700_001_000_000,
        )


def test_parse_candle_rejects_invalid_numbers():
    raw = make_kline()
    raw[4] = "NO_ES_NUMERO"

    with pytest.raises(BinanceProviderError):
        BinanceProvider._parse_candle(
            raw,
            1_700_001_000_000,
        )


# ============================================================
# VALIDACIÓN OHLCV
# ============================================================

def test_parse_candle_rejects_negative_price():
    raw = make_kline(
        open_price=-100,
    )

    with pytest.raises(BinanceProviderError):
        BinanceProvider._parse_candle(
            raw,
            1_700_001_000_000,
        )


def test_parse_candle_rejects_negative_volume():
    raw = make_kline(
        volume=-10,
    )

    with pytest.raises(BinanceProviderError):
        BinanceProvider._parse_candle(
            raw,
            1_700_001_000_000,
        )


def test_parse_candle_rejects_invalid_ohlc():
    raw = make_kline(
        open_price=100,
        high_price=90,
        low_price=95,
        close_price=105,
    )

    with pytest.raises(BinanceProviderError):
        BinanceProvider._parse_candle(
            raw,
            1_700_001_000_000,
        )


# ============================================================
# DATA API BINANCE
# ============================================================

def test_request_uses_data_api_binance():
    response = FakeResponse(
        status_code=200,
        payload=[],
    )

    session = FakeSession(response)

    provider = BinanceProvider(
        session=session,
    )

    result = provider._request(
        provider.KLINES_ENDPOINT,
        {
            "symbol": "BTCUSDT",
            "interval": "15m",
            "limit": 5,
        },
    )

    assert result == []
    assert len(session.calls) == 1

    call = session.calls[0]

    assert (
        call["url"]
        == "https://data-api.binance.vision/api/v3/klines"
    )

    assert call["params"]["symbol"] == "BTCUSDT"
    assert call["params"]["interval"] == "15m"
    assert call["params"]["limit"] == 5


# ============================================================
# GET KLINES
# ============================================================

def test_get_klines_returns_candles():
    raw_data = [
        make_kline(
            timestamp=1_700_000_000_000,
            close_price=100,
        ),
        make_kline(
            timestamp=1_700_000_900_000,
            close_price=105,
        ),
        make_kline(
            timestamp=1_700_001_800_000,
            close_price=110,
        ),
    ]

    response = FakeResponse(
        status_code=200,
        payload=raw_data,
    )

    session = FakeSession(response)

    provider = BinanceProvider(
        session=session,
    )

    candles = provider.get_klines(
        "BTC",
        "15m",
        limit=3,
    )

    assert len(candles) == 3

    assert all(
        isinstance(candle, Candle)
        for candle in candles
    )

    assert candles[0].close == 100
    assert candles[1].close == 105
    assert candles[2].close == 110


def test_get_klines_normalizes_symbol():
    response = FakeResponse(
        status_code=200,
        payload=[
            make_kline(),
        ],
    )

    session = FakeSession(response)

    provider = BinanceProvider(
        session=session,
    )

    provider.get_klines(
        "btc",
        "15m",
        limit=1,
    )

    call = session.calls[0]

    assert (
        call["params"]["symbol"]
        == "BTCUSDT"
    )


# ============================================================
# MULTI TIMEFRAME
# ============================================================

def test_get_multi_timeframe():
    response = FakeResponse(
        status_code=200,
        payload=[
            make_kline(),
        ],
    )

    session = FakeSession(response)

    provider = BinanceProvider(
        session=session,
    )

    result = provider.get_multi_timeframe(
        "BTC",
        intervals=("15m", "1h", "4h"),
        limit=1,
    )

    assert set(result.keys()) == {
        "15m",
        "1h",
        "4h",
    }

    assert len(result["15m"]) == 1
    assert len(result["1h"]) == 1
    assert len(result["4h"]) == 1


# ============================================================
# ERRORES HTTP
# ============================================================

def test_request_raises_provider_error_on_http_error():
    response = FakeResponse(
        status_code=451,
        payload={
            "code": -1000,
            "msg": "Unavailable",
        },
    )

    session = FakeSession(response)

    provider = BinanceProvider(
        session=session,
        max_retries=1,
    )

    with pytest.raises(BinanceProviderError):
        provider._request(
            provider.KLINES_ENDPOINT,
            {
                "symbol": "BTCUSDT",
                "interval": "15m",
                "limit": 5,
            },
        )


# ============================================================
# CONFIGURACIÓN
# ============================================================

def test_binance_provider_configuration():
    provider = BinanceProvider()

    assert (
        provider.BASE_URL
        == "https://data-api.binance.vision"
    )

    assert provider.DEFAULT_TIMEOUT == 20
    assert provider.MAX_LIMIT == 1000