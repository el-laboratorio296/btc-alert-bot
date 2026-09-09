import os
import json
import time
import requests


# ============================================================
# CONFIGURACIÓN
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

STATE_FILE = "bot_state.json"

MARKETS_URL = (
    "https://api.coingecko.com/api/v3/coins/markets"
)

HEADERS = {
    "User-Agent": "BTC-Alert-Laboratorio/2.0"
}


# ============================================================
# 5 CRIPTOMONEDAS PRINCIPALES
# ============================================================

MONEDAS_PRINCIPALES = {
    "bitcoin": "BTC",
    "ethereum": "ETH",
    "solana": "SOL",
    "binancecoin": "BNB",
    "ripple": "XRP",
}


# ============================================================
# STABLECOINS QUE NO QUEREMOS COMO SEXTA MONEDA
# ============================================================

STABLECOINS = {
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


# ============================================================
# PETICIONES HTTP
# ============================================================

def solicitar(url, params=None, intentos=3):

    for intento in range(intentos):

        try:

            respuesta = requests.get(
                url,
                params=params,
                headers=HEADERS,
                timeout=25
            )

            # Si CoinGecko nos limita temporalmente
            # esperamos antes de volver a intentar.

            if respuesta.status_code == 429:

                espera = 15 * (
                    intento + 1
                )

                print(
                    f"CoinGecko 429. "
                    f"Esperando {espera}s..."
                )

                if intento < intentos - 1:

                    time.sleep(espera)

                    continue

            respuesta.raise_for_status()

            return respuesta.json()

        except requests.RequestException as error:

            print(
                f"Error HTTP "
                f"(intento {intento + 1}/"
                f"{intentos}): {error}"
            )

            if intento < intentos - 1:

                time.sleep(3)

    return None


# ============================================================
# TELEGRAM
# ============================================================

def enviar_telegram(mensaje):

    if not TELEGRAM_BOT_TOKEN:

        print(
            "Faltan las credenciales de Telegram."
        )

        return False

    if not TELEGRAM_CHAT_ID:

        print(
            "Falta TELEGRAM_CHAT_ID."
        )

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

        print(
            "Mensaje enviado a Telegram."
        )

        return True

    except requests.RequestException as error:

        print(
            f"Error enviando Telegram: "
            f"{error}"
        )

        return False


# ============================================================
# MEMORIA
# ============================================================

def cargar_estado():

    estado_por_defecto = {
        "ultima_alerta": {}
    }

    if not os.path.exists(
        STATE_FILE
    ):

        print(
            "No existe memoria anterior."
        )

        return estado_por_defecto

    try:

        with open(
            STATE_FILE,
            "r",
            encoding="utf-8"
        ) as archivo:

            estado = json.load(
                archivo
            )

        if not isinstance(
            estado,
            dict
        ):

            return estado_por_defecto

        if not isinstance(
            estado.get(
                "ultima_alerta"
            ),
            dict
        ):

            print(
                "Formato antiguo "
                "de memoria detectado."
            )

            estado[
                "ultima_alerta"
            ] = {}

        return estado

    except Exception as error:

        print(
            f"Error leyendo memoria: "
            f"{error}"
        )

        return estado_por_defecto


def guardar_estado(estado):

    try:

        if not isinstance(
            estado.get(
                "ultima_alerta"
            ),
            dict
        ):

            estado[
                "ultima_alerta"
            ] = {}

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

        print(
            "Memoria guardada correctamente."
        )

    except Exception as error:

        print(
            f"Error guardando memoria: "
            f"{error}"
        )


# ============================================================
# OBTENER TODO EL MERCADO
# ============================================================

def obtener_mercado():

    parametros = {
        "vs_currency": "usd",
        "order": "volume_desc",
        "per_page": 100,
        "page": 1,

        # IMPORTANTE:
        # ahora obtenemos el histórico
        # dentro de la misma consulta.

        "sparkline": "true",

        # Varios períodos para analizar
        # tendencia y momentum.

        "price_change_percentage": (
            "1h,24h,7d"
        ),

        "locale": "en"
    }

    datos = solicitar(
        MARKETS_URL,
        parametros
    )

    if not datos:

        raise Exception(
            "No fue posible obtener "
            "el mercado."
        )

    print(
        f"Mercado recibido: "
        f"{len(datos)} monedas."
    )

    return datos


# ============================================================
# RSI
# ============================================================

def calcular_rsi(
    precios,
    periodo=14
):

    if not precios:

        return None

    if len(precios) < periodo + 1:

        return None

    cambios = []

    for i in range(
        1,
        len(precios)
    ):

        cambios.append(
            precios[i]
            - precios[i - 1]
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
        sum(
            ganancias[:periodo]
        )
        / periodo
    )

    promedio_perdida = (
        sum(
            perdidas[:periodo]
        )
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

    return (
        100
        - (
            100
            / (1 + rs)
        )
    )


# ============================================================
# LIQUIDEZ
# ============================================================

def calcular_liquidez(
    volumen,
    market_cap
):

    if not volumen:
        return None

    if not market_cap:
        return None

    return (
        volumen
        / market_cap
    )


# ============================================================
# SELECCIÓN INTELIGENTE DE LA SEXTA MONEDA
# ============================================================

def seleccionar_moneda_dinamica(
    mercado
):

    candidatos = []

    ids_fijos = set(
        MONEDAS_PRINCIPALES.keys()
    )

    for moneda in mercado:

        coin_id = moneda.get(
            "id"
        )

        simbolo = str(
            moneda.get(
                "symbol",
                ""
            )
        ).lower()

        precio = moneda.get(
            "current_price"
        )

        market_cap = (
            moneda.get(
                "market_cap"
            )
            or 0
        )

        volumen = (
            moneda.get(
                "total_volume"
            )
            or 0
        )

        cambio_1h = (
            moneda.get(
                "price_change_percentage_1h_in_currency"
            )
        )

        cambio_24h = (
            moneda.get(
                "price_change_percentage_24h_in_currency"
            )
        )

        cambio_7d = (
            moneda.get(
                "price_change_percentage_7d_in_currency"
            )
        )

        sparkline = (
            moneda
            .get(
                "sparkline_in_7d",
                {}
            )
            .get(
                "price",
                []
            )
        )

        # ----------------------------------------------------
        # FILTROS
        # ----------------------------------------------------

        if coin_id in ids_fijos:

            continue

        if simbolo in STABLECOINS:

            continue

        if not precio:

            continue

        if cambio_24h is None:

            continue

        # Evitamos monedas excesivamente pequeñas.

        if market_cap < 500_000_000:

            continue

        # Necesitamos liquidez real.

        if volumen < 50_000_000:

            continue

        # Queremos movimiento.

        if abs(cambio_24h) < 3:

            continue

        rsi = calcular_rsi(
            sparkline
        )

        liquidez = calcular_liquidez(
            volumen,
            market_cap
        )

        if liquidez is None:

            liquidez = 0

        # ----------------------------------------------------
        # PUNTUACIÓN
        # ----------------------------------------------------

        puntuacion = 0

        # Movimiento principal

        puntuacion += (
            min(
                abs(cambio_24h),
                15
            )
            * 2.5
        )

        # Liquidez

        puntuacion += min(
            liquidez * 100,
            12
        )

        # Momentum de 1 hora

        if cambio_1h is not None:

            puntuacion += (
                max(
                    min(
                        cambio_1h,
                        3
                    ),
                    -3
                )
                * 2
            )

        # Tendencia de 7 días

        if cambio_7d is not None:

            puntuacion += (
                max(
                    min(
                        cambio_7d,
                        15
                    ),
                    -15
                )
                * 0.4
            )

        # RSI saludable

        if rsi is not None:

            if 45 <= rsi <= 70:

                puntuacion += 12

            elif rsi < 35:

                # También puede ser interesante
                # si está en sobreventa.

                puntuacion += 8

            elif rsi > 80:

                # Penalizamos sobrecompra extrema.

                puntuacion -= 12

        # Penalizamos pumps demasiado extremos
        # que comienzan a perder fuerza.

        if (
            cambio_24h > 20
            and (
                cambio_1h is None
                or cambio_1h < 0
            )
        ):

            puntuacion -= 10

        candidatos.append(
            (
                puntuacion,
                moneda,
                rsi
            )
        )

    if not candidatos:

        print(
            "No se encontró "
            "una sexta moneda adecuada."
        )

        return None

    candidatos.sort(
        key=lambda x: x[0],
        reverse=True
    )

    puntuacion, seleccionada, rsi = (
        candidatos[0]
    )

    print(
        "Sexta moneda seleccionada: "
        f"{str(seleccionada.get('symbol', '')).upper()} "
        f"{seleccionada.get('name', '')} "
        f"(score {puntuacion:.1f})"
    )

    if rsi is not None:

        print(
            f"RSI candidata: {rsi:.2f}"
        )

    return seleccionada


# ============================================================
# ANALIZAR MONEDA
# ============================================================

def analizar_moneda(
    moneda
):

    coin_id = moneda.get(
        "id"
    )

    simbolo = str(
        moneda.get(
            "symbol",
            ""
        )
    ).upper()

    nombre = moneda.get(
        "name",
        simbolo
    )

    precio = moneda.get(
        "current_price"
    )

    cambio_1h = moneda.get(
        "price_change_percentage_1h_in_currency"
    )

    cambio_24h = moneda.get(
        "price_change_percentage_24h_in_currency"
    )

    cambio_7d = moneda.get(
        "price_change_percentage_7d_in_currency"
    )

    volumen = (
        moneda.get(
            "total_volume"
        )
        or 0
    )

    market_cap = (
        moneda.get(
            "market_cap"
        )
        or 0
    )

    high_24h = moneda.get(
        "high_24h"
    )

    low_24h = moneda.get(
        "low_24h"
    )

    sparkline = (
        moneda
        .get(
            "sparkline_in_7d",
            {}
        )
        .get(
            "price",
            []
        )
    )

    if precio is None:

        return None

    if cambio_24h is None:

        return None

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    rsi = calcular_rsi(
        sparkline
    )

    # --------------------------------------------------------
    # RANGO RECIENTE
    # --------------------------------------------------------

    if len(sparkline) >= 24:

        ultimos = sparkline[-24:]

    elif sparkline:

        ultimos = sparkline

    else:

        ultimos = [
            precio
        ]

    soporte = min(
        ultimos
    )

    resistencia = max(
        ultimos
    )

    promedio = (
        sum(ultimos)
        / len(ultimos)
    )

    # --------------------------------------------------------
    # SOPORTE
    # --------------------------------------------------------

    cerca_soporte = False

    if precio > 0:

        distancia = (
            precio - soporte
        ) / precio

        cerca_soporte = (
            distancia <= 0.02
        )

    # --------------------------------------------------------
    # RESISTENCIA
    # --------------------------------------------------------

    cerca_resistencia = False

    if precio > 0:

        distancia = (
            resistencia - precio
        ) / precio

        cerca_resistencia = (
            distancia <= 0.01
        )

    # --------------------------------------------------------
    # LIQUIDEZ
    # --------------------------------------------------------

    liquidez = calcular_liquidez(
        volumen,
        market_cap
    )

    # ========================================================
    # ESCENARIO DE RECUPERACIÓN
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

    # RSI

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

    # Soporte

    if cerca_soporte:

        puntuacion_caida += 15

        razones_caida.append(
            "precio cerca del soporte"
        )

    # Rebote de 1h

    if (
        cambio_1h is not None
        and cambio_1h > 0
    ):

        puntuacion_caida += 10

        razones_caida.append(
            "rebote positivo en 1h"
        )

    # Debilidad de 7 días

    if (
        cambio_7d is not None
        and cambio_7d < -8
    ):

        puntuacion_caida += 10

        razones_caida.append(
            "tendencia 7d debilitada"
        )

    # Alta rotación

    if (
        liquidez is not None
        and liquidez >= 0.10
    ):

        puntuacion_caida += 5

        razones_caida.append(
            "alta rotación de volumen"
        )

    # ========================================================
    # MOMENTUM ALCISTA
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

    # Movimiento 1h

    if cambio_1h is not None:

        if cambio_1h >= 1:

            puntuacion_momentum += 15

            razones_momentum.append(
                "impulso positivo en 1h"
            )

        elif cambio_1h <= -2:

            puntuacion_momentum -= 10

    # RSI

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

        elif rsi > 75:

            puntuacion_momentum -= 10

            razones_momentum.append(
                "RSI elevado"
            )

    # Precio sobre promedio

    if precio > promedio:

        puntuacion_momentum += 10

        razones_momentum.append(
            "precio sobre promedio reciente"
        )

    # Resistencia

    if cerca_resistencia:

        puntuacion_momentum += 5

        razones_momentum.append(
            "cerca de resistencia"
        )

    # Liquidez

    if (
        liquidez is not None
        and liquidez >= 0.10
    ):

        puntuacion_momentum += 10

        razones_momentum.append(
            "volumen/capitalización elevado"
        )

    # ========================================================
    # DECISIÓN
    # ========================================================

    tipo_alerta = None

    puntuacion = 0

    razones = []

    if (
        puntuacion_caida >= 60
        and puntuacion_caida
        >= puntuacion_momentum
    ):

        tipo_alerta = (
            "RECUPERACION"
        )

        puntuacion = (
            puntuacion_caida
        )

        razones = (
            razones_caida
        )

    elif puntuacion_momentum >= 60:

        tipo_alerta = (
            "MOMENTUM"
        )

        puntuacion = (
            puntuacion_momentum
        )

        razones = (
            razones_momentum
        )

    elif puntuacion_caida >= 50:

        tipo_alerta = (
            "ATENCION"
        )

        puntuacion = (
            puntuacion_caida
        )

        razones = (
            razones_caida
        )

    # ========================================================
    # NIVEL
    # ========================================================

    nivel = None

    if tipo_alerta:

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
        "cambio_1h": cambio_1h,
        "cambio_24h": cambio_24h,
        "cambio_7d": cambio_7d,
        "rsi": rsi,
        "volumen": volumen,
        "market_cap": market_cap,
        "liquidez": liquidez,
        "soporte": soporte,
        "resistencia": resistencia,
        "low24": low_24h,
        "high24": high_24h,
        "razones": razones
    }


# ============================================================
# FORMATO DE PRECIO
# ============================================================

def formato_precio(
    precio
):

    if precio is None:

        return "N/D"

    if precio >= 1000:

        return f"${precio:,.0f}"

    if precio >= 1:

        return f"${precio:,.2f}"

    return f"${precio:,.6f}"


# ============================================================
# CREAR MENSAJE TELEGRAM
# ============================================================

def crear_mensaje(alertas):

    if not alertas:
        return None

    lineas = [
        "🚨 BTC ALERT BOT",
        "",
        "🔎 {} alerta(s) nueva(s)".format(
            len(alertas)
        ),
        "📊 Scanner técnico automático",
        ""
    ]

    for alerta in alertas:

        tipo = alerta.get("alerta")

        if tipo == "RECUPERACION":

            titulo = (
                "🟢 {} — POSIBLE RECUPERACIÓN"
                .format(alerta["simbolo"])
            )

        elif tipo == "MOMENTUM":

            titulo = (
                "🚀 {} — MOMENTUM ALCISTA"
                .format(alerta["simbolo"])
            )

        else:

            titulo = (
                "🟠 {} — ATENCIÓN"
                .format(alerta["simbolo"])
            )

        lineas.append(
            "━━━━━━━━━━━━━━"
        )

        lineas.append(titulo)

        lineas.append(
            "Nivel: {}".format(
                alerta["nivel"]
            )
        )

        lineas.append(
            "Puntuación: {}/100".format(
                alerta["puntuacion"]
            )
        )

        lineas.append(
            "💰 Precio: {}".format(
                formato_precio(
                    alerta["precio"]
                )
            )
        )

        cambio_1h = alerta.get(
            "cambio_1h"
        )

        if cambio_1h is not None:

            lineas.append(
                "⚡ 1h: {:+.2f}%".format(
                    cambio_1h
                )
            )

        cambio_24h = alerta.get(
            "cambio_24h"
        )

        if cambio_24h is not None:

            lineas.append(
                "📈 24h: {:+.2f}%".format(
                    cambio_24h
                )
            )

        cambio_7d = alerta.get(
            "cambio_7d"
        )

        if cambio_7d is not None:

            lineas.append(
                "📅 7d: {:+.2f}%".format(
                    cambio_7d
                )
            )

        rsi = alerta.get(
            "rsi"
        )

        if rsi is not None:

            lineas.append(
                "📊 RSI(14): {:.2f}".format(
                    rsi
                )
            )

        volumen = alerta.get(
            "volumen"
        )

        if volumen:

            lineas.append(
                "📦 Volumen 24h: ${:,.0f}".format(
                    volumen
                )
            )

        liquidez = alerta.get(
            "liquidez"
        )

        if liquidez is not None:

            lineas.append(
                "💧 Volumen/Cap: {:.1f}%".format(
                    liquidez * 100
                )
            )

        lineas.append(
            "📍 Soporte: {}".format(
                formato_precio(
                    alerta["soporte"]
                )
            )
        )

        lineas.append(
            "📍 Resistencia: {}".format(
                formato_precio(
                    alerta["resistencia"]
                )
            )
        )

        razones = alerta.get(
            "razones",
            []
        )

        if razones:

            lineas.append("")

            lineas.append(
                "Motivos:"
            )

            for razon in razones:

                lineas.append(
                    "• {}".format(
                        razon
                    )
                )

        lineas.append("")

        lineas.append(
            "⚠️ Señal técnica, "
            "no recomendación de compra."
        )

    return "\n".join(lineas)

# ============================================================
# EJECUTAR PROGRAMA
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except Exception as error:

        print("")
        print("ERROR CRÍTICO:")
        print(str(error))

        raise