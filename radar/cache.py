from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any


class CacheError(Exception):
    """Error base del sistema de caché."""


class CacheCorruptedError(CacheError):
    """El archivo de caché existe pero no contiene datos válidos."""


class MarketCache:
    """
    Caché local, seguro y basado en JSON.

    Características:
    - Claves separadas por proveedor/símbolo/timeframe.
    - Escrituras atómicas.
    - TTL configurable.
    - No considera errores de API como datos válidos.
    - Tolera archivos corruptos.
    - No depende de servicios externos.
    """

    VERSION = 1

    def __init__(
        self,
        directory: str | Path = "data/cache",
        clock=time.time,
    ) -> None:
        self.directory = Path(directory)
        self.clock = clock
        self.directory.mkdir(parents=True, exist_ok=True)

    # ============================================================
    # UTILIDADES
    # ============================================================

    @staticmethod
    def _safe_key(key: str) -> str:
        """
        Convierte una clave lógica en un nombre de archivo seguro.
        """
        if not key or not key.strip():
            raise ValueError("La clave de caché no puede estar vacía.")

        allowed = set(
            "abcdefghijklmnopqrstuvwxyz"
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            "0123456789"
            "_-."
            ":"
        )

        cleaned = "".join(
            char if char in allowed else "_"
            for char in key.strip()
        )

        return cleaned

    def _path_for(self, key: str) -> Path:
        return self.directory / f"{self._safe_key(key)}.json"

    # ============================================================
    # LECTURA
    # ============================================================

    def get(
        self,
        key: str,
        max_age_seconds: int,
        allow_stale: bool = False,
    ) -> dict[str, Any] | None:
        """
        Recupera un elemento del caché.

        Args:
            key:
                Identificador lógico.

            max_age_seconds:
                Antigüedad máxima permitida.

            allow_stale:
                Si True, permite devolver datos antiguos.

        Returns:
            El payload almacenado o None si no existe/no es válido.
        """

        if max_age_seconds < 0:
            raise ValueError("max_age_seconds no puede ser negativo.")

        path = self._path_for(key)

        if not path.exists():
            return None

        try:
            with path.open("r", encoding="utf-8") as file:
                entry = json.load(file)
        except (OSError, json.JSONDecodeError) as exc:
            # Un caché corrupto nunca debe romper el radar.
            self.delete(key)
            return None

        if not isinstance(entry, dict):
            self.delete(key)
            return None

        if entry.get("version") != self.VERSION:
            self.delete(key)
            return None

        saved_at = entry.get("saved_at")

        if not isinstance(saved_at, (int, float)):
            self.delete(key)
            return None

        age = self.clock() - float(saved_at)

        if age < 0:
            # El reloj del sistema pudo retroceder.
            # Tratamos los datos como no confiables.
            return None

        if age > max_age_seconds and not allow_stale:
            return None

        payload = entry.get("payload")

        if not isinstance(payload, dict):
            self.delete(key)
            return None

        return payload

    # ============================================================
    # LECTURA CON METADATOS
    # ============================================================

    def get_entry(
        self,
        key: str,
    ) -> dict[str, Any] | None:
        """
        Devuelve la entrada completa del caché.

        Útil para diagnóstico y observabilidad.
        """

        path = self._path_for(key)

        if not path.exists():
            return None

        try:
            with path.open("r", encoding="utf-8") as file:
                entry = json.load(file)
        except (OSError, json.JSONDecodeError):
            self.delete(key)
            return None

        if not isinstance(entry, dict):
            self.delete(key)
            return None

        return entry

    # ============================================================
    # ESCRITURA
    # ============================================================

    def set(
        self,
        key: str,
        payload: dict[str, Any],
        source: str,
        fetched_at: float | None = None,
    ) -> None:
        """
        Guarda datos en caché mediante escritura atómica.

        Nunca debe utilizarse para almacenar respuestas de error.
        """

        if not isinstance(payload, dict):
            raise ValueError("payload debe ser un diccionario.")

        if not source or not source.strip():
            raise ValueError("source no puede estar vacío.")

        timestamp = (
            float(fetched_at)
            if fetched_at is not None
            else float(self.clock())
        )

        entry = {
            "version": self.VERSION,
            "key": key,
            "source": source,
            "saved_at": timestamp,
            "payload": payload,
        }

        destination = self._path_for(key)

        temporary_path: Path | None = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.directory,
                prefix=".cache_",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:

                json.dump(
                    entry,
                    temporary_file,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )

                temporary_file.flush()
                os.fsync(temporary_file.fileno())

                temporary_path = Path(temporary_file.name)

            os.replace(temporary_path, destination)

        except OSError as exc:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass

            raise CacheError(
                f"No se pudo guardar el caché '{key}': {exc}"
            ) from exc

    # ============================================================
    # FRESCURA
    # ============================================================

    def is_fresh(
        self,
        key: str,
        max_age_seconds: int,
    ) -> bool:
        """
        Indica si existe una entrada dentro del TTL permitido.
        """

        entry = self.get_entry(key)

        if entry is None:
            return False

        saved_at = entry.get("saved_at")

        if not isinstance(saved_at, (int, float)):
            return False

        age = self.clock() - float(saved_at)

        if age < 0:
            return False

        return age <= max_age_seconds

    # ============================================================
    # ELIMINAR
    # ============================================================

    def delete(self, key: str) -> bool:
        """
        Elimina una entrada.

        Returns:
            True si se eliminó.
            False si no existía.
        """

        path = self._path_for(key)

        try:
            path.unlink()
            return True
        except FileNotFoundError:
            return False
        except OSError as exc:
            raise CacheError(
                f"No se pudo eliminar el caché '{key}': {exc}"
            ) from exc

    # ============================================================
    # LIMPIAR TODO
    # ============================================================

    def clear(self) -> int:
        """
        Elimina todos los archivos JSON del caché.

        Returns:
            Cantidad de archivos eliminados.
        """

        deleted = 0

        for path in self.directory.glob("*.json"):
            try:
                path.unlink()
                deleted += 1
            except OSError as exc:
                raise CacheError(
                    f"No se pudo eliminar '{path}': {exc}"
                ) from exc

        return deleted

    # ============================================================
    # INFORMACIÓN
    # ============================================================

    def stats(self) -> dict[str, Any]:
        """
        Información básica del caché.
        """

        files = list(self.directory.glob("*.json"))

        return {
            "directory": str(self.directory),
            "entries": len(files),
            "version": self.VERSION,
        }