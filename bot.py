import os
import requests

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

COINGECKO_URL = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=bitcoin&vs_currencies=usd&include_24hr_change=true"
)


def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    datos = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje
    }

    respuesta = requests.post(
        url,
        data=datos,
        timeout=15
    )

    respuesta.raise_for_status()


def obtener_bitcoin():
    respuesta = requests.get(
        COINGECKO_URL,
        timeout=15
    )

    respuesta.raise_for_status()

    datos = respuesta.json()

    precio = float(datos["bitcoin"]["usd"])
    cambio = float(datos["bitcoin"]["usd_24h_change"])

    return precio, cambio


if __name__ == "__main__":
    precio, cambio = obtener_bitcoin()

    mensaje = (
        "🤖 BTC ALERT BOT\n\n"
        f"₿ Bitcoin: ${precio:,.2f}\n"
        f"📊 Cambio 24h: {cambio:.2f}%\n\n"
        "✅ Sistema funcionando correctamente."
    )

    enviar_telegram(mensaje)