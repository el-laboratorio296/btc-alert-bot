from __future__ import annotations

import json
import time

import pytest

from radar.state import (
    STATE_VERSION,
    SignalState,
    StateStore,
)


def base_signal(
    asset="BTCUSDT",
    decision="BUY",
    price=100000.0,
    timestamp=1700000000.0,
):
    return {
        "asset": asset,
        "decision": decision,
        "bias": "BULLISH",
        "price": price,
        "technical_score": 80.0,
        "confidence": 85.0,
        "market_regime": "RISK_ON",
        "risk_level": "LOW",
        "reason": "Señal confirmada.",
        "entry_zone": "100000-101000",
        "invalidation": 98000.0,
        "stop": 97500.0,
        "tp1": 103000.0,
        "tp2": 106000.0,
        "tp3": 110000.0,
        "risk_reward": 2.0,
        "timestamp": timestamp,
    }


def test_state_version_exists():
    assert isinstance(STATE_VERSION, int)
    assert STATE_VERSION >= 1


def test_signal_state_can_be_created():
    signal = SignalState(
        asset="BTCUSDT",
        decision="BUY",
        price=100000.0,
        timestamp=1700000000.0,
    )

    assert signal.asset == "BTCUSDT"
    assert signal.decision == "BUY"
    assert signal.price == 100000.0
    assert signal.timestamp == 1700000000.0


def test_signal_state_has_default_metadata():
    signal = SignalState(
        asset="BTCUSDT",
        decision="BUY",
        price=100000.0,
        timestamp=1700000000.0,
    )

    assert signal.bias == "NEUTRAL"
    assert signal.confidence == 0.0
    assert signal.technical_score == 0.0
    assert signal.market_regime == "NEUTRAL"
    assert signal.risk_level == "MEDIUM"


def test_signal_state_to_dict_is_json_serializable():
    signal = SignalState(
        asset="BTCUSDT",
        decision="BUY",
        price=100000.0,
        timestamp=1700000000.0,
    )

    data = signal.to_dict()

    assert isinstance(data, dict)
    json.dumps(data)


def test_signal_state_normalizes_asset():
    signal = SignalState(
        asset="btcusdt",
        decision="BUY",
        price=100000.0,
        timestamp=1700000000.0,
    )

    assert signal.asset == "BTCUSDT"


def test_signal_state_rejects_empty_asset():
    with pytest.raises(ValueError):
        SignalState(
            asset="",
            decision="BUY",
            price=100000.0,
            timestamp=1700000000.0,
        )


def test_signal_state_rejects_empty_decision():
    with pytest.raises(ValueError):
        SignalState(
            asset="BTCUSDT",
            decision="",
            price=100000.0,
            timestamp=1700000000.0,
        )


def test_signal_state_rejects_negative_price():
    with pytest.raises(ValueError):
        SignalState(
            asset="BTCUSDT",
            decision="BUY",
            price=-1.0,
            timestamp=1700000000.0,
        )


def test_signal_state_rejects_invalid_timestamp():
    with pytest.raises(ValueError):
        SignalState(
            asset="BTCUSDT",
            decision="BUY",
            price=100000.0,
            timestamp=-1.0,
        )


def test_store_can_be_created(tmp_path):
    store = StateStore(tmp_path / "state.json")

    assert store.path.exists()
    assert store.path.name == "state.json"


def test_new_store_is_empty(tmp_path):
    store = StateStore(tmp_path / "state.json")

    assert store.get_all() == {}


def test_new_store_has_valid_state_file(tmp_path):
    path = tmp_path / "state.json"

    StateStore(path)

    assert path.exists()

    data = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    assert data["version"] == STATE_VERSION
    assert isinstance(data["signals"], dict)


def test_store_save_and_load_signal(tmp_path):
    path = tmp_path / "state.json"

    store = StateStore(path)

    signal = SignalState(
        asset="BTCUSDT",
        decision="BUY",
        price=100000.0,
        timestamp=1700000000.0,
    )

    store.save_signal(signal)

    loaded = store.get_signal("BTCUSDT")

    assert loaded is not None
    assert loaded["asset"] == "BTCUSDT"
    assert loaded["decision"] == "BUY"
    assert loaded["price"] == 100000.0


