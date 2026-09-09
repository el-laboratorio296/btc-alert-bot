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