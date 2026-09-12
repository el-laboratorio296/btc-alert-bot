from __future__ import annotations

import sys
import time

from radar.market import MarketDataManager, MarketDataError


SYMBOL = "BTC"
TIMEFRAMES = ("15m", "1h", "4h", "1d")
LIMIT = 60


def check_binance(manager: MarketDataManager) -> None:
    print("=" * 60)
    print("PRUEBA REAL: BINANCE")
    print("=" * 60)

    for timeframe in TIMEFRAMES:
        print(f"\n→ BTC {timeframe}")

        data = manager._load_binance_timeframe(
            symbol=SYMBOL,
            timeframe=timeframe,
            limit=LIMIT,
        )

        if not data.candles:
            raise RuntimeError(
                f"Binance no devolvió velas para {timeframe}."
            )

        print(f"  Velas recibidas: {len(data.candles)}")
        print(f"  Fuente: {data.quality.source}")
        print(
            f"  Último cierre: "
            f"{data.candles[-1].close}"
        )
        print(
            f"  Último timestamp: "
            f"{data.candles[-1].timestamp}"
        )
        print(
            f"  Última vela cerrada: "
            f"{data.candles[-1].is_closed}"
        )

        if len(data.candles) < 50:
            raise RuntimeError(
                f"Insuficientes velas para {timeframe}."
            )

        if data.quality is None:
            raise RuntimeError(
                f"Sin información de calidad para {timeframe}."
            )

    print("\n✓ Binance respondió correctamente.")


def check_coingecko(manager: MarketDataManager) -> None:
    print("\n" + "=" * 60)
    print("PRUEBA REAL: COINGECKO")
    print("=" * 60)

    ticker = manager._load_market_ticker(SYMBOL)

    print(f"\n→ {ticker.symbol}")
    print(f"  Precio: ${ticker.price:,.4f}")
    print(f"  Market cap: ${ticker.market_cap:,.0f}")
    print(f"  Volumen 24h: ${ticker.volume_24h:,.0f}")
    print(f"  Cambio 1h: {ticker.change_1h:.2f}%")
    print(f"  Cambio 24h: {ticker.change_24h:.2f}%")
    print(f"  Cambio 7d: {ticker.change_7d:.2f}%")

    if ticker.price <= 0:
        raise RuntimeError(
            "CoinGecko devolvió un precio inválido."
        )

    global_market = manager.get_global_market()

    print("\n→ Mercado global")
    print(
        "  Market cap global: "
        f"${global_market['total_market_cap_usd']:,.0f}"
    )
    print(
        "  Volumen global: "
        f"${global_market['total_volume_usd']:,.0f}"
    )
    print(
        "  Dominancia BTC: "
        f"{global_market['btc_dominance']:.2f}%"
    )
    print(
        "  Dominancia ETH: "
        f"{global_market['eth_dominance']:.2f}%"
    )

    if global_market["total_market_cap_usd"] <= 0:
        raise RuntimeError(
            "Market cap global inválido."
        )

    print("\n✓ CoinGecko respondió correctamente.")


def check_complete_asset(manager: MarketDataManager) -> None:
    print("\n" + "=" * 60)
    print("PRUEBA DE INTEGRACIÓN: MARKET.PY")
    print("=" * 60)

    asset = manager.get_asset(
        symbol=SYMBOL,
        timeframes=TIMEFRAMES,
        limit=LIMIT,
    )

    print(f"\nActivo: {asset.symbol}")
    print(f"Precio: ${asset.price:,.4f}")

    for timeframe, data in asset.timeframes.items():
        print(
            f"  {timeframe}: "
            f"{len(data.candles)} velas | "
            f"fuente={data.quality.source}"
        )

        if not data.candles:
            raise RuntimeError(
                f"Sin velas para {timeframe}."
            )

    print("\n✓ market.py integró correctamente")
    print("  CoinGecko + Binance.")


def main() -> int:
    print("\n")
    print("🧪 RADAR EL LABORATORIO")
    print("PRUEBA REAL DE PROVEEDORES")
    print(f"Timestamp: {time.time():.0f}")
    print("\n")

    manager = MarketDataManager()

    try:
        check_binance(manager)
        check_coingecko(manager)
        check_complete_asset(manager)

    except (
        MarketDataError,
        RuntimeError,
        ValueError,
    ) as exc:
        print("\n" + "=" * 60)
        print("❌ PRUEBA FALLIDA")
        print("=" * 60)
        print(f"Error: {exc}")
        return 1

    except Exception as exc:
        print("\n" + "=" * 60)
        print("❌ ERROR INESPERADO")
        print("=" * 60)
        print(
            f"{type(exc).__name__}: {exc}"
        )
        return 1

    print("\n" + "=" * 60)
    print("🟢 PRUEBA REAL COMPLETADA")
    print("=" * 60)
    print("Binance: OK")
    print("CoinGecko: OK")
    print("market.py: OK")
    print("Integración: OK")

    return 0


if __name__ == "__main__":
    sys.exit(main())