def test_store_preserves_multiple_assets(tmp_path):
    store = StateStore(tmp_path / "state.json")

    store.save_signal(
        SignalState(
            asset="BTCUSDT",
            decision="BUY",
            price=100000.0,
            timestamp=1700000000.0,
        )
    )

    store.save_signal(
        SignalState(
            asset="ETHUSDT",
            decision="ACCUMULATE",
            price=4000.0,
            timestamp=1700000000.0,
        )
    )

    signals = store.get_all()

    assert set(signals.keys()) == {
        "BTCUSDT",
        "ETHUSDT",
    }


def test_store_replaces_existing_asset_state(tmp_path):
    store = StateStore(tmp_path / "state.json")

    first = SignalState(
        asset="BTCUSDT",
        decision="BUY",
        price=100000.0,
        timestamp=1700000000.0,
    )

    second = SignalState(
        asset="BTCUSDT",
        decision="WAIT_CONFIRMATION",
        price=99000.0,
        timestamp=1700000600.0,
    )

    store.save_signal(first)
    store.save_signal(second)

    loaded = store.get_signal("BTCUSDT")

    assert loaded is not None
    assert loaded["decision"] == (
        "WAIT_CONFIRMATION"
    )
    assert loaded["price"] == 99000.0


def test_get_unknown_asset_returns_none(tmp_path):
    store = StateStore(tmp_path / "state.json")

    assert store.get_signal("SOLUSDT") is None


def test_get_all_returns_copy(tmp_path):
    store = StateStore(tmp_path / "state.json")

    store.save_signal(
        SignalState(
            asset="BTCUSDT",
            decision="BUY",
            price=100000.0,
            timestamp=1700000000.0,
        )
    )

    data = store.get_all()

    data["BTCUSDT"]["decision"] = "AVOID"

    original = store.get_signal("BTCUSDT")

    assert original["decision"] == "BUY"


def test_store_delete_signal(tmp_path):
    store = StateStore(tmp_path / "state.json")

    store.save_signal(
        SignalState(
            asset="BTCUSDT",
            decision="BUY",
            price=100000.0,
            timestamp=1700000000.0,
        )
    )

    assert store.delete_signal("BTCUSDT") is True
    assert store.get_signal("BTCUSDT") is None


def test_delete_unknown_signal_returns_false(tmp_path):
    store = StateStore(tmp_path / "state.json")

    assert store.delete_signal("BTCUSDT") is False


def test_store_clear_removes_all_signals(tmp_path):
    store = StateStore(tmp_path / "state.json")

    for asset in (
        "BTCUSDT",
        "ETHUSDT",
        "SOLUSDT",
    ):
        store.save_signal(
            SignalState(
                asset=asset,
                decision="BUY",
                price=100.0,
                timestamp=1700000000.0,
            )
        )

    deleted = store.clear()

    assert deleted == 3
    assert store.get_all() == {}


def test_store_persists_between_instances(tmp_path):
    path = tmp_path / "state.json"

    store1 = StateStore(path)

    store1.save_signal(
        SignalState(
            asset="BTCUSDT",
            decision="BUY",
            price=100000.0,
            timestamp=1700000000.0,
        )
    )

    store2 = StateStore(path)

    loaded = store2.get_signal("BTCUSDT")

    assert loaded is not None
    assert loaded["decision"] == "BUY"


def test_store_handles_corrupted_json(tmp_path):
    path = tmp_path / "state.json"

    path.write_text(
        "{ invalid json",
        encoding="utf-8",
    )

    store = StateStore(path)

    assert store.get_all() == {}


def test_store_handles_wrong_root_structure(tmp_path):
    path = tmp_path / "state.json"

    path.write_text(
        json.dumps(
            {
                "invalid": True,
            }
        ),
        encoding="utf-8",
    )

    store = StateStore(path)

    assert store.get_all() == {}


def test_store_handles_wrong_version(tmp_path):
    path = tmp_path / "state.json"

    path.write_text(
        json.dumps(
            {
                "version": 999,
                "signals": {},
            }
        ),
        encoding="utf-8",
    )

    store = StateStore(path)

    assert store.get_all() == {}


def test_store_uses_atomic_write(tmp_path):
    path = tmp_path / "state.json"

    store = StateStore(path)

    store.save_signal(
        SignalState(
            asset="BTCUSDT",
            decision="BUY",
            price=100000.0,
            timestamp=1700000000.0,
        )
    )

    temporary_files = list(
        tmp_path.glob("*.tmp")
    )

    assert temporary_files == []


def test_store_rejects_invalid_signal_object(tmp_path):
    store = StateStore(tmp_path / "state.json")

    with pytest.raises(TypeError):
        store.save_signal(
            "invalid"
        )


