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
        for punto in datos["prices"]
    ]


def calcular_rsi(precios, periodo=14):
    if len(precios) < periodo + 1:
        raise ValueError("No hay suficientes datos para calcular el RSI.")

    cambios = [
        precios[i] - precios[i - 1]
        for i in range(1, len(precios))
    ]

    ganancias = [
        max(cambio, 0)
        for cambio in cambios
    ]

    perdidas = [
        max(-cambio, 0)
        for cambio in cambios
    ]

    promedio_ganancia = sum(ganancias[:periodo]) / periodo
    promedio_perdida = sum(perdidas[:periodo]) / periodo

    for i in range(periodo, len(ganancias)):
        promedio_ganancia = (
            promedio_ganancia * (periodo - 1)
            + ganancias[i]
        ) / periodo

        promedio_perdida = (
            promedio_perdida * (periodo - 1)
            + perdidas[i]
        ) / periodo

    if promedio_perdida == 0:
        return 100.0

    rs = promedio_ganancia / promedio_perdida

    return 100 - (100 / (1 + rs))


def analizar(precio, cambio_24h, rsi):
    if cambio_24h <= -3 and rsi <= 30:
        return (
            "caida_rsi_fuerte",
            "🚨 ALERTA FUERTE DE BTC\n\n"
            f"₿ Precio: ${precio:,.2f}\n"
            f"📉 Cambio 24h: {cambio_24h:.2f}%\n"
            f"📊 RSI(14): {rsi:.2f}\n\n"
            "🟢 Caída importante + RSI en sobreventa.\n"
            "🎯 Posible zona de interés.\n\n"
            "⚠️ No es una señal garantizada de compra."
        )

    if cambio_24h <= -5:
        return (
            "caida_fuerte",
            "🚨 ALERTA BTC\n\n"
            f"₿ Precio: ${precio:,.2f}\n"
            f"📉 Cambio 24h: {cambio_24h:.2f}%\n"
            f"📊 RSI(14): {rsi:.2f}\n\n"
            "📉 BTC presenta una caída fuerte.\n"
            "👀 Vigilar el mercado."
        )

    if rsi <= 30:
        return (
            "rsi_sobreventa",
            "🟢 ALERTA RSI BTC\n\n"
            f"₿ Precio: ${precio:,.2f}\n"
            f"📉 Cambio 24h: {cambio_24h:.2f}%\n"
            f"📊 RSI(14): {rsi:.2f}\n\n"
            "🟢 RSI en zona de sobreventa.\n"
            "🎯 Posible zona de interés.\n\n"
            "⚠️ No es una señal garantizada de compra."
        )

    return None, None


if __name__ == "__main__":

    precio, cambio_24h = obtener_datos_bitcoin()

    precios = obtener_precios()

    rsi = calcular_rsi(precios)

    tipo_alerta, mensaje = analizar(
        precio,
        cambio_24h,
        rsi
    )

    estado = cargar_estado()

    ultima_alerta = estado.get("ultima_alerta")

    if tipo_alerta is None:

        guardar_estado(None)

        print("Sin alerta. No se envía mensaje a Telegram.")

    elif tipo_alerta != ultima_alerta:

        enviar_telegram(mensaje)

        guardar_estado(tipo_alerta)

        print(f"Nueva alerta enviada: {tipo_alerta}")

    else:

        print(
            f"La alerta '{tipo_alerta}' ya fue enviada. "
            "No se repite."
        )