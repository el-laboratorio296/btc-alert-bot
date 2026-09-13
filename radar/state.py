from __future__ import annotations

import copy
import json
import math
import os
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping


STATE_VERSION = 1


class StateError(Exception):
    """Error base del almacenamiento de estado."""


class StateCorruptedError(StateError):
    """El archivo de estado existe pero no es válido."""


def _finite_number(
    value: Any,
    name: str,
    default: float | None = None,
) -> float | None:
    if value is None:
        return default

    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{name} debe ser numérico."
        ) from exc

    if not math.isfinite(number):
        raise ValueError(
            f"{name} debe ser un número finito."
        )

    return number


def _optional_number(
    value: Any,
    name: str,
    default: float | None = None,
) -> float | None:
    if value is None:
        return default

    return _finite_number(
        value,
        name,
        default,
    )


def _normalize_asset(value: Any) -> str:
    if value is None:
        raise ValueError(
            "asset es obligatorio."
        )

    asset = str(value).strip().upper()

    if not asset:
        raise ValueError(
            "asset no puede estar vacío."
        )

    return asset


def _normalize_decision(value: Any) -> str:
    if value is None:
        raise ValueError(
            "decision es obligatorio."
        )

    decision = str(value).strip().upper()

    if not decision:
        raise ValueError(
            "decision no puede estar vacío."
        )

    return decision


def _normalize_text(
    value: Any,
    default: str = "",
) -> str:
    if value is None:
        return default

    return str(value).strip()


def _normalize_collection(
    value: Any,
) -> tuple[str, ...]:
    if value is None:
        return ()

    if isinstance(
        value,
        str,
    ):
        return (value.strip(),)

    if not isinstance(
        value,
        (list, tuple, set),
    ):
        return ()

    result: list[str] = []

    for item in value:
        text = str(item).strip()

        if text:
            result.append(text)

    return tuple(result)


@dataclass(frozen=True)
class SignalState:
    asset: str
    decision: str
    price: float
    timestamp: float

    bias: str = "NEUTRAL"
    technical_score: float = 0.0
    confidence: float = 0.0
    market_regime: str = "NEUTRAL"
    risk_level: str = "MEDIUM"

    reason: str = ""

    entry_zone: str = ""

    invalidation: float | None = None
    stop: float | None = None

    tp1: float | None = None
    tp2: float | None = None
    tp3: float | None = None

    risk_reward: float | None = None

    confirmations: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "asset",
            _normalize_asset(self.asset),
        )

        object.__setattr__(
            self,
            "decision",
            _normalize_decision(
                self.decision
            ),
        )

        price = _finite_number(
            self.price,
            "price",
        )

        if price is None or price <= 0:
            raise ValueError(
                "price debe ser mayor que cero."
            )

        object.__setattr__(
            self,
            "price",
            price,
        )

        timestamp = _finite_number(
            self.timestamp,
            "timestamp",
        )

        if timestamp is None or timestamp < 0:
            raise ValueError(
                "timestamp debe ser mayor o igual a cero."
            )

        object.__setattr__(
            self,
            "timestamp",
            timestamp,
        )

        object.__setattr__(
            self,
            "bias",
            _normalize_text(
                self.bias,
                "NEUTRAL",
            ).upper(),
        )

        technical_score = _finite_number(
            self.technical_score,
            "technical_score",
            0.0,
        )

        confidence = _finite_number(
            self.confidence,
            "confidence",
            0.0,
        )

        if technical_score is None:
            technical_score = 0.0

        if confidence is None:
            confidence = 0.0

        object.__setattr__(
            self,
            "technical_score",
            technical_score,
        )

        object.__setattr__(
            self,
            "confidence",
            confidence,
        )

        object.__setattr__(
            self,
            "market_regime",
            _normalize_text(
                self.market_regime,
                "NEUTRAL",
            ).upper(),
        )

        object.__setattr__(
            self,
            "risk_level",
            _normalize_text(
                self.risk_level,
                "MEDIUM",
            ).upper(),
        )

        object.__setattr__(
            self,
            "reason",
            _normalize_text(
                self.reason
            ),
        )

        object.__setattr__(
            self,
            "entry_zone",
            _normalize_text(
                self.entry_zone
            ),
        )

        for field_name in (
            "invalidation",
            "stop",
            "tp1",
            "tp2",
            "tp3",
            "risk_reward",
        ):
            value = _optional_number(
                getattr(self, field_name),
                field_name,
                None,
            )

            object.__setattr__(
                self,
                field_name,
                value,
            )

        object.__setattr__(
            self,
            "confirmations",
            _normalize_collection(
                self.confirmations
            ),
        )

        object.__setattr__(
            self,
            "blockers",
            _normalize_collection(
                self.blockers
            ),
        )

        object.__setattr__(
            self,
            "warnings",
            _normalize_collection(
                self.warnings
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)

        data["confirmations"] = list(
            self.confirmations
        )

        data["blockers"] = list(
            self.blockers
        )

        data["warnings"] = list(
            self.warnings
        )

        return data

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
    ) -> "SignalState":
        if not isinstance(
            data,
            Mapping,
        ):
            raise TypeError(
                "data debe ser un Mapping."
            )

        if "asset" not in data:
            raise ValueError(
                "asset es obligatorio."
            )

        if "decision" not in data:
            raise ValueError(
                "decision es obligatorio."
            )

        if "price" not in data:
            raise ValueError(
                "price es obligatorio."
            )

        if "timestamp" not in data:
            raise ValueError(
                "timestamp es obligatorio."
            )

        return cls(
            asset=data["asset"],
            decision=data["decision"],
            price=data["price"],
            timestamp=data["timestamp"],
            bias=data.get(
                "bias",
                "NEUTRAL",
            ),
            technical_score=data.get(
                "technical_score",
                0.0,
            ),
            confidence=data.get(
                "confidence",
                0.0,
            ),
            market_regime=data.get(
                "market_regime",
                "NEUTRAL",
            ),
            risk_level=data.get(
                "risk_level",
                "MEDIUM",
            ),
            reason=data.get(
                "reason",
                "",
            ),
            entry_zone=data.get(
                "entry_zone",
                "",
            ),
            invalidation=data.get(
                "invalidation"
            ),
            stop=data.get(
                "stop"
            ),
            tp1=data.get(
                "tp1"
            ),
            tp2=data.get(
                "tp2"
            ),
            tp3=data.get(
                "tp3"
            ),
            risk_reward=data.get(
                "risk_reward"
            ),
            confirmations=data.get(
                "confirmations",
                (),
            ),
            blockers=data.get(
                "blockers",
                (),
            ),
            warnings=data.get(
                "warnings",
                (),
            ),
        )


