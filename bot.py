import os
import json
import requests

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

STATE_FILE = "bot_state.json"

PRICE_URL = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=bitcoin&vs_currencies=usd&include_24hr_change=true"
)

CHART_URL = (
    "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
    "?vs_currency=usd&days=2&interval=hourly"
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


def cargar_estado():
    if not os.path.exists(STATE_FILE):
        return {"ultima_alerta": None}

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as archivo:
            return json.load(archivo)
    except (json.JSONDecodeError, OSError):
        return {"ultima_alerta": None}


def guardar_estado(ultima_alerta):
    estado = {
        "ultima_alerta": ultima_alerta
    }

    with open(STATE_FILE, "w", encoding="utf-8") as archivo:
        json.dump(estado, archivo)


def obtener_datos_bitcoin():
    respuesta = requests.get(
        PRICE_URL,
        timeout=15
    )

    respuesta.raise_for_status()

    datos = respuesta.json()

    precio = float(datos["bitcoin"]["usd"])
    cambio_24h = float(datos["bitcoin"]["usd_24h_change"])

    return precio, cambio_24h


def obtener_precios():
    respuesta = requests.get(
        CHART_URL,
        timeout=15
    )

    respuesta.raise_for_status()

    datos = respuesta.json()

    return [
        float(punto[1])
        for punto in datos["