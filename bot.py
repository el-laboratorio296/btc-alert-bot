import os
import json
import math
import time
import requests


# ============================================================
# CONFIGURACIÓN
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

STATE_FILE = "bot_state.json"

COINGECKO_MARKETS_URL = (
    "https://api.coingecko.com/api/v3/coins/markets"
)

COINGECKO_CHART_URL = (
    "https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
)

HEADERS = {
    "User-Agent": "BTC-Alert-Laboratorio/1.0"
}


# ============================================================
# CRIPTOMONEDAS PRINCIPALES
# ============================================================

MONEDAS_PRINCIPALES = {
    "bitcoin": "BTC",
    "ethereum": "ETH",
    "solana": "SOL",
    "binancecoin": "BNB",
    "ripple": "XRP",
}


# ============================================================
# FUNCIONES GENERALES
# ============================================================

def solicitar(url, params=None, intentos=3):
    """
    Realiza una petición HTTP con algunos reintentos.
    """

    for intento in range(intentos):

        try:
            respuesta = requests.get(
                url,
                params=params,
                headers=HEADERS,
                timeout=20
            )

            respuesta.raise_for_status()

            return respuesta.json()

        except requests.RequestException as error:

            print(
                f"Error HTTP (intento "
                f"{intento + 1}/{intentos}): {error}"
            )

            if intento < intentos - 1:
                time.sleep(3)

    return None


# ============================================================
# TELEGRAM
# ============================================================

def enviar_telegram(mensaje):

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:

        print("Faltan las credenciales de Telegram.")

        return False

    url = (
        f"https://api.telegram.org/bot"
        f"{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    datos = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje
    }

    try:

        respuesta = requests.post(
            url,
            data=datos,
            timeout=20
        )

        respuesta.raise_for_status()

        print("Mensaje enviado a Telegram.")

        return True

    except requests.RequestException as error:

        print(f"Error enviando Telegram: {error}")

        return False


# ============================================================
# ESTADO DEL BOT
# ============================================================

def cargar_estado():

    if not os.path.exists(STATE_FILE):

        return {
            "ultima_alerta": {}
        }

    try:

        with open(
            STATE_FILE,
            "r",
            encoding="utf-8"
        ) as archivo:

            estado = json.load(archivo)

            if "ultima_alerta" not in estado:
                estado["ultima_alerta"] = {}

            return estado

    except Exception as error:

        print(f"Error leyendo estado: {error}")

        return {
            "ultima_alerta": {}
        }


def guardar_estado(estado):

    try:

        with open(
            STATE_FILE,
            "w",
            encoding="utf-8"
        ) as archivo:

            json.dump(
                estado,
                archivo,
                indent=2,
                ensure_ascii=False
            )

        print("Estado guardado correctamente.")

    except Exception as error:

        print(f"Error guardando estado: {error}")


# ============================================================
# OBTENER MERCADO
# ============================================================

def obtener_mercado():

    parametros = {
        "vs_currency": "usd",
        "order": "volume_desc",
        "per_page": 100,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "24h"
    }

    datos = solicitar(
        COINGECKO_MARKETS_URL,
        parametros
    )

    if not datos:
        raise Exception(
            "No fue posible obtener datos del mercado."
        )

    return datos


# ============================================================
# BUSCAR SEXTA CRIPTOMONEDA
# ============================================================

