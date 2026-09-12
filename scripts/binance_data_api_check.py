from __future__ import annotations

import requests


URL = "https://data-api.binance.vision/api/v3/klines"

PARAMS = {
    "symbol": "BTCUSDT",
    "interval": "15m",
    "limit": 5,
}


def main() -> int:
    print("=" * 60)
    print("🧪 BINANCE DATA API")
    print("=" * 60)

    print(f"URL: {URL}")
    print(f"Par: {PARAMS['symbol']}")
    print(f"Intervalo: {PARAMS['interval']}")

    try:
        response = requests.get(
            URL,
            params=PARAMS,
            timeout=20,
        )

        print(f"\nHTTP: {response.status_code}")

        response.raise_for_status()

        data = response.json()

        if not isinstance(data, list):
            raise RuntimeError(
                "La respuesta no es una lista."
            )

        print(
            f"Velas recibidas: {len(data)}"
        )

        for candle in data:
            print(
                f"timestamp={candle[0]} "
                f"open={candle[1]} "
                f"high={candle[2]} "
                f"low={candle[3]} "
                f"close={candle[4]} "
                f"volume={candle[5]}"
            )

        print("\n🟢 BINANCE DATA API RESPONDE")
        return 0

    except Exception as exc:
        print("\n🔴 PRUEBA FALLIDA")
        print(
            f"{type(exc).__name__}: {exc}"
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())