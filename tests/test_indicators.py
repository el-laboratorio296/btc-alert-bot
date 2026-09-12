from __future__ import annotations

import math

import pytest

from radar.indicators import (
    atr,
    compute_indicators,
    ema,
    momentum,
    relative_volume,
    rsi,
    true_range,
    trend_from_emas,
    volatility,
)


# ============================================================
# HELPERS
# ============================================================


def assert_close(
    actual: float | None,
    expected: float,
    *,
    rel: float = 1e-9,
    abs_tol: float = 1e-9,
) -> None:
    """
    Comparación segura para números flotantes.

    Evita falsos errores como:

        19.999999999999996 != 20.0
    """

    assert actual is not None
    assert actual == pytest.approx(
        expected,
        rel=rel,
        abs=abs_tol,
    )


# ============================================================
# EMA
# ============================================================


def test_ema_rejects_invalid_period() -> None:
    values = [100.0, 110.0, 120.0]

    with pytest.raises(ValueError):
        ema(values, 0)


def test_ema_rejects_empty_values() -> None:
    with pytest.raises(ValueError):
        ema([], 3)


def test_ema_returns_none_until_enough_data() -> None:
    values = [100.0, 110.0, 120.0]

    result = ema(values, 5)

    assert len(result) == len(values)

    for value in result:
        assert value is None


def test_ema_calculates_values() -> None:
    values = [
        100.0,
        110.0,
        120.0,
        130.0,
    ]

    result = ema(values, 2)

    assert len(result) == len(values)

    assert result[0] is None

    assert_close(
        result[1],
        105.0,
    )

    # EMA:
    # 120 * 2/3 + 105 * 1/3
    expected = (
        120.0 * (2.0 / 3.0)
        + 105.0 * (1.0 / 3.0)
    )

    assert_close(
        result[2],
        expected,
    )


# ============================================================
# RSI
# ============================================================


def test_rsi_rejects_invalid_period() -> None:
    values = [100.0, 101.0, 102.0]

    with pytest.raises(ValueError):
        rsi(values, 0)


def test_rsi_returns_none_until_enough_data() -> None:
    values = [
        100.0,
        101.0,
        102.0,
    ]

    result = rsi(values, 14)

    assert len(result) == len(values)

    for value in result:
        assert value is None


def test_rsi_detects_strong_uptrend() -> None:
    values = [
        100.0,
        101.0,
        102.0,
        103.0,
        104.0,
        105.0,
        106.0,
        107.0,
        108.0,
        109.0,
        110.0,
        111.0,
        112.0,
        113.0,
        114.0,
        115.0,
    ]

    result = rsi(values, 14)

    assert len(result) == len(values)

    last = result[-1]

    assert last is not None
    assert 0.0 <= last <= 100.0

    # Una serie que solamente sube debe producir
    # un RSI muy alto.
    assert last > 90.0


def test_rsi_detects_strong_downtrend() -> None:
    values = [
        115.0,
        114.0,
        113.0,
        112.0,
        111.0,
        110.0,
        109.0,
        108.0,
        107.0,
        106.0,
        105.0,
        104.0,
        103.0,
        102.0,
        101.0,
        100.0,
    ]

    result = rsi(values, 14)

    last = result[-1]

    assert last is not None
    assert 0.0 <= last <= 100.0

    assert last < 10.0


# ============================================================
# TRUE RANGE
# ============================================================


def test_true_range_first_candle() -> None:
    result = true_range(
        high=110.0,
        low=100.0,
        previous_close=None,
    )

    assert_close(
        result,
        10.0,
    )


def test_true_range_uses_previous_close() -> None:
    result = true_range(
        high=110.0,
        low=100.0,
        previous_close=90