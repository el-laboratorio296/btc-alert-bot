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
        self.directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    @staticmethod
    def _safe_key(key: str) -> str:
        if not key or not key.strip():
            raise ValueError(
                "La clave de caché no puede estar vacía."
            )

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

    def get(
        self,
        key: str,
        max_age_seconds: int,
        allow_stale: bool = False,
    ) -> dict[str, Any] | None:

        if max_age_seconds < 0:
            raise ValueError(
                "max_age_seconds no puede ser negativo."
            )

        path = self._path_for(key)

        if not path.exists():
            return None

        try:
            with path.open(
                "r",
                encoding="utf-8",
            ) as file:
                entry = json.load(file)

        except (
            OSError,
            json.JSONDecodeError,
        ):
            self.delete(key)
            return None

        if not isinstance(entry, dict):
            self.delete(key)
            return None

        if entry.get("version") != self.VERSION:
            self.delete(key)
            return None

        saved_at = entry.get("saved_at")

        if not isinstance(
            saved_at,
            (int, float),
        ):
            self.delete(key)
            return None

        age = self.clock() - float(saved_at)

        if age < 0:
            return None

        if (
            age > max_age_seconds
            and not allow_stale
        ):
            return None

        payload = entry.get("payload")

        if not isinstance(payload, dict):
            self.delete(key)
            return None

        return payload

    def get_entry(
        self,
        key: str,
    ) -> dict[str, Any] | None:

        path = self._path_for(key)

        if not path.exists():
            return None

        try:
            with path.open(
                "r",
                encoding="utf-8",
            ) as file:
                entry = json.load(file)

        except (
            OSError,
            json.JSONDecodeError,
        ):
            self.delete(key)
            return None

        if not isinstance(entry, dict):
            self.delete(key)
            return None

        return entry

    def set(
        self,
        key: str,
        payload: dict[str, Any],
        source: str,
        fetched_at: float | None = None,
    ) -> None:

        if not isinstance(payload, dict):
            raise ValueError(
                "payload debe ser un diccionario."
            )

        if not source or not source.strip():
            raise ValueError(
                "source no puede estar vacío."
            )

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
                os.fsync(
                    temporary_file.fileno()
                )

                temporary_path = Path(
                    temporary_file.name
                )

            os.replace(
                temporary_path,
                destination,
            )

        except OSError as exc:

            if temporary_path is not None:
                try:
                    temporary_path.unlink(
                        missing_ok=True
                    )
                except OSError:
                    pass

            raise CacheError(
                f"No se pudo guardar el caché "
                f"'{key}': {exc}"
            ) from exc

    def is_fresh(
        self,
        key: str,
        max_age_seconds: int,
    ) -> bool:

        entry = self.get_entry(key)

        if entry is None:
            return False

        saved_at = entry.get("saved_at")

        if not isinstance(
            saved_at,
            (int, float),
        ):
            return False

        age = self.clock() - float(saved_at)

        if age < 0:
            return False

        return age <= max_age_seconds

    def delete(
        self,
        key: str,
    ) -> bool:

        path = self._path_for(key)

        try:
            path.unlink()
            return True

        except FileNotFoundError:
            return False

        except OSError as exc:
            raise CacheError(
                f"No se pudo eliminar "
                f"el caché '{key}': {exc}"
            ) from exc

    def clear(self) -> int:

        deleted = 0

        for path in self.directory.glob(
            "*.json"
        ):
            try:
                path.unlink()
                deleted += 1

            except OSError as exc:
                raise CacheError(
                    f"No se pudo eliminar "
                    f"'{path}': {exc}"
                ) from exc

        return deleted

    def stats(self) -> dict[str, Any]:

        files = list(
            self.directory.glob("*.json")
        )

        return {
            "directory": str(
                self.directory
            ),
            "entries": len(files),
            "version": self.VERSION,
        }