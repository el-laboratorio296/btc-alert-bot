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
    "User-Agent": "BTC-Alert-Laboratorio/3.0"
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
# STABLECOINS EXCLUIDAS
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
    "pyusd",
}


# ============================================================
# PETICIONES HTTP
# ============================================================

def solicitar(url, params=None, intentos=3):

    for intento in range(
        1,
        intentos + 1
    ):

        try:

            respuesta = requests.get(
                url,
                params=params,
                headers=HEADERS,
                timeout=30
            )

            # ------------------------------------------------
            # RATE LIMIT DE COINGECKO
            # ------------------------------------------------

            if respuesta.status_code == 429:

                print(
                    f"CoinGecko 429 "
                    f"(intento {intento}/{intentos})."
                )

                if intento < intentos:

                    espera = 10 * intento

                    print(
                        f"Esperando {espera} segundos..."
                    )

                    time.sleep(
                        espera
                    )

                    continue

            respuesta.raise_for_status()

            return respuesta.json()

        except requests.RequestException as error:

            print(
                f"Error HTTP "
                f"(intento {intento}/{intentos}): "
                f"{error}"
            )

            if intento < intentos:

                time.sleep(3)

    return None


# ============================================================
# TELEGRAM
# ============================================================

def enviar_telegram(mensaje):

    if not TELEGRAM_BOT_TOKEN:

        print(
            "Falta TELEGRAM_BOT_TOKEN."
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

    estado_defecto = {
        "ultima_alerta": {}
    }

    if not os.path.exists(
        STATE_FILE
    ):

        print(
            "No existe memoria anterior."
        )

        return estado_defecto

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

            return estado_defecto

        if not isinstance(
            estado.get(
                "ultima_alerta"
            ),
            dict
        ):

            estado[
                "ultima_alerta"
            ] = {}

        return estado

    except Exception as error:

        print(
            f"Error leyendo memoria: "
            f"{error}"
        )

        return estado_defecto


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

        print(
            "Memoria guardada correctamente."
        )

    except Exception as error:

        print(
            f"Error guardando memoria: "
            f"{error}"
        )


# ============================================================
# OBTENER MERCADO
# ============================================================

def obtener_mercado():

    parametros = {
        "vs_currency": "usd",
        "order": "volume_desc",
        "per_page": 100,
        "page": 1,
        "sparkline": "true",
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
# SELECCIÓN DE LA SEXTA MONEDA
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

        cambio_1h = moneda.get(
            "price_change_percentage_1h_in_currency"
        )

        cambio_24h = moneda.get(
            "price_change_percentage_24h_in_currency"
        )

        cambio_7d = moneda.get(
            "price_change_percentage_7d_in_currency"
        )

        # ----------------------------------------------------
        # EXCLUSIONES
        # ----------------------------------------------------

        if coin_id in ids_fijos:

            continue

        if simbolo in STABLECOINS:

            continue

        if not precio:

            continue

        if cambio_24h is None:

            continue

        # Capitalización mínima

        if market_cap < 500_000_000:

            continue

        # Volumen mínimo

        if volumen < 50_000_000:

            continue

        # Movimiento mínimo

        if abs(cambio_24h) < 3:

            continue

        # ----------------------------------------------------
        # RSI DE LA CANDIDATA
        # ----------------------------------------------------

        precios = (
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

        rsi = calcular_rsi(
            precios
        )

        # ----------------------------------------------------
        # LIQUIDEZ
        # ----------------------------------------------------

        if market_cap > 0:

            liquidez = (
                volumen
                / market_cap
            )

        else:

            liquidez = 0

        # ----------------------------------------------------
        # PUNTUACIÓN
        # ----------------------------------------------------

        puntuacion = 0

        # Movimiento

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

        # Movimiento de 1 hora

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

        # Tendencia 7 días

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

        # RSI

        if rsi is not None:

            if 45 <= rsi <= 70:

                puntuacion += 12

            elif rsi < 35:

                puntuacion += 8

            elif rsi > 80:

                puntuacion -= 12

        # Pump extremo perdiendo fuerza

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
                moneda
            )
        )

    # --------------------------------------------------------
    # SIN CANDIDATOS
    # --------------------------------------------------------

    if not candidatos:

        print(
            "No se encontró "
            "una sexta moneda adecuada."
        )

        return None

    # --------------------------------------------------------
    # ORDENAR
    # --------------------------------------------------------

    candidatos.sort(
        key=lambda x: x[0],
        reverse=True
    )

    puntuacion = candidatos[0][0]

    seleccionada = candidatos[0][1]

    simbolo = str(
        seleccionada.get(
            "symbol",
            ""
        )
    ).upper()

    nombre = seleccionada.get(
        "name",
        ""
    )

    print(
        "Sexta moneda seleccionada: "
        f"{simbolo} {nombre}"
    )

    print(
        f"Score candidata: "
        f"{puntuacion:.1f}"
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

    precios = (
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
        precios
    )

    # --------------------------------------------------------
    # RANGO DE LAS ÚLTIMAS 24 OBSERVACIONES
    # --------------------------------------------------------

    if len(precios) >= 24:

        ultimos = precios[-24:]

    elif precios:

        ultimos = precios

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
    # DISTANCIA DEL SOPORTE
    # --------------------------------------------------------

    if precio > 0:

        distancia_soporte = (
            precio - soporte
        ) / precio

    else:

        distancia_soporte = 1

    cerca_soporte = (
        distancia_soporte <= 0.02
    )

    # --------------------------------------------------------
    # DISTANCIA DE RESISTENCIA
    # --------------------------------------------------------

    if precio > 0:

        distancia_resistencia = (
            resistencia - precio
        ) / precio

    else:

        distancia_resistencia = 1

    cerca_resistencia = (
        distancia_resistencia <= 0.01
    )

    # --------------------------------------------------------
    # LIQUIDEZ
    # --------------------------------------------------------

    if market_cap > 0:

        liquidez = (
            volumen
            / market_cap
        )

    else:

        liquidez = 0

    # ========================================================
    # ESCENARIO DE RECUPERACIÓN
    # ========================================================

    puntuacion_caida = 0

    razones_caida = []

    # Caída 24h

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

    # Rebote 1h

    if (
        cambio_1h is not None
        and cambio_1h > 0
    ):

        puntuacion_caida += 10

        razones_caida.append(
            "rebote positivo en 1h"
        )

    # Debilidad 7d

    if (
        cambio_7d is not None
        and cambio_7d < -8
    ):

        puntuacion_caida += 10

        razones_caida.append(
            "tendencia 7d debilitada"
        )

    # Liquidez

    if liquidez >= 0.10:

        puntuacion_caida += 5

        razones_caida.append(
            "alta rotación de volumen"
        )

    # ========================================================
    # MOMENTUM ALCISTA
    # ========================================================

    puntuacion_momentum = 0

    razones_momentum = []

    # Movimiento 24h

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

            razones_momentum.append(
                "pérdida de fuerza en 1h"
            )

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

    if liquidez >= 0.10:

        puntuacion_momentum += 10

        razones_momentum.append(
            "buena rotación de mercado"
        )

    # ========================================================
    # DECISIÓN FINAL
    # ========================================================

    alerta = None

    puntuacion = 0

    razones = []

    # Recuperación

    if (
        puntuacion_caida >= 60
        and puntuacion_caida
        >= puntuacion_momentum
    ):

        alerta = "RECUPERACION"

        puntuacion = (
            puntuacion_caida
        )

        razones = (
            razones_caida
        )

    # Momentum

    elif puntuacion_momentum >= 60:

        alerta = "MOMENTUM"

        puntuacion = (
            puntuacion_momentum
        )

        razones = (
            razones_momentum
        )

    # Atención

    elif puntuacion_caida >= 50:

        alerta = "ATENCION"

        puntuacion = (
            puntuacion_caida
        )

        razones = (
            razones_caida
        )

    # --------------------------------------------------------
    # NIVEL
    # --------------------------------------------------------

    nivel = None

    if alerta:

        if puntuacion >= 75:

            nivel = "FUERTE"

        elif puntuacion >= 60:

            nivel = "MODERADA"

        else:

            nivel = "ATENCION"

    # --------------------------------------------------------
    # RESULTADO
    # --------------------------------------------------------

    return {

        "coin_id": coin_id,

        "simbolo": simbolo,

        "nombre": nombre,

        "alerta": alerta,

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

        "razones": razones,
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

        return (
            f"${precio:,.0f}"
        )

    if precio >= 1:

        return (
            f"${precio:,.2f}"
        )

    return (
        f"${precio:,.6f}"
    )


# ============================================================
# CREAR MENSAJE DE TELEGRAM
# ============================================================

def crear_mensaje(
    alertas
):

    if not alertas:

        return None

    lineas = [

        "🚨 BTC ALERT BOT",

        "🧪 LABORATORIO",

        "",

        f"🔎 {len(alertas)} "
        "alerta(s) nueva(s)",

        "📊 Scanner técnico automático",

        "",
    ]

    for alerta in alertas:

        tipo = alerta.get(
            "alerta"
        )

        # ----------------------------------------------------
        # TÍTULO
        # ----------------------------------------------------

        if tipo == "RECUPERACION":

            titulo = (
                "🟢 "
                f"{alerta['simbolo']} "
                "— POSIBLE RECUPERACIÓN"
            )

        elif tipo == "MOMENTUM":

            titulo = (
                "🚀 "
                f"{alerta['simbolo']} "
                "— MOMENTUM ALCISTA"
            )

        else:

            titulo = (
                "🟠 "
                f"{alerta['simbolo']} "
                "— ATENCIÓN"
            )

        lineas.append(
            "━━━━━━━━━━━━━━"
        )

        lineas.append(
            titulo
        )

        lineas.append(
            f"Nivel: "
            f"{alerta['nivel']}"
        )

        lineas.append(
            f"Puntuación: "
            f"{alerta['puntuacion']}/100"
        )

        lineas.append(
            "💰 Precio: "
            f"{formato_precio(alerta['precio'])}"
        )

        # ----------------------------------------------------
        # 1H
        # ----------------------------------------------------

        cambio_1h = alerta.get(
            "cambio_1h"
        )

        if cambio_1h is not None:

            lineas.append(
                f"⚡ 1h: "
                f"{cambio_1h:+.2f}%"
            )

        # ----------------------------------------------------
        # 24H
        # ----------------------------------------------------

        cambio_24h = alerta.get(
            "cambio_24h"
        )

        if cambio_24h is not None:

            lineas.append(
                f"📈 24h: "
                f"{cambio_24h:+.2f}%"
            )

        # ----------------------------------------------------
        # 7D
        # ----------------------------------------------------

        cambio_7d = alerta.get(
            "cambio_7d"
        )

        if cambio_7d is not None:

            lineas.append(
                f"📅 7d: "
                f"{cambio_7d:+.2f}%"
            )

        # ----------------------------------------------------
        # RSI
        # ----------------------------------------------------

        rsi = alerta.get(
            "rsi"
        )

        if rsi is not None:

            lineas.append(
                f"📊 RSI(14): "
                f"{rsi:.2f}"
            )

        # ----------------------------------------------------
        # VOLUMEN
        # ----------------------------------------------------

        volumen = alerta.get(
            "volumen"
        )

        if volumen:

            lineas.append(
                "📦 Volumen 24h: "
                f"${volumen:,.0f}"
            )

        # ----------------------------------------------------
        # SOPORTE
        # ----------------------------------------------------

        lineas.append(
            "📍 Soporte: "
            f"{formato_precio(alerta['soporte'])}"
        )

        # ----------------------------------------------------
        # RESISTENCIA
        # ----------------------------------------------------

        lineas.append(
            "📍 Resistencia: "
            f"{formato_precio(alerta['resistencia'])}"
        )

        # ----------------------------------------------------
        # RAZONES
        # ----------------------------------------------------

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
                    f"• {razon}"
                )

        lineas.append("")

        lineas.append(
            "⚠️ Señal técnica, "
            "no recomendación de compra."
        )

        lineas.append("")

    return "\n".join(
        lineas
    )


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

def main():

    print("")
    print(
        "========================================"
    )
    print(
        " BTC ALERT BOT - LABORATORIO"
    )
    print(
        "========================================"
    )
    print("")

    # --------------------------------------------------------
    # CARGAR MEMORIA
    # --------------------------------------------------------

    estado = cargar_estado()

    ultima_alerta = estado.get(
        "ultima_alerta",
        {}
    )

    if not isinstance(
        ultima_alerta,
        dict
    ):

        ultima_alerta = {}

    # --------------------------------------------------------
    # OBTENER MERCADO
    # --------------------------------------------------------

    mercado = obtener_mercado()

    # --------------------------------------------------------
    # SEXTA MONEDA DINÁMICA
    # --------------------------------------------------------

    moneda_dinamica = (
        seleccionar_moneda_dinamica(
            mercado
        )
    )

    # --------------------------------------------------------
    # CONSTRUIR LISTA
    # --------------------------------------------------------

    monedas_a_analizar = []

    for coin_id in MONEDAS_PRINCIPALES:

        encontrada = None

        for moneda in mercado:

            if moneda.get(
                "id"
            ) == coin_id:

                encontrada = moneda

                break

        if encontrada is not None:

            monedas_a_analizar.append(
                encontrada
            )

    # Añadir sexta moneda

    if moneda_dinamica is not None:

        monedas_a_analizar.append(
            moneda_dinamica
        )

    print("")

    print(
        "Monedas a analizar: "
        f"{len(monedas_a_analizar)}"
    )

    print("")

    # --------------------------------------------------------
    # ANALIZAR TODAS
    # --------------------------------------------------------

    alertas_nuevas = []

    for moneda in monedas_a_analizar:

        simbolo = str(
            moneda.get(
                "symbol",
                ""
            )
        ).upper()

        print(
            f"Analizando {simbolo}..."
        )

        try:

            resultado = analizar_moneda(
                moneda
            )

            # ----------------------------------------------
            # ERROR DE DATOS
            # ----------------------------------------------

            if resultado is None:

                print(
                    f"{simbolo}: "
                    "NO SE PUDO ANALIZAR"
                )

                continue

            tipo_alerta = resultado.get(
                "alerta"
            )

            # ----------------------------------------------
            # SIN ALERTA
            # ----------------------------------------------

            if tipo_alerta is None:

                ultima_alerta[
                    simbolo
                ] = None

                print(
                    f"{simbolo}: "
                    "SIN ALERTA"
                )

                continue

            # ----------------------------------------------
            # ALERTA NUEVA
            # ----------------------------------------------

            alerta_anterior = (
                ultima_alerta.get(
                    simbolo
                )
            )

            if tipo_alerta != alerta_anterior:

                alertas_nuevas.append(
                    resultado
                )

                ultima_alerta[
                    simbolo
                ] = tipo_alerta

                print(
                    f"{simbolo}: "
                    f"NUEVA ALERTA "
                    f"{tipo_alerta}"
                )

            else:

                print(
                    f"{simbolo}: "
                    f"ALERTA "
                    f"{tipo_alerta} "
                    "YA ENVIADA"
                )

        except Exception as error:

            print(
                f"{simbolo}: "
                f"ERROR durante análisis: "
                f"{error}"
            )

    # --------------------------------------------------------
    # GUARDAR MEMORIA
    # --------------------------------------------------------

    estado[
        "ultima_alerta"
    ] = ultima_alerta

    guardar_estado(
        estado
    )

    # --------------------------------------------------------
    # TELEGRAM
    # --------------------------------------------------------

    if alertas_nuevas:

        mensaje = crear_mensaje(
            alertas_nuevas
        )

        if mensaje:

            enviado = enviar_telegram(
                mensaje
            )

            if enviado:

                print(
                    f"Se enviaron "
                    f"{len(alertas_nuevas)} "
                    "alerta(s) nueva(s)."
                )

            else:

                print(
                    "No se pudo enviar "
                    "el mensaje a Telegram."
                )

    else:

        print("")

        print(
            "No hay alertas nuevas."
        )

    # --------------------------------------------------------
    # FINAL
    # --------------------------------------------------------

    print("")

    print(
        "Análisis completado correctamente."
    )

    print("")


# ============================================================
# EJECUTAR
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except Exception as error:

        print("")

        print(
            "ERROR CRÍTICO:"
        )

        print(
            str(error)
        )

        raise