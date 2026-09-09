import os
import requests

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    datos = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje
    }

    respuesta = requests.post(url, data=datos, timeout=15)
    respuesta.raise_for_status()


if __name__ == "__main__":
    enviar_telegram(
        "🤖 BTC ALERT BOT\n\n"
        "✅ El sistema está funcionando correctamente."
    )