def seleccionar_moneda_dinamica(mercado):

    ids_principales = set(
        MONEDAS_PRINCIPALES.keys()
    )

    monedas_estables = {
        "usdt",
        "usdc",
        "dai",
        "usde",
        "fdusd",
        "tusd",
        "usds",
        "usdd",
        "pyusd"
    }

    candidatos = []

    for moneda in mercado:

        coin_id = moneda.get("id")
        simbolo = moneda.get(
            "symbol",
            ""
        ).lower()

        if coin_id in ids_principales:
            continue

        if simbolo in monedas_estables:
            continue

        precio = moneda.get("current_price")

        volumen = moneda.get(
            "total_volume"
        ) or 0

        cambio = moneda.get(
            "price_change_percentage_24h"
        )

        market_cap = moneda.get(
            "market_cap"
        ) or 0

        if not precio or not cambio:
            continue

        # Buscamos monedas con movimiento real
        # y suficiente liquidez.

        if volumen < 30_000_000:
            continue

        # Primera prioridad:
        # mucho volumen + movimiento importante.

        movimiento = abs(cambio)

        if movimiento < 3:
            continue

        # Preferimos monedas con mayor capitalización
        # para evitar señales excesivamente especulativas.

        if market_cap < 300_000_000:
            continue

        puntuacion = (
            movimiento * 3
            + min(volumen / 100_000_000, 5)
            + min(market_cap / 1_000_000_000, 3)
        )

        candidatos.append(
            (
                puntuacion,
                moneda
            )
        )

    if not candidatos:

        print(
            "No se encontró una sexta moneda adecuada."
        )

        return None

    candidatos.sort(
        key=lambda x: x[0],
        reverse=True
    )

    seleccionada = candidatos[0][1]

    print(
        "Sexta moneda seleccionada:",
        seleccionada.get("symbol", "").upper(),
        seleccionada.get("name")
    )

    return seleccionada


# ============================================================
# HISTÓRICO DE PRECIOS
# ============================================================

def obtener_historico(coin_id):

    url = COINGECKO_CHART_URL.format(
        coin_id=coin_id
    )

    parametros = {
        "vs_currency": "usd",
        "days": 2,
        "interval": "hourly"
    }

    datos = solicitar(
        url,
        parametros
    )

    if not datos:

        print(
            f"No se pudo obtener histórico de {coin_id}"
        )

        return [], []

    precios = [
        item[1]
        for item in datos.get(
            "prices",
            []
        )
    ]

    volumenes = [
        item[1]
        for item in datos.get(
            "total_volumes",
            []
        )
    ]

    return precios, volumenes


# ============================================================
# RSI
# ============================================================

def calcular_rsi(precios, periodo=14):

    if len(precios) < periodo + 1:

        return None

    cambios = []

    for i in range(
        1,
        len(precios)
    ):

        cambios.append(
            precios[i] - precios[i - 1]
        )

    ganancias = [
        max(cambio, 0)
        for cambio in cambios
    ]

    perdidas = [
        abs(min(cambio, 0))
        for cambio in cambios
    ]

    promedio_ganancia = (
        sum(ganancias[:periodo])
        / periodo
    )

    promedio_perdida = (
        sum(perdidas[:periodo])
        / periodo
    )

    for i in range(
        periodo,
        len(cambios)
    ):

        promedio_ganancia = (
            (
                promedio_ganancia
                * (periodo - 1)
            )
            + ganancias[i]
        ) / periodo

        promedio_perdida = (
            (
                promedio_perdida
                * (periodo - 1)
            )
            + perdidas[i]
        ) / periodo

    if promedio_perdida == 0:

        return 100.0

    rs = (
        promedio_ganancia
        / promedio_perdida
    )

    rsi = 100 - (
        100 / (1 + rs)
    )

    return rsi


# ============================================================
# ANÁLISIS DE VOLUMEN
# ============================================================

def calcular_ratio_volumen(volumenes):

    if len(volumenes) < 10:

        return None

    volumen_actual = volumenes[-1]

    anteriores = volumenes[-25:-1]

    if not anteriores:

        return None

    promedio = (
        sum(anteriores)
        / len(anteriores)
    )

    if promedio <= 0:

        return None

    return volumen_actual / promedio


# ============================================================
# ANÁLISIS TÉCNICO
# ============================================================

