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
# PETICIONES HTTP
# ============================================================

def solicitar(url, params=None, intentos=3):

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
                f"Error HTTP "
                f"(intento {intento + 1}/{intentos}): "
                f"{error}"
            )

            if intento < intentos - 1:

                time.sleep(3)

    return None


# ============================================================
# TELEGRAM
# ============================================================

def enviar_telegram(mensaje):

    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: falta TELEGRAM_BOT_TOKEN.")
        return False

    if not TELEGRAM_CHAT_ID:
        print("ERROR: falta TELEGRAM_CHAT_ID.")
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
            f"Error enviando mensaje a Telegram: "
            f"{error}"
        )

        return False


# ============================================================
# MEMORIA DEL BOT
# ============================================================

def cargar_estado():

    estado_por_defecto = {
        "ultima_alerta": {}
    }

    if not os.path.exists(STATE_FILE):

        print(
            "No existe memoria anterior. "
            "Creando memoria nueva."
        )

        return estado_por_defecto

    try:

        with open(
            STATE_FILE,
            "r",
            encoding="utf-8"
        ) as archivo:

            estado = json.load(archivo)

        if not isinstance(estado, dict):

            print(
                "Memoria inválida. "
                "Creando memoria nueva."
            )

            return estado_por_defecto

        ultima_alerta = estado.get(
            "ultima_alerta"
        )

        # ----------------------------------------------------
        # CORRECCIÓN IMPORTANTE
        # ----------------------------------------------------
        # Si el estado antiguo tiene:
        #
        # "ultima_alerta": null
        #
        # lo convertimos automáticamente en:
        #
        # "ultima_alerta": {}
        #
        # para evitar el error NoneType.
        # ----------------------------------------------------

        if not isinstance(
            ultima_alerta,
            dict
        ):

            print(
                "Formato antiguo de memoria detectado."
            )

            print(
                "Reiniciando memoria de alertas."
            )

            estado["ultima_alerta"] = {}

        return estado

    except Exception as error:

        print(
            f"Error leyendo memoria: {error}"
        )

        print(
            "Se utilizará una memoria nueva."
        )

        return estado_por_defecto


def guardar_estado(estado):

    try:

        # Seguridad adicional:
        # nunca permitimos guardar None
        # como ultima_alerta.

        if not isinstance(
            estado.get("ultima_alerta"),
            dict
        ):

            estado["ultima_alerta"] = {}

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
        "sparkline": "false",
        "price_change_percentage": "24h"
    }

    datos = solicitar(
        COINGECKO_MARKETS_URL,
        parametros
    )

    if not datos:

        raise Exception(
            "No fue posible obtener "
            "los datos del mercado."
        )

    print(
        f"Mercado recibido: "
        f"{len(datos)} monedas."
    )

    return datos


# ============================================================
# SELECCIONAR SEXTA MONEDA
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

        precio = moneda.get(
            "current_price"
        )

        volumen = moneda.get(
            "total_volume"
        ) or 0

        cambio = moneda.get(
            "price_change_percentage_24h"
        )

        market_cap = moneda.get(
            "market_cap"
        ) or 0

        if coin_id in ids_principales:
            continue

        if simbolo in monedas_estables:
            continue

        if not precio:
            continue

        if cambio is None:
            continue

        if volumen < 30_000_000:
            continue

        movimiento = abs(cambio)

        if movimiento < 3:
            continue

        if market_cap < 300_000_000:
            continue

        # Puntuación basada en:
        # movimiento + volumen + capitalización

        puntuacion = (
            movimiento * 3
            + min(
                volumen / 100_000_000,
                5
            )
            + min(
                market_cap / 1_000_000_000,
                3
            )
        )

        candidatos.append(
            (
                puntuacion,
                moneda
            )
        )

    if not candidatos:

        print(
            "No se encontró una "
            "sexta moneda adecuada."
        )

        return None

    candidatos.sort(
        key=lambda x: x[0],
        reverse=True
    )

    seleccionada = candidatos[0][1]

    print(
        "Sexta moneda seleccionada: "
        f"{seleccionada.get('symbol', '').upper()} "
        f"{seleccionada.get('name', '')}"
    )

    return seleccionada