def test_store_normalizes_asset_lookup(tmp_path):
    store = StateStore(tmp_path / "state.json")

    store.save_signal(
        SignalState(
            asset="BTCUSDT",
            decision="BUY",
            price=100000.0,
            timestamp=1700000000.0,
        )
    )

    assert store.get_signal("btcusdt") is not None


def test_signal_age_is_calculated(tmp_path):
    now = 1700001000.0

    store = StateStore(
        tmp_path / "state.json",
        clock=lambda: now,
    )

    store.save_signal(
        SignalState(
            asset="BTCUSDT",
            decision="BUY",
            price=100000.0,
            timestamp=1700000000.0,
        )
    )

    assert store.signal_age(
        "BTCUSDT"
    ) == 1000.0


def test_unknown_signal_age_returns_none(tmp_path):
    store = StateStore(
        tmp_path / "state.json",
        clock=lambda: 1700001000.0,
    )

    assert store.signal_age(
        "BTCUSDT"
    ) is None


def test_signal_is_fresh(tmp_path):
    now = 1700001000.0

    store = StateStore(
        tmp_path / "state.json",
        clock=lambda: now,
    )

    store.save_signal(
        SignalState(
            asset="BTCUSDT",
            decision="BUY",
            price=100000.0,
            timestamp=1700000900.0,
        )
    )

    assert store.is_fresh(
        "BTCUSDT",
        max_age_seconds=120,
    ) is True


def test_signal_is_not_fresh_after_limit(tmp_path):
    now = 1700001000.0

    store = StateStore(
        tmp_path / "state.json",
        clock=lambda: now,
    )

    store.save_signal(
        SignalState(
            asset="BTCUSDT",
            decision="BUY",
            price=100000.0,
            timestamp=1700000000.0,
        )
    )

    assert store.is_fresh(
        "BTCUSDT",
        max_age_seconds=120,
    ) is False


def test_signal_change_detection(tmp_path):
    store = StateStore(tmp_path / "state.json")

    first = SignalState(
        asset="BTCUSDT",
        decision="BUY",
        price=100000.0,
        timestamp=1700000000.0,
    )

    second = SignalState(
        asset="BTCUSDT",
        decision="AVOID",
        price=90000.0,
        timestamp=1700000600.0,
    )

    store.save_signal(first)

    assert store.has_changed(second) is True


def test_identical_signal_is_not_changed(tmp_path):
    store = StateStore(tmp_path / "state.json")

    signal = SignalState(
        asset="BTCUSDT",
        decision="BUY",
        price=100000.0,
        timestamp=1700000000.0,
    )

    store.save_signal(signal)

    same_signal = SignalState(
        asset="BTCUSDT",
        decision="BUY",
        price=100000.0,
        timestamp=1700000600.0,
    )

    assert store.has_changed(
        same_signal
    ) is False


def test_new_signal_counts_as_changed(tmp_path):
    store = StateStore(tmp_path / "state.json")

    signal = SignalState(
        asset="BTCUSDT",
        decision="BUY",
        price=100000.0,
        timestamp=1700000000.0,
    )

    assert store.has_changed(signal) is True


def test_decision_change_counts_as_changed(tmp_path):
    store = StateStore(tmp_path / "state.json")

    store.save_signal(
        SignalState(
            asset="BTCUSDT",
            decision="WAIT_CONFIRMATION",
            price=100000.0,
            timestamp=1700000000.0,
        )
    )

    new_signal = SignalState(
        asset="BTCUSDT",
        decision="BUY",
        price=100000.0,
        timestamp=1700000600.0,
    )

    assert store.has_changed(new_signal) is True


def test_price_change_alone_does_not_change_signal(tmp_path):
    store = StateStore(tmp_path / "state.json")

    store.save_signal(
        SignalState(
            asset="BTCUSDT",
            decision="BUY",
            price=100000.0,
            timestamp=1700000000.0,
        )
    )

    new_signal = SignalState(
        asset="BTCUSDT",
        decision="BUY",
        price=101000.0,
        timestamp=1700000600.0,
    )

    assert store.has_changed(new_signal) is False


def test_store_records_last_update_time(tmp_path):
    path = tmp_path / "state.json"

    store = StateStore(
        path,
        clock=lambda: 1700001000.0,
    )

    store.save_signal(
        SignalState(
            asset="BTCUSDT",
            decision="BUY",
            price=100000.0,
            timestamp=1700000000.0,
        )
    )

    data =