class StateStore:
    """
    Almacenamiento persistente del estado de señales.

    El archivo utiliza esta estructura:

    {
        "version": 1,
        "updated_at": 1234567890.0,
        "signals": {
            "BTCUSDT": {
                ...
            }
        }
    }
    """

    def __init__(
        self,
        path: str | Path,
        clock=time.time,
    ) -> None:
        if path is None:
            raise TypeError(
                "path no puede ser None."
            )

        if not isinstance(
            path,
            (str, Path),
        ):
            raise TypeError(
                "path debe ser str o Path."
            )

        self.path = Path(path)
        self.clock = clock

        if self.path.exists():
            self._load_or_reset()
        else:
            self._write_state(
                self._empty_state()
            )

    @staticmethod
    def _empty_state() -> dict[str, Any]:
        return {
            "version": STATE_VERSION,
            "updated_at": None,
            "signals": {},
        }

    def _validate_root(
        self,
        data: Any,
    ) -> dict[str, Any]:
        if not isinstance(
            data,
            dict,
        ):
            raise StateCorruptedError(
                "La raíz del estado debe ser un objeto."
            )

        if data.get("version") != STATE_VERSION:
            raise StateCorruptedError(
                "Versión de estado incompatible."
            )

        signals = data.get(
            "signals"
        )

        if not isinstance(
            signals,
            dict,
        ):
            raise StateCorruptedError(
                "signals debe ser un objeto."
            )

        updated_at = data.get(
            "updated_at"
        )

        if (
            updated_at is not None
            and not isinstance(
                updated_at,
                (int, float),
            )
        ):
            raise StateCorruptedError(
                "updated_at no es válido."
            )

        return data

    def _read_state(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty_state()

        try:
            with self.path.open(
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(file)
        except (
            OSError,
            json.JSONDecodeError,
        ) as exc:
            raise StateCorruptedError(
                "No se pudo leer el archivo de estado."
            ) from exc

        return self._validate_root(
            data
        )

    def _load_or_reset(self) -> None:
        try:
            self._read_state()
        except StateCorruptedError:
            self._write_state(
                self._empty_state()
            )

    def _write_state(
        self,
        state: Mapping[str, Any],
    ) -> None:
        if not isinstance(
            state,
            Mapping,
        ):
            raise TypeError(
                "state debe ser un Mapping."
            )

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path: Path | None = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:

                json.dump(
                    state,
                    temporary_file,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )

                temporary_file.write("\n")

                temporary_file.flush()

                os.fsync(
                    temporary_file.fileno()
                )

                temporary_path = Path(
                    temporary_file.name
                )

            os.replace(
                temporary_path,
                self.path,
            )

        except OSError as exc:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(
                        missing_ok=True
                    )
                except OSError:
                    pass

            raise StateError(
                f"No se pudo guardar el estado: {exc}"
            ) from exc

    def _load_signals(
        self,
    ) -> dict[str, Any]:
        state = self._read_state()

        signals = state[
            "signals"
        ]

        return copy.deepcopy(
            signals
        )

    def get_all(self) -> dict[str, Any]:
        return self._load_signals()

    def get_signal(
        self,
        asset: str,
    ) -> dict[str, Any] | None:
        normalized_asset = _normalize_asset(
            asset
        )

        signals = self._load_signals()

        signal = signals.get(
            normalized_asset
        )

        if signal is None:
            return None

        return copy.deepcopy(
            signal
        )

    def save_signal(
        self,
        signal: SignalState,
    ) -> None:
        if not isinstance(
            signal,
            SignalState,
        ):
            raise TypeError(
                "signal debe ser un SignalState."
            )

        state = self._read_state()

        signals = state.get(
            "signals",
            {},
        )

        signals[
            signal.asset
        ] = signal.to_dict()

        state = {
            "version": STATE_VERSION,
            "updated_at": float(
                self.clock()
            ),
            "signals": signals,
        }

        self._write_state(
            state
        )

    def delete_signal(
        self,
        asset: str,
    ) -> bool:
        normalized_asset = _normalize_asset(
            asset
        )

        state = self._read_state()

        signals = state.get(
            "signals",
            {},
        )

        if normalized_asset not in signals:
            return False

        del signals[
            normalized_asset
        ]

        state = {
            "version": STATE_VERSION,
            "updated_at": float(
                self.clock()
            ),
            "signals": signals,
        }

        self._write_state(
            state
        )

        return True

    def clear(self) -> int:
        state = self._read_state()

        signals = state.get(
            "signals",
            {},
        )

        deleted = len(
            signals
        )

        state = {
            "version": STATE_VERSION,
            "updated_at": float(
                self.clock()
            ),
            "signals": {},
        }

        self._write_state(
            state
        )

        return deleted

    def signal_age(
        self,
        asset: str,
    ) -> float | None:
        signal = self.get_signal(
            asset
        )

        if signal is None:
            return None

        timestamp = signal.get(
            "timestamp"
        )

        if not isinstance(
            timestamp,
            (int, float),
        ):
            return None

        age = float(
            self.clock()
        ) - float(
            timestamp
        )

        return max(
            0.0,
            age,
        )

    def is_fresh(
        self,
        asset: str,
        max_age_seconds: int | float,
    ) -> bool:
        if max_age_seconds < 0:
            raise ValueError(
                "max_age_seconds no puede ser negativo."
            )

        age = self.signal_age(
            asset
        )

        if age is None:
            return False

        return age <= float(
            max_age_seconds
        )

    @staticmethod
    def _signal_fingerprint(
        signal: SignalState,
    ) -> tuple[Any, ...]:
        """
        Determina qué elementos representan
        un cambio material de señal.

        El precio y timestamp NO forman parte
        del fingerprint. Esto evita generar
        una alerta nueva cada vez que cambia
        ligeramente el precio.
        """

        return (
            signal.asset,
            signal.decision,
            signal.bias,
            signal.technical_score,
            signal.confidence,
            signal.market_regime,
            signal.risk_level,
            signal.reason,
            signal.entry_zone,
            signal.invalidation,
            signal.stop,
            signal.tp1,
            signal.tp2,
            signal.tp3,
            signal.risk_reward,
            signal.confirmations,
            signal.blockers,
            signal.warnings,
        )

    def has_changed(
        self,
        signal: SignalState,
    ) -> bool:
        if not isinstance(
            signal,
            SignalState,
        ):
            raise TypeError(
                "signal debe ser un SignalState."
            )

        previous = self.get_signal(
            signal.asset
        )

        if previous is None:
            return True

        try:
            previous_signal = (
                SignalState.from_dict(
                    previous
                )
            )
        except (
            TypeError,
            ValueError,
            KeyError,
        ):
            return True

        return (
            self._signal_fingerprint(
                previous_signal
            )
            != self._signal_fingerprint(
                signal
            )
        )

    def save_if_changed(
        self,
        signal: SignalState,
    ) -> bool:
        changed = self.has_changed(
            signal
        )

        if changed:
            self.save_signal(
                signal
            )

        return changed

    def updated_at(self) -> float | None:
        state = self._read_state()

        value = state.get(
            "updated_at"
        )

        if value is None:
            return None

        return float(value)

    def stats(self) -> dict[str, Any]:
        state = self._read_state()

        signals = state.get(
            "signals",
            {},
        )

        return {
            "version": STATE_VERSION,
            "path": str(self.path),
            "signals": len(
                signals
            ),
            "updated_at": state.get(
                "updated_at"
            ),
        }