def analizar_moneda(
    coin_id,
    simbolo,
    nombre,
    precio,
    cambio_24h,
    volumen_24h,
    precios,
    volumenes
):

    if not precios:

        return None

    rsi = calcular_rsi(precios)

    ratio_volumen = calcular_ratio_volumen(
        volumenes
    )

    ultimos_24 = precios[-24:]

    minimo_24h = min(ultimos_24)

    maximo_24h = max(ultimos_24)

    promedio_24h = (
        sum(ultimos_24)
        / len(ultimos_24)
    )

    distancia_soporte = (
        (precio - minimo_24h)
        / precio
    )

    cerca_soporte = (
        distancia_soporte <= 0.02
    )

    cerca_resistencia = (
        (maximo_24h - precio)
        / precio
        <= 0.01
    )

    volumen_fuerte = (
        ratio_volumen is not None
        and ratio_volumen >= 1.5
    )

    volumen_muy_fuerte = (
        ratio_volumen is not None
        and ratio_volumen >= 2.0
    )

    # ========================================================
    # ESCENARIO DE CAÍDA / POSIBLE RECUPERACIÓN
    # ========================================================

    puntuacion_caida = 0

    razones_caida = []

    if cambio_24h <= -5:

        puntuacion_caida += 35

        razones_caida.append(
            "caída 24h fuerte"
        )

    elif cambio_24h <= -3:

        puntuacion_caida += 25

        razones_caida.append(
            "caída 24h relevante"
        )

    if rsi is not None:

        if rsi <= 30:

            puntuacion_caida += 30

            razones_caida.append(
                "RSI en sobreventa"
            )

        elif rsi <= 35:

            puntuacion_caida += 20

            razones_caida.append(
                "RSI bajo"
            )

    if volumen_muy_fuerte:

        puntuacion_caida += 25

        razones_caida.append(
            "volumen muy alto"
        )

    elif volumen_fuerte:

        puntuacion_caida += 15

        razones_caida.append(
            "volumen alto"
        )

    if cerca_soporte:

        puntuacion_caida += 15

        razones_caida.append(
            "cerca del soporte"
        )

    # ========================================================
    # ESCENARIO DE MOMENTUM ALCISTA
    # ========================================================

    puntuacion_momentum = 0

    razones_momentum = []

    if cambio_24h >= 7:

        puntuacion_momentum += 35

        razones_momentum.append(
            "subida 24h muy fuerte"
        )

    elif cambio_24h >= 5:

        puntuacion_momentum += 30

        razones_momentum.append(
            "subida 24h fuerte"
        )

    elif cambio_24h >= 3:

        puntuacion_momentum += 15

        razones_momentum.append(
            "movimiento alcista"
        )

    if volumen_muy_fuerte:

        puntuacion_momentum += 25

        razones_momentum.append(
            "volumen muy alto"
        )

    elif volumen_fuerte:

        puntuacion_momentum += 15

        razones_momentum.append(
            "volumen alto"
        )

    if rsi is not None:

        if 50 <= rsi <= 70:

            puntuacion_momentum += 20

            razones_momentum.append(
                "RSI saludable"
            )

        elif 45 <= rsi < 50:

            puntuacion_momentum += 10

            razones_momentum.append(
                "RSI recuperándose"
            )

    if precio > promedio_24h:

        puntuacion_momentum += 10

        razones_momentum.append(
            "precio sobre promedio 24h"
        )

    if cerca_resistencia:

        puntuacion_momentum += 10

        razones_momentum.append(
            "cerca de resistencia"
        )

    # ========================================================
    # DECIDIR TIPO DE ALERTA
    # ========================================================

    tipo_alerta = None

    puntuacion = 0

    razones = []

    if (
        puntuacion_caida >= 60
        and puntuacion_caida
        >= puntuacion_momentum
    ):

        tipo_alerta = "RECUPERACION"

        puntuacion = puntuacion_caida

        razones = razones_caida

    elif puntuacion_momentum >= 60:

        tipo_alerta = "MOMENTUM"

        puntuacion = puntuacion_momentum

        razones = razones_momentum

    elif puntuacion_caida >= 50:

        tipo_alerta = "ATENCION"

        puntuacion = puntuacion_caida

        razones = razones_caida

    if tipo_alerta is None:

        return {
            "coin_id": coin_id,
            "simbolo": simbolo,
            "nombre": nombre,
            "alerta": None,
            "puntuacion": 0,
            "precio": precio,
            "cambio_24h": cambio_24h,
            "rsi": rsi,
            "ratio_volumen": ratio_volumen,
            "soporte": minimo_24h,
            "resistencia": maximo_24h,
            "razones": []
        }

    if puntuacion >= 75:

        nivel = "FUERTE"

    elif puntuacion >= 60:

        nivel = "MODERADA"

    else:

        nivel = "ATENCION"

    return {
        "coin_id": coin_id,
        "simbolo": simbolo,
        "nombre": nombre,
        "alerta": tipo_alerta,
        "nivel": nivel,
        "puntuacion": puntuacion,
        "precio": precio,
        "cambio_24h": cambio_24h,
        "rsi": rsi,
        "ratio_volumen": ratio_volumen,
        "soporte": minimo_24h,
        "resistencia": maximo_24h,
        "razones": razones
    }


