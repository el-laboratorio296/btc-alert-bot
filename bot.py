import os
import json
import time
import math
import statistics
import requests


# ============================================================
# EL LABORATORIO - CRYPTO ALERT BOT
# VERSIÓN 4.0
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

STATE_FILE = "bot_state.json"

MARKETS_URL = (
    "https://api.coingecko.com/api/v3/coins/markets"
)

HEADERS = {
    "User-Agent": "BTC-Alert-Laboratorio/4.0"
}


# ============================================================
# CONFIGURACIÓN DEL SISTEMA
# ============================================================

MONEDAS_PRINCIPALES = {
    "bitcoin": "BTC",
    "ethereum": "ETH",
    "solana": "SOL",
    "binancecoin": "BNB",
    "ripple": "XRP",
}


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

    for intento in range(1, intentos + 1):

        try:

            respuesta = requests.get(
                url,
                params=params,
                headers=HEADERS,
                timeout=30
            )

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

                    time.sleep(espera)

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

        print("Falta TELEGRAM_BOT_TOKEN.")

        return False

    if not TELEGRAM_CHAT_ID:

        print("Falta TELEGRAM_CHAT_ID.")

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

        print(
            f"Error enviando Telegram: {error}"
        )

        return False


# ============================================================
# MEMORIA
# ============================================================

def cargar_estado():

    estado_defecto = {
        "ultima_alerta": {}
    }

    if not os.path.exists(STATE_FILE):

        print("No existe memoria anterior.")

        return estado_defecto

    try:

        with open(
            STATE_FILE,
            "r",
            encoding="utf-8"
        ) as archivo:

            estado = json.load(archivo)

        if not isinstance(estado, dict):

            return estado_defecto

        if not isinstance(
            estado.get("ultima_alerta"),
            dict
        ):

            estado["ultima_alerta"] = {}

        return estado

    except Exception as error:

        print(
            f"Error leyendo memoria: {error}"
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

        print("Memoria guardada correctamente.")

    except Exception as error:

        print(
            f"Error guardando memoria: {error}"
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
            "No fue posible obtener el mercado."
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

    for i in range(1, len(precios)):

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

    for i in range(periodo, len(cambios)):

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
# UTILIDADES MATEMÁTICAS
# ============================================================

def limitar(valor, minimo, maximo):

    return max(
        minimo,
        min(valor, maximo)
    )


def porcentaje(valor):

    if valor is None:

        return "N/D"

    return f"{valor:+.2f}%"


def dinero(valor):

    if valor is None:

        return "N/D"

    if valor >= 1000:

        return f"${valor:,.2f}"

    if valor >= 1:

        return f"${valor:,.4f}"

    if valor >= 0.01:

        return f"${valor:,.6f}"

    return f"${valor:.8f}"


# ============================================================
# VOLATILIDAD
# ============================================================

def calcular_volatilidad(precios):

    if not precios or len(precios) < 10:

        return None

    retornos = []

    for i in range(1, len(precios)):

        anterior = precios[i - 1]
        actual = precios[i]

        if anterior <= 0:

            continue

        retorno = (
            (actual - anterior)
            / anterior
        ) * 100

        retornos.append(retorno)

    if len(retornos) < 5:

        return None

    try:

        return statistics.pstdev(retornos)

    except Exception:

        return None


# ============================================================
# SELECCIÓN DE LA SEXTA MONEDA
# ============================================================

def seleccionar_moneda_dinamica(mercado):

    candidatos = []

    ids_fijos = set(
        MONEDAS_PRINCIPALES.keys()
    )

    for moneda in mercado:

        coin_id = moneda.get("id")

        simbolo = str(
            moneda.get("symbol", "")
        ).lower()

        precio = moneda.get(
            "current_price"
        )

        market_cap = (
            moneda.get("market_cap")
            or 0
        )

        volumen = (
            moneda.get("total_volume")
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

        if coin_id in ids_fijos:

            continue

        if simbolo in STABLECOINS:

            continue

        if not precio:

            continue

        if cambio_24h is None:

            continue

        if market_cap < 500_000_000:

            continue

        if volumen < 50_000_000:

            continue

        if abs(cambio_24h) < 3:

            continue

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

        rsi = calcular_rsi(precios)

        if market_cap > 0:

            liquidez = (
                volumen
                / market_cap
            )

        else:

            liquidez = 0

        puntuacion = 0

        # Movimiento 24h
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

        # Movimiento 1h
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

        # Tendencia 7d
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
# SCORE LABORATORIO
# ============================================================

def calcular_score_laboratorio(
    moneda,
    precios,
    rsi,
    soporte,
    resistencia,
    promedio,
    volatilidad
):

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
        moneda.get("total_volume")
        or 0
    )

    market_cap = (
        moneda.get("market_cap")
        or 0
    )

    # ========================================================
    # 1. TENDENCIA - 20 PUNTOS
    # ========================================================

    tendencia = 0

    if cambio_7d is not None:

        if cambio_7d >= 15:

            tendencia += 12

        elif cambio_7d >= 8:

            tendencia += 10

        elif cambio_7d >= 4:

            tendencia += 8

        elif cambio_7d >= 1:

            tendencia += 6

        elif cambio_7d >= -2:

            tendencia += 4

        elif cambio_7d >= -6:

            tendencia += 2

    if precio is not None and promedio > 0:

        diferencia_promedio = (
            (precio - promedio)
            / promedio
        ) * 100

        if diferencia_promedio >= 5:

            tendencia += 8

        elif diferencia_promedio >= 2:

            tendencia += 7

        elif diferencia_promedio >= 0:

            tendencia += 5

        elif diferencia_promedio >= -3:

            tendencia += 3

        else:

            tendencia += 1

    tendencia = limitar(
        tendencia,
        0,
        20
    )

    # ========================================================
    # 2. MOMENTUM - 15 PUNTOS
    # ========================================================

    momentum = 0

    if cambio_1h is not None:

        if cambio_1h >= 2:

            momentum += 8

        elif cambio_1h >= 1:

            momentum += 7

        elif cambio_1h >= 0.3:

            momentum += 5

        elif cambio_1h >= 0:

            momentum += 3

        elif cambio_1h >= -1:

            momentum += 1

    if cambio_24h is not None:

        if cambio_24h >= 10:

            momentum += 7

        elif cambio_24h >= 5:

            momentum += 6

        elif cambio_24h >= 3:

            momentum += 5

        elif cambio_24h >= 0:

            momentum += 3

        elif cambio_24h >= -3:

            momentum += 1

    momentum = limitar(
        momentum,
        0,
        15
    )

    # ========================================================
    # 3. RSI - 15 PUNTOS
    # ========================================================

    rsi_score = 0

    if rsi is not None:

        if 52 <= rsi <= 68:

            rsi_score = 15

        elif 48 <= rsi < 52:

            rsi_score = 12

        elif 68 < rsi <= 72:

            rsi_score = 12

        elif 40 <= rsi < 48:

            rsi_score = 8

        elif 72 < rsi <= 78:

            rsi_score = 7

        elif 30 <= rsi < 40:

            rsi_score = 7

        elif rsi < 30:

            rsi_score = 5

        else:

            rsi_score = 2

    # ========================================================
    # 4. VOLUMEN - 15 PUNTOS
    # ========================================================

    volumen_score = 0

    if market_cap > 0:

        rotacion = (
            volumen
            / market_cap
        )

    else:

        rotacion = 0

    if volumen >= 1_000_000_000:

        volumen_score += 8

    elif volumen >= 500_000_000:

        volumen_score += 7

    elif volumen >= 200_000_000:

        volumen_score += 6

    elif volumen >= 100_000_000:

        volumen_score += 5

    elif volumen >= 50_000_000:

        volumen_score += 3

    if rotacion >= 0.30:

        volumen_score += 7

    elif rotacion >= 0.20:

        volumen_score += 6

    elif rotacion >= 0.10:

        volumen_score += 5

    elif rotacion >= 0.05:

        volumen_score += 3

    else:

        volumen_score += 1

    volumen_score = limitar(
        volumen_score,
        0,
        15
    )

    # ========================================================
    # 5. SOPORTE - 15 PUNTOS
    # ========================================================

    soporte_score = 0

    if precio and soporte:

        distancia = (
            (precio - soporte)
            / precio
        ) * 100

        if distancia <= 1:

            soporte_score = 15

        elif distancia <= 2:

            soporte_score = 13

        elif distancia <= 3:

            soporte_score = 11

        elif distancia <= 5:

            soporte_score = 8

        elif distancia <= 8:

            soporte_score = 5

        else:

            soporte_score = 2

    # ========================================================
    # 6. REBOTE - 10 PUNTOS
    # ========================================================

    rebote_score = 0

    if cambio_1h is not None:

        if cambio_1h >= 2:

            rebote_score += 6

        elif cambio_1h >= 1:

            rebote_score += 5

        elif cambio_1h >= 0.3:

            rebote_score += 4

        elif cambio_1h > 0:

            rebote_score += 2

    if precio and soporte:

        distancia_soporte = (
            (precio - soporte)
            / precio
        ) * 100

        if distancia_soporte <= 2:

            rebote_score += 4

        elif distancia_soporte <= 4:

            rebote_score += 2

    rebote_score = limitar(
        rebote_score,
        0,
        10
    )

    # ========================================================
    # 7. LIQUIDEZ - 5 PUNTOS
    # ========================================================

    liquidez_score = 0

    if rotacion >= 0.30:

        liquidez_score = 5

    elif rotacion >= 0.20:

        liquidez_score = 4

    elif rotacion >= 0.10:

        liquidez_score = 3

    elif rotacion >= 0.05:

        liquidez_score = 2

    elif rotacion > 0:

        liquidez_score = 1

    # ========================================================
    # 8. RIESGO - 5 PUNTOS
    # ========================================================

    riesgo_score = 5

    if volatilidad is not None:

        if volatilidad >= 5:

            riesgo_score = 0

        elif volatilidad >= 3:

            riesgo_score = 1

        elif volatilidad >= 2:

            riesgo_score = 2

        elif volatilidad >= 1:

            riesgo_score = 4

        else:

            riesgo_score = 5

    # RSI extremo reduce calidad de la señal
    if rsi is not None:

        if rsi >= 80:

            riesgo_score = max(
                0,
                riesgo_score - 2
            )

        elif rsi <= 20:

            riesgo_score = max(
                0,
                riesgo_score - 1
            )

    riesgo_score = limitar(
        riesgo_score,
        0,
        5
    )

    # ========================================================
    # TOTAL
    # ========================================================

    score_total = (
        tendencia
        + momentum
        + rsi_score
        + volumen_score
        + soporte_score
        + rebote_score
        + liquidez_score
        + riesgo_score
    )

    score_total = limitar(
        round(score_total),
        0,
        100
    )

    componentes = {
        "tendencia": tendencia,
        "momentum": momentum,
        "rsi": rsi_score,
        "volumen": volumen_score,
        "soporte": soporte_score,
        "rebote": rebote_score,
        "liquidez": liquidez_score,
        "riesgo": riesgo_score
    }

    return score_total, componentes


# ============================================================
# NIVEL DEL SCORE
# ============================================================

def obtener_nivel_score(score):

    if score >= 90:

        return "EXCEPCIONAL"

    if score >= 75:

        return "FUERTE"

    if score >= 60:

        return "INTERESANTE"

    if score >= 40:

        return "OBSERVACION"

    return "DEBIL"


# ============================================================
# ICONO DEL SCORE
# ============================================================

def obtener_icono_score(score):

    if score >= 90:

        return "🔥"

    if score >= 75:

        return "🚀"

    if score >= 60:

        return "🟢"

    if score >= 40:

        return "🟡"

    return "🔴"


# ============================================================
# ANALIZAR MONEDA
# ============================================================

def analizar_moneda(moneda):

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

    if not precios:

        precios = [precio]

    # ========================================================
    # RSI
    # ========================================================

    rsi = calcular_rsi(
        precios
    )

    # ========================================================
    # ÚLTIMAS 24 OBSERVACIONES
    # ========================================================

    if len(precios) >= 24:

        ultimos = precios[-24:]

    else:

        ultimos = precios

    soporte = min(ultimos)

    resistencia = max(ultimos)

    promedio = (
        sum(ultimos)
        / len(ultimos)
    )

    # ========================================================
    # VOLATILIDAD
    # ========================================================

    volatilidad = calcular_volatilidad(
        ultimos
    )

    # ========================================================
    # SCORE LABORATORIO
    # ========================================================

    score, componentes = (
        calcular_score_laboratorio(
            moneda,
            precios,
            rsi,
            soporte,
            resistencia,
            promedio,
            volatilidad
        )
    )

    nivel = obtener_nivel_score(
        score
    )

    icono = obtener_icono_score(
        score
    )

    # ========================================================
    # DISTANCIA AL SOPORTE
    # ========================================================

    if precio > 0:

        distancia_soporte = (
            (precio - soporte)
            / precio
        ) * 100

    else:

        distancia_soporte = 100

    # ========================================================
    # DISTANCIA A RESISTENCIA
    # ========================================================

    if precio > 0:

        distancia_resistencia = (
            (resistencia - precio)
            / precio
        ) * 100

    else:

        distancia_resistencia = 100

    # ========================================================
    # LIQUIDEZ
    # ========================================================

    market_cap = (
        moneda.get("market_cap")
        or 0
    )

    volumen = (
        moneda.get("total_volume")
        or 0
    )

    if market_cap > 0:

        liquidez = (
            volumen
            / market_cap
        )

    else:

        liquidez = 0

    # ========================================================
    # CLASIFICACIÓN
    # ========================================================

    alerta = None

    razones = []

    # --------------------------------------------------------
    # RECUPERACIÓN
    # --------------------------------------------------------

    condiciones_recuperacion = 0

    if cambio_24h <= -3:

        condiciones_recuperacion += 1

        razones.append(
            "caída 24h relevante"
        )

    if rsi is not None and rsi <= 40:

        condiciones_recuperacion += 1

        razones.append(
            "RSI bajo"
        )

    if distancia_soporte <= 3:

        condiciones_recuperacion += 1

        razones.append(
            "precio próximo al soporte"
        )

    if cambio_1h is not None and cambio_1h > 0:

        condiciones_recuperacion += 1

        razones.append(
            "rebote positivo en 1h"
        )

    # --------------------------------------------------------
    # MOMENTUM
    # --------------------------------------------------------

    condiciones_momentum = 0

    razones_momentum = []

    if cambio_24h >= 3:

        condiciones_momentum += 1

        razones_momentum.append(
            "movimiento alcista 24h"
        )

    if cambio_1h is not None and cambio_1h > 0.3:

        condiciones_momentum += 1

        razones_momentum.append(
            "impulso positivo en 1h"
        )

    if cambio_7d is not None and cambio_7d > 0:

        condiciones_momentum += 1

        razones_momentum.append(
            "tendencia 7d positiva"
        )

    if precio > promedio:

        condiciones_momentum += 1

        razones_momentum.append(
            "precio sobre promedio reciente"
        )

    if rsi is not None and 50 <= rsi <= 70:

        condiciones_momentum += 1

        razones_momentum.append(
            "RSI saludable"
        )

    # ========================================================
    # DECISIÓN FINAL
    # ========================================================

    # Primero buscamos recuperación.
    if (
        score >= 70
        and condiciones_recuperacion >= 2
        and cambio_24h < 0
    ):

        alerta = "RECUPERACION"

        razones = razones[:5]

    # Después momentum.
    elif (
        score >= 75
        and condiciones_momentum >= 3
    ):

        alerta = "MOMENTUM"

        razones = razones_momentum[:5]

    # Atención por debilidad.
    elif (
        score >= 60
        and (
            cambio_24h <= -5
            or (
                rsi is not None
                and rsi <= 30
            )
        )
    ):

        alerta = "ATENCION"

        razones = []

        if cambio_24h <= -5:

            razones.append(
                "caída 24h fuerte"
            )

        if rsi is not None and rsi <= 30:

            razones.append(
                "RSI en sobreventa"
            )

        if distancia_soporte <= 3:

            razones.append(
                "precio cerca del soporte"
            )

    # ========================================================
    # LECTURA HUMANA
    # ========================================================

    lectura = []

    if cambio_7d is not None:

        if cambio_7d > 5:

            lectura.append(
                "tendencia semanal positiva"
            )

        elif cambio_7d < -5:

            lectura.append(
                "tendencia semanal debilitada"
            )

    if cambio_1h is not None:

        if cambio_1h > 1:

            lectura.append(
                "momentum positivo de corto plazo"
            )

        elif cambio_1h < -1:

            lectura.append(
                "pérdida de fuerza en 1h"
            )

    if rsi is not None:

        if 50 <= rsi <= 70:

            lectura.append(
                "RSI en zona saludable"
            )

        elif rsi < 35:

            lectura.append(
                "RSI bajo"
            )

        elif rsi > 75:

            lectura.append(
                "RSI elevado"
            )

    if distancia_soporte <= 3:

        lectura.append(
            "precio próximo al soporte"
        )

    if distancia_resistencia <= 2:

        lectura.append(
            "precio próximo a resistencia"
        )

    if not lectura:

        lectura.append(
            "sin condición técnica dominante"
        )

    return {
        "simbolo": simbolo,
        "nombre": nombre,
        "precio": precio,
        "cambio_1h": cambio_1h,
        "cambio_24h": cambio_24h,
        "cambio_7d": cambio_7d,
        "rsi": rsi,
        "soporte": soporte,
        "resistencia": resistencia,
        "high_24h": high_24h,
        "low_24h": low_24h,
        "volatilidad": volatilidad,
        "liquidez": liquidez,
        "volumen": volumen,
        "market_cap": market_cap,
        "score": score,
        "componentes": componentes,
        "nivel": nivel,
        "icono": icono,
        "alerta": alerta,
        "razones": razones,
        "lectura": lectura
    }


# ============================================================
# MENSAJE TELEGRAM
# ============================================================

def construir_mensaje(resultado):

    simbolo = resultado["simbolo"]

    alerta = resultado["alerta"]

    score = resultado["score"]

    nivel = resultado["nivel"]

    icono = resultado["icono"]

    titulo = (
        "RECUPERACION"
        if alerta == "RECUPERACION"
        else
        "MOMENTUM"
        if alerta == "MOMENTUM"
        else
        "ATENCION"
    )

    componentes = resultado[
        "componentes"
    ]

    razones = resultado[
        "razones"
    ]

    lectura = resultado[
        "lectura"
    ]

    razones_texto = ""

    for razon in razones:

        razones_texto += (
            f"• {razon}\n"
        )

    lectura_texto = ""

    for item in lectura[:4]:

        lectura_texto += (
            f"• {item}\n"
        )

    rsi = resultado["rsi"]

    if rsi is None:

        rsi_texto = "N/D"

    else:

        rsi_texto = f"{rsi:.1f}"

    volatilidad = resultado[
        "volatilidad"
    ]

    if volatilidad is None:

        volatilidad_texto = "N/D"

    else:

        volatilidad_texto = (
            f"{volatilidad:.2f}%"
        )

    liquidez = resultado[
        "liquidez"
    ]

    liquidez_texto = (
        f"{liquidez * 100:.2f}%"
    )

    mensaje = (
        "🧪 EL LABORATORIO\n"
        "\n"
        f"{icono} {simbolo} — {titulo}\n"
        "\n"
        f"⭐ SCORE LABORATORIO: "
        f"{score}/100\n"
        f"🎯 NIVEL: {nivel}\n"
        "\n"
        f"💰 Precio: "
        f"{dinero(resultado['precio'])}\n"
        f"📈 1h: "
        f"{porcentaje(resultado['cambio_1h'])}\n"
        f"📊 24h: "
        f"{porcentaje(resultado['cambio_24h'])}\n"
        f"📅 7d: "
        f"{porcentaje(resultado['cambio_7d'])}\n"
        f"📉 RSI: {rsi_texto}\n"
        f"📦 Volumen: "
        f"${resultado['volumen']:,.0f}\n"
        f"💧 Liquidez: "
        f"{liquidez_texto}\n"
        f"🌊 Volatilidad: "
        f"{volatilidad_texto}\n"
        "\n"
        f"🧱 Soporte: "
        f"{dinero(resultado['soporte'])}\n"
        f"🔺 Resistencia: "
        f"{dinero(resultado['resistencia'])}\n"
        "\n"
        "🧠 LECTURA:\n"
        f"{lectura_texto}"
        "\n"
        "🔎 FACTORES DEL SCORE:\n"
        f"📈 Tendencia: "
        f"{componentes['tendencia']}/20\n"
        f"⚡ Momentum: "
        f"{componentes['momentum']}/15\n"
        f"📊 RSI: "
        f"{componentes['rsi']}/15\n"
        f"📦 Volumen: "
        f"{componentes['volumen']}/15\n"
        f"🧱 Soporte: "
        f"{componentes['soporte']}/15\n"
        f"🔄 Rebote: "
        f"{componentes['rebote']}/10\n"
        f"💧 Liquidez: "
        f"{componentes['liquidez']}/5\n"
        f"⚠️ Riesgo: "
        f"{componentes['riesgo']}/5\n"
        "\n"
        "📌 MOTIVOS:\n"
        f"{razones_texto}"
        "\n"
        "⚠️ Señal técnica. "
        "No constituye una recomendación "
        "automática de compra o venta."
    )

    return mensaje


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "============================================"
    )

    print(
        "🧪 BTC ALERT BOT - EL LABORATORIO 4.0"
    )

    print(
        "============================================"
    )

    # --------------------------------------------------------
    # MEMORIA
    # --------------------------------------------------------

    estado = cargar_estado()

    # --------------------------------------------------------
    # MERCADO
    # --------------------------------------------------------

    mercado = obtener_mercado()

    # --------------------------------------------------------
    # SEXTA MONEDA
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

        for moneda in mercado:

            if moneda.get("id") == coin_id:

                monedas_a_analizar.append(
                    moneda
                )

                break

    if moneda_dinamica:

        monedas_a_analizar.append(
            moneda_dinamica
        )

    print(
        f"Monedas a analizar: "
        f"{len(monedas_a_analizar)}"
    )

    # --------------------------------------------------------
    # ANALIZAR
    # --------------------------------------------------------

    resultados = []

    for moneda in monedas_a_analizar:

        simbolo = str(
            moneda.get(
                "symbol",
                ""
            )
        ).upper()

        print(
            f"\nAnalizando {simbolo}..."
        )

        try:

            resultado = analizar_moneda(
                moneda
            )

            if resultado is None:

                print(
                    f"{simbolo}: "
                    "datos insuficientes"
                )

                continue

            print(
                f"{simbolo}: "
                f"SCORE "
                f"{resultado['score']}/100"
            )

            print(
                f"Nivel: "
                f"{resultado['nivel']}"
            )

            if resultado["alerta"]:

                print(
                    f"Alerta: "
                    f"{resultado['alerta']}"
                )

            else:

                print(
                    "SIN ALERTA"
                )

            resultados.append(
                resultado
            )

        except Exception as error:

            print(
                f"Error analizando "
                f"{simbolo}: {error}"
            )

    # --------------------------------------------------------
    # NUEVAS ALERTAS
    # --------------------------------------------------------

    nuevas_alertas = []

    ultima_alerta = estado[
        "ultima_alerta"
    ]

    for resultado in resultados:

        simbolo = resultado[
            "simbolo"
        ]

        alerta = resultado[
            "alerta"
        ]

        if not alerta:

            continue

        alerta_anterior = ultima_alerta.get(
            simbolo
        )

        # ----------------------------------------------------
        # ANTI-REPETICIÓN
        # ----------------------------------------------------

        if alerta_anterior == alerta:

            print(
                f"{simbolo}: "
                f"{alerta} YA ENVIADA"
            )

            continue

        print(
            f"{simbolo}: "
            f"NUEVA ALERTA "
            f"{alerta}"
        )

        nuevas_alertas.append(
            resultado
        )

        ultima_alerta[
            simbolo
        ] = alerta

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

    for resultado in nuevas_alertas:

        mensaje = construir_mensaje(
            resultado
        )

        enviar_telegram(
            mensaje
        )

        # Pequeña pausa para evitar
        # demasiadas solicitudes seguidas.
        time.sleep(1)

    # --------------------------------------------------------
    # RESUMEN
    # --------------------------------------------------------

    if nuevas_alertas:

        print(
            f"Se enviaron "
            f"{len(nuevas_alertas)} "
            f"alerta(s) nuevas."
        )

    else:

        print(
            "No hay alertas nuevas."
        )

    print(
        "Análisis completado correctamente."
    )


# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == "__main__":

    main()