# ============================================================
# OBTENER HISTÓRICO
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
            f"No se pudo obtener histórico "
            f"de {coin_id}."
        )

        return [], []

    precios = [
        elemento[1]
        for elemento in datos.get(
            "prices",
            []
        )
    ]

    volumenes = [
        elemento[1]
        for elemento in datos.get(
            "total_volumes",
            []
        )
    ]

    return precios, volumenes


# ============================================================
# RSI
# ============================================================

def calcular_rsi(
    precios,
    periodo=14
):

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

    return 100 - (
        100 / (1 + rs)
    )


# ============================================================
# RATIO DE VOLUMEN
# ============================================================

def calcular_ratio_volumen(
    volumenes
):

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

    return (
        volumen_actual
        / promedio
    )


# ============================================================
# ANÁLISIS DE UNA MONEDA
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

    rsi = calcular_rsi(
        precios
    )

    ratio_volumen = (
        calcular_ratio_volumen(
            volumenes
        )
    )

    ultimos_24 = precios[-24:]

    minimo_24h = min(
        ultimos_24
    )

    maximo_24h = max(
        ultimos_24
    )

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

    distancia_resistencia = (
        (maximo_24h - precio)
        / precio
    )

    cerca_resistencia = (
        distancia_resistencia <= 0.01
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
    # PUNTUACIÓN DE POSIBLE RECUPERACIÓN
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
            "precio cerca del soporte"
        )

    # ========================================================
    # PUNTUACIÓN DE MOMENTUM
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
            "precio cerca de resistencia"
        )

    # ========================================================
    # DECISIÓN FINAL
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
            "nivel": None,
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
# FORMATO DE PRECIO
# ============================================================

def formato_precio(precio):

    if precio >= 1000:

        return f"${precio:,.0f}"

    if precio >= 1:

        return f"${precio:,.2f}"

    return f"${precio:,.6f}"


# ============================================================
# CREAR MENSAJE
# ============================================================