# ============================================================
# FORMATEAR PRECIO
# ============================================================

def formato_precio(precio):

    if precio >= 1000:

        return f"${precio:,.0f}"

    if precio >= 1:

        return f"${precio:,.2f}"

    return f"${precio:,.6f}"


# ============================================================
# CREAR MENSAJE DE ALERTA
# ============================================================

def crear_mensaje(alertas):

    if not alertas:

        return None

    mensaje = [
        "🚨 BTC ALERT BOT",
        "",
        f"🔎 {len(alertas)} alerta(s) nueva(s)",
        "📊 Análisis técnico automático",
        ""
    ]

    for alerta in alertas:

        simbolo = alerta["simbolo"]

        precio = formato_precio(
            alerta["precio"]
        )

        cambio = alerta["cambio_24h"]

        rsi = alerta["rsi"]

        ratio = alerta["ratio_volumen"]

        soporte = formato_precio(
            alerta["soporte"]
        )

        resistencia = formato_precio(
            alerta["resistencia"]
        )

        mensaje.append(
            f"━━━━━━━━━━━━━━"
        )

        if alerta["alerta"] == "RECUPERACION":

            mensaje.append(
                f"🟢 {simbolo} — "
                f"POSIBLE RECUPERACIÓN"
            )

        elif alerta["alerta"] == "MOMENTUM":

            mensaje.append(
                f"🚀 {simbolo} — "
                f"MOMENTUM ALCISTA"
            )

        else:

            mensaje.append(
                f"🟠 {simbolo} — "
                f"ATENCIÓN"
            )

        mensaje.append(
            f"Nivel: {alerta['nivel']}"
        )

        mensaje.append(
            f"Puntuación: "
            f"{alerta['puntuacion']}/100"
        )

        mensaje.append(
            f"💰 Precio: {precio}"
        )

        mensaje.append(
            f"📈 24h: {cambio:+.2f}%"
        )

        if rsi is not None:

            mensaje.append(
                f"📊 RSI(14): {rsi:.2f}"
            )

        else:

            mensaje.append(
                "📊 RSI(14): N/D"
            )

        if ratio is not None:

            mensaje.append(
                f"📦 Volumen: "
                f"{ratio:.2f}x promedio"
            )

        else:

            mensaje.append(
                "📦 Volumen: N/D"
            )

        mensaje.append(
            f"📍 Soporte 24h: {soporte}"
        )

        mensaje.append(
            f"📍 Resistencia 24h: "
            f"{resistencia}"
        )

        if alerta["razones"]:

            mensaje.append("")

            mensaje.append(
                "Motivos:"
            )

            for razon in alerta["razones"]:

                mensaje.append(
                    f"• {razon}"
                )

        mensaje.append("")

        mensaje.append(
            "⚠️ Señal técnica, "
            "no recomendación de compra."
        )

    return "\n".join(mensaje)


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

def main():

    print("===================================")
    print(" BTC ALERT BOT - LABORATORIO")
    print("===================================")

    estado = cargar_estado()

    mercado = obtener_mercado()

    # --------------------------------------------------------
    # Buscar sexta moneda dinámica
    # --------------------------------------------------------

    moneda_dinamica = seleccionar_moneda_dinamica(
        mercado
    )

    monedas_a_analizar = []

    # --------------------------------------------------------
    # Agregar las 5 principales
    # --------------------------------------------------------

    for coin_id, simbolo in MONEDAS_PRINCIPALES.items():

        monedas_a_analizar.append(
            (
                coin_id,
                simbolo
            )
        )

    # --------------------------------------------------------
    # Agregar sexta moneda
    # --------------------------------------------------------

    if moneda_dinamica:

        coin_id = moneda_dinamica.get("id")

        simbolo = moneda_dinamica.get(
            "symbol",
            ""
        ).upper()

        monedas_a_analizar.append(
            (
                coin_id,
                simbolo
            )
        )

    # --------------------------------------------------------
    # Diccionario de datos del mercado
    # --------------------------------------------------------

    mercado_por_id = {}

    for moneda in mercado:

        mercado_por_id[
            moneda.get("id")
        ] = moneda

    nuevas_alertas = []

    ultima_alerta = estado.get(
        "ultima_alerta",
        {}
    )

    # --------------------------------------------------------
    # Analizar cada moneda
    # --------------------------------------------------------

    for coin_id, simbolo in monedas_a_analizar:

        print("")
        print(
            f"Analizando {simbolo}..."
        )

        datos_mercado = mercado_por_id.get(
            coin_id
        )

        if not datos_mercado:

            print(
                f"No hay datos de mercado "
                f"para {simbolo}."
            )

            continue

        precio = datos_mercado.get(
            "current_price"
        )

        cambio_24h = (
            datos_mercado.get(
                "price_change_percentage_24h"
            )
            or 0
        )

        volumen_24h = (
            datos_mercado.get(
                "total_volume"
            )
            or 0
        )

        nombre = datos_mercado.get(
            "name",
            simbolo
        )

        precios, volumenes = obtener_historico(
            coin_id
        )

        resultado = analizar_moneda(
            coin_id,
            simbolo,
            nombre,
            precio,
            cambio_24h,
            volumen_24h,
            precios,
            volumenes
        )

        if not resultado:

            continue

        if resultado["alerta"] is None:

            print(
                f"{simbolo}: SIN ALERTA"
            )

            # Al desaparecer una alerta,
            # permitimos que vuelva a generarse
            # en el futuro.

            ultima_alerta[simbolo] = None

            continue

        tipo = resultado["alerta"]

        nivel = resultado["nivel"]

        identificador_alerta = (
            f"{tipo}_{nivel}"
        )

        anterior = ultima_alerta.get(
            simbolo
        )

        print(
            f"{simbolo}: "
            f"{tipo} "
            f"{nivel} "
            f"{resultado['puntuacion']}/100"
        )

        if identificador_alerta != anterior:

            nuevas_alertas.append(
                resultado
            )

            ultima_alerta[simbolo] = (
                identificador_alerta
            )

        else:

            print(
                f"{simbolo}: "
                "alerta ya enviada. "
                "No se repite."
            )

    # --------------------------------------------------------
    # Guardar estado
    # --------------------------------------------------------

    estado["ultima_alerta"] = ultima_alerta

    guardar_estado(
        estado
    )

    # --------------------------------------------------------
    # Telegram
    # --------------------------------------------------------

    if nuevas_alertas:

        mensaje = crear_mensaje(
            nuevas_alertas
        )

        enviar_telegram(
            mensaje
        )

        print("")
        print(
            f"Se enviaron "
            f"{len(nuevas_alertas)} alerta(s)."
        )

    else:

        print("")
        print(
            "No hay alertas nuevas."
        )

    print("")
    print(
        "Análisis completado correctamente."
    )


# ============================================================
# EJECUTAR
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except Exception as error:

        print(
            "ERROR CRÍTICO:"
        )

        print(error)

        raise