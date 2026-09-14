from __future__ import annotations

import logging
import os
import sys
import time
from typing import Any, Dict, List, Sequence

import requests

from radar.alerts import build_alert
from radar.decision import build_decision
from radar.indicators import compute_indicators
from radar.market import MarketDataService
from radar.reports import (
    REPORT_TYPE_CLOSING,
    REPORT_TYPE_INTRADAY,
    REPORT_TYPE_OPENING,
    build_report,
)
from radar.risk import calculate_risk_plan
from radar.scoring import calculate_technical_score
from radar.state import StateStore
from radar.strategy import evaluate_strategy
from radar.structure import analyze_structure


# ============================================================
# CONFIGURACIÓN
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

STATE_FILE = os.getenv("RADAR_STATE_FILE", "radar_state.json")

REQUEST_TIMEOUT = int(os.getenv("RADAR_REQUEST_TIMEOUT", "20"))

PRIMARY_ASSETS = (
    "BTC",
    "ETH",
    "SOL",
    "BNB",
    "XRP",
)

TECHNICAL_TIMEFRAMES = (
    "15m",
    "1h",
    "4h",
    "1d",
)

DEFAULT_REPORT_TYPE = os.getenv(
    "RADAR_REPORT_TYPE",
    REPORT_TYPE_INTRADAY,
).strip().lower()


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("el-laboratorio-radar")


# ============================================================
# ERRORES
# ============================================================


class BotError(Exception):
    """Error controlado del orquestador."""


# ============================================================
# TELEGRAM
# ============================================================


def send_telegram(message: str) -> bool:
    """
    Envía un mensaje a Telegram.

    El estado NO se actualiza aquí.
    El caller debe guardar el estado únicamente
    después de recibir confirmación exitosa.
    """

    if not TELEGRAM_BOT_TOKEN:
        logger.error("Falta TELEGRAM_BOT_TOKEN.")
        return False

    if not TELEGRAM_CHAT_ID:
        logger.error("Falta TELEGRAM_CHAT_ID.")
        return False

    url = (
        "https://api.telegram.org/bot"
        f"{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code != 200:
            logger.error(
                "Telegram HTTP %s: %s",
                response.status_code,
                response.text[:500],
            )
            return False

        data = response.json()

        if not data.get("ok", False):
            logger.error("Telegram rechazó el mensaje: %s", data)
            return False

        return True

    except requests.RequestException as exc:
        logger.error("Error de conexión con Telegram: %s", exc)
        return False

    except ValueError as exc:
        logger.error("Respuesta JSON inválida de Telegram: %s", exc)
        return False


# ============================================================
# UTILIDADES
# ============================================================


def normalize_symbol(symbol: str) -> str:
    return str(symbol).strip().upper()


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)

        if number != number:
            return default

        return number

    except (TypeError, ValueError):
        return default


def get_mapping_value(
    mapping: Any,
    key: str,
    default: Any = None,
) -> Any:

    if isinstance(mapping, dict):
        return mapping.get(key, default)

    return getattr(mapping, key, default)


def serialize_result(result: Any) -> Dict[str, Any]:
    """
    Convierte dataclasses/diccionarios simples a un diccionario
    que pueda ser consumido por los siguientes módulos.
    """

    if result is None:
        return {}

    if isinstance(result, dict):
        return result

    if hasattr(result, "__dataclass_fields__"):
        return {
            field_name: getattr(result, field_name)
            for field_name in result.__dataclass_fields__
        }

    if hasattr(result, "__dict__"):
        return dict(result.__dict__)

    return {}


# ============================================================
# DESCUBRIMIENTO DEL SEXTO ACTIVO
# ============================================================


def select_dynamic_asset(market_service: MarketDataService) -> str | None:
    """
    Busca un sexto activo dinámico mediante CoinGecko.

    Importante:
    el movimiento de precio por sí solo NO determina la selección.

    El activo seleccionado posteriormente pasa por todo el Radar V5.
    """

    try:
        markets = market_service.coingecko.get_markets(
            limit=100,
            page=1,
        )

    except Exception as exc:
        logger.warning(
            "No fue posible obtener universo CoinGecko: %s",
            exc,
        )
        return None

    candidates: List[Dict[str, Any]] = []

    excluded = {
        normalize_symbol(symbol)
        for symbol in PRIMARY_ASSETS
    }

    for asset in markets:
        symbol = normalize_symbol(
            asset.get("symbol", "")
        )

        if not symbol:
            continue

        if symbol in excluded:
            continue

        market_cap = safe_float(
            asset.get("market_cap"),
        )

        volume_24h = safe_float(
            asset.get("volume_24h"),
        )

        rank = safe_float(
            asset.get("rank"),
        )

        change_24h = safe_float(
            asset.get("change_24h"),
        )

        # Filtros mínimos de operabilidad.
        if market_cap < 500_000_000:
            continue

        if volume_24h < 50_000_000:
            continue

        # Evitamos seleccionar activos completamente planos.
        if abs(change_24h) < 1.0:
            continue

        candidates.append(
            {
                "symbol": symbol,
                "market_cap": market_cap,
                "volume_24h": volume_24h,
                "rank": rank,
                "change_24h": change_24h,
            }
        )

    if not candidates:
        logger.warning(
            "No se encontró sexto activo dinámico."
        )
        return None

    # Preferimos liquidez + capitalización + movimiento razonable.
    # NO usamos abs(change_24h) como criterio dominante para evitar
    # seleccionar automáticamente un activo que simplemente está cayendo.
    candidates.sort(
        key=lambda item: (
            item["volume_24h"],
            item["market_cap"],
            -abs(item["change_24h"]),
            -item["rank"],
        ),
        reverse=True,
    )

    selected = candidates[0]["symbol"]

    logger.info(
        "Sexto activo dinámico seleccionado: %s",
        selected,
    )

    return selected


# ============================================================
# MERCADO
# ============================================================


def build_market_service() -> MarketDataService:
    """
    Construye el servicio central de mercado.

    Binance:
        datos técnicos OHLCV.

    CoinGecko:
        universo y market intelligence.
    """

    return MarketDataService()


# ============================================================
# ANÁLISIS DE UN ACTIVO
# ============================================================