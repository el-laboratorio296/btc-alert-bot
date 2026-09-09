import os
import requests

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

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

    precios = [
        float(punto[1])
        for punto in datos["prices"]
    ]

    return precios


def calcular_rsi(precios, periodo=14):
    if len(precios) < periodo + 1:
        raise ValueError("No hay suficientes datos para calcular el RSI.")

    cambios = []

    for i in range(1, len(precios)):
        cambios.append(precios[i] - precios[i - 1])

    ganancias = []
    perdidas = []

    for cambio in cambios:
        if cambio > 0:
            ganancias.append(cambio)
            perdidas.append(0)
        else:
            ganancias.append(0)
            perdidas.append(abs(cambio))

    promedio_ganancia = sum(ganancias[:periodo]) / periodo
    promedio_perdida = sum(perdidas[:periodo]) / periodo

    for i in range(periodo, len(ganancias)):
        promedio_ganancia = (
            (promedio_ganancia * (periodo - 1))
            + ganancias[i]
        ) / periodo

        promedio_perdida = (
            (promedio_perdida * (periodo - 1))
            + perdidas[i]
        ) / periodo

    if promedio_perdida == 0:
        return 100.0

    rs = promedio_ganancia / promedio_perdida

    rsi = 100 - (100 / (1 + rs))

    return rsi


def analizar(precio, cambio_24h, rsi):
    alertas = []

    if cambio_24h <= -5:
        alertas.append("📉 Caída fuerte superior al 5%")

    elif cambio_24h <= -3:
        alertas.append("📉 Caída importante superior al 3%")

    if rsi <= 30:
        alertas.append("🟢 RSI en zona de sobreventa")

    elif rsi <= 35:
        alertas.append("🟡 RSI acercándose a sobreventa")

    if cambio_24h <= -3 and rsi <= 30:
        return (
            "🚨 ALERTA FUERTE DE BTC\n\n"
            + "\n".join(alertas)
            + "\n\n"
            "🎯 Posible zona de interés.\n"
            "⚠️ No es una señal garantizada de compra."
        )

    if alertas:
        return (
            "⚠️ ALERTA BTC\n\n"
            + "\n".join(alertas)
            + "\n\n"
            "👀 Conviene vigilar el mercado."
        )

    return (
        "🟢 BTC — SIN ALERTA\n\n"
        "No se detectan condiciones fuertes "
        "de caída o sobreventa en este momento."
    )


if __name__ == "__main__":

    precio, cambio_24h = obtener_datos_bitcoin()

    precios = obtener_precios()

    rsi = calcular_rsi(precios)

    resultado = analizar(
        precio,
        cambio_24h,
        rsi
    )

    mensaje = (
        "🤖 BTC ALERT BOT\n\n"
        f"₿ Bitcoin: ${precio:,.2f}\n"
        f"📉 Cambio 24h: {cambio_24h:.2f}%\n"
        f"📊 RSI(14): {rsi:.2f}\n\n"
        f"{resultado}\n\n"
        "✅ Análisis completado correctamente."
    )

    enviar_telegram(mensaje)