def crear_mensaje(
    alertas
):

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

        if alerta["alerta"] == "RECUPERACION":

            titulo = (
                f"🟢 {simbolo} — "
                "POSIBLE RECUPERACIÓN"
            )

        elif alerta["alerta"] == "MOMENTUM":

            titulo = (
                f"🚀 {simbolo} — "
                "MOMENTUM ALCISTA"
            )

        else:

            titulo = (
                f"🟠 {simbolo} — "
                "ATENCIÓN"
            )

        mensaje.append(
            "━━━━━━━━━━━━━━"
        )

        mensaje.append(
            titulo
        )

        mensaje.append(
            f"Nivel: {alerta['nivel']}"
        )

        mensaje.append(
            f"Puntuación: "
            f"{alerta['puntuacion']}/100"
        )

        mensaje.append(
            f"💰 Precio: "
            f"{formato_precio(alerta['precio'])}"
        )

        mensaje.append(
            f"📈 24h: "
            f"{alerta['cambio_24h']:+.2f}%"
        )

        if alerta["rsi"] is not None:

            mensaje.append(
                f"📊 RSI(14): "
                f"{alerta['rsi']:.2f}"
            )

        else:

            mensaje.append(
                "📊 RSI(14): N/D"
            )

        if alerta["ratio_volumen"] is not None:

            mensaje.append(
                f"📦 Volumen: "
                f"{alerta['ratio_volumen']:.2f}x promedio"
            )

        else:

            mensaje.append(
                "📦 Volumen: N/D"
            )

        mensaje.append(
            f"📍 Soporte 24h: "
            f"{formato_precio(alerta['soporte'])}"
        )

        mensaje.append(
            f"📍 Resistencia 24h: "
            f"{formato_precio(alerta['resistencia'])}"
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

    return "\n".join(
        mensaje
    )


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

def main():

    print(
        "==================================="
    )

    print(
        " BTC ALERT BOT - LABORATORIO"
    )

    print(
        "==================================="
    )

    estado = cargar_estado()

    # Seguridad adicional.
    # Garantiza que siempre sea un diccionario.

    ultima_alerta = estado.get(
        "ultima_alerta"
    )

    if not isinstance(
        ultima_alerta,
        dict
    ):

        ultima_alerta = {}

        estado["ultima_alerta"] = (
            ultima_alerta
        )

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

    monedas_a_analizar = []

    # --------------------------------------------------------
    # CINCO PRINCIPALES
    # --------------------------------------------------------

    for coin_id, simbolo in (
        MONEDAS_PRINCIPALES.items()
    ):

        monedas_a_analizar.append(
            (
                coin_id,
                simbolo
            )
        )

    # --------------------------------------------------------
    # SEXTA MONEDA
    # --------------------------------------------------------

    if moneda_dinamica:

        coin_id = moneda_dinamica.get(
            "id"
        )

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
    # MERCADO POR ID
    # --------------------------------------------------------

    mercado_por_id = {}

    for moneda in mercado:

        coin_id = moneda.get(
            "id"
        )

        if coin_id:

            mercado_por_id[
                coin_id
            ] = moneda

    nuevas_alertas = []

    # --------------------------------------------------------
    # ANALIZAR MONEDAS
    # --------------------------------------------------------

    for coin_id, simbolo in (
        monedas_a_analizar
    ):

        print("")
        print(
            f"Analizando {simbolo}..."
        )

        datos = mercado_por_id.get(
            coin_id
        )

        if not datos:

            print(
                f"No hay datos para "
                f"{simbolo}."
            )

            continue

        precio = datos.get(
            "current_price"
        )

        cambio_24h = (
            datos.get(
                "price_change_percentage_24h"
            )
            or 0
        )

        volumen_24h = (
            datos.get(
                "total_volume"
            )
            or 0
        )

        nombre = datos.get(
            "name",
            simbolo
        )

        if precio is None:

            print(
                f"Precio no disponible "
                f"para {simbolo}."
            )

            continue

        precios, volumenes = (
            obtener_historico(
                coin_id
            )
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

            print(
                f"No fue posible analizar "
                f"{simbolo}."
            )

            continue

        # ----------------------------------------------------
        # SIN ALERTA
        # ----------------------------------------------------

        if resultado["alerta"] is None:

            print(
                f"{simbolo}: SIN ALERTA"
            )

            # MUY IMPORTANTE:
            # Al desaparecer una alerta,
            # reiniciamos su memoria.
            # Así podrá volver a alertar
            # cuando aparezca una nueva señal.

            ultima_alerta[simbolo] = None

            continue

        # ----------------------------------------------------
        # ALERTA DETECTADA
        # ----------------------------------------------------

        tipo = resultado["alerta"]

        nivel = resultado["nivel"]

        identificador = (
            f"{tipo}_{nivel}"
        )

        anterior = (
            ultima_alerta.get(
                simbolo
            )
        )

        print(
            f"{simbolo}: "
            f"{tipo} "
            f"{nivel} "
            f"{resultado['puntuacion']}/100"
        )

        # ----------------------------------------------------
        # EVITAR REPETICIONES
        # ----------------------------------------------------

        if identificador != anterior:

            nuevas_alertas.append(
                resultado
            )

            ultima_alerta[simbolo] = (
                identificador
            )

            print(
                f"Nueva alerta: "
                f"{simbolo}"
            )

        else:

            print(
                f"{simbolo}: "
                "alerta ya enviada. "
                "No se repite."
            )

    # --------------------------------------------------------
    # GUARDAR MEMORIA
    # --------------------------------------------------------

    estado["ultima_alerta"] = (
        ultima_alerta
    )

    guardar_estado(
        estado
    )

    # --------------------------------------------------------
    # ENVIAR ALERTAS
    # --------------------------------------------------------

    if nuevas_alertas:

        mensaje = crear_mensaje(
            nuevas_alertas
        )

        enviado = enviar_telegram(
            mensaje
        )

        if enviado:

            print(
                f"Se enviaron "
                f"{len(nuevas_alertas)} "
                "alerta(s)."
            )

        else:

            print(
                "No fue posible enviar "
                "las alertas a Telegram."
            )

    else:

        print(
            "No hay alertas nuevas."
        )

    print("")
    print(
        "Análisis completado correctamente."
    )


# ============================================================
# EJECUCIÓN
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