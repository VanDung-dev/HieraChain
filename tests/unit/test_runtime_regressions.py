"""P2 regressions for exported validation, monitoring and network paths."""

import asyncio
import threading
import time
from pathlib import Path

import pyarrow as pa
import pytest
import zmq

from hierachain.core.block import convert_events_to_arrow
from hierachain.error_mitigation.data_validator import (
    DataValidator,
    ValidationLevel,
    validate_consistency,
)
from hierachain.error_mitigation.error_classifier import ErrorClassifier
from hierachain.error_mitigation.journal import TransactionJournal
from hierachain.monitoring.alert_system import AlertManager
from hierachain.monitoring.types import (
    AlertSeverity,
    MetricType,
    MetricUnit,
    PerformanceMetric,
)
from hierachain.network.zmq_transport import (
    MAX_MESSAGE_BYTES,
    MAX_REPLAY_ENTRIES,
    ZmqNode,
    _handle_received_message,
)


@pytest.mark.parametrize("level", list(ValidationLevel))
def test_arrow_schema_rejects_incompatible_types(level: ValidationLevel) -> None:
    table = pa.table({"entity_id": [1], "event": [2], "timestamp": ["later"]})
    assert not DataValidator(level).validate_table(table).is_valid


def test_consistency_checks_values_order_and_serialized_details() -> None:
    events = [{"entity_id": "E", "event": "created", "timestamp": 1, "details": {"x": 1}}]
    table = pa.table({"entity_id": ["E"], "event": ["created"], "timestamp": [1.0], "details": ['{"x":1}']})
    assert validate_consistency(events, table).is_valid
    events[0]["entity_id"] = "other"
    result = validate_consistency(events, table)
    assert not result.is_valid
    assert "Row[0]" in result.errors[0]


def test_consistency_uses_the_canonical_arrow_event_representation() -> None:
    events = [{"entity_id": "E", "event": "created", "timestamp": 1.0,
               "details": {"x": 1, "nested": {"y": True}}, "extra": "preserved in payload"}]
    table = convert_events_to_arrow(events)
    assert validate_consistency(events, table).is_valid
    index = table.schema.get_field_index("details")
    tampered = table.set_column(index, table.schema.field(index),
                               pa.array([[('x', 'tampered')]], type=table.schema.field(index).type))
    assert not validate_consistency(events, tampered).is_valid
    events[0]["extra"] = "changed"
    assert not validate_consistency(events, table).is_valid


def test_journal_rejects_ancestor_and_dangling_symlinks(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "data" / "alias").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="Security"):
        TransactionJournal("data/alias/journal")
    assert not (outside / "journal").exists()
    (tmp_path / "data" / "journal").mkdir()
    (tmp_path / "data" / "journal" / "current.arrow").symlink_to(outside / "missing")
    with pytest.raises(ValueError, match="Security"):
        TransactionJournal()


def test_key_security_error_triggers_configured_lockdown(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    received = []
    classifier = ErrorClassifier({}, lockdown_callback=received.append)
    info = classifier.classify_error({"error_type": "encryption key error", "message": "key error"})
    assert received == [info]


@pytest.mark.parametrize("value, expected", [(100, "normal"), (94, "warning"), (89, "critical")])
def test_success_rate_thresholds_use_low_is_bad(value: float, expected: str) -> None:
    metric = PerformanceMetric("success", MetricType.CONSENSUS, MetricUnit.PERCENTAGE, "rate",
                               threshold_warning=95, threshold_critical=90, low_is_bad=True)
    metric.add_value(value)
    assert metric.is_threshold_exceeded()[1] == expected


def test_critical_cpu_alert_upgrades_warning_and_notification_does_not_block() -> None:
    started = threading.Event()
    release = threading.Event()
    manager = AlertManager()
    for rule in manager.alert_rules.values():
        rule.escalation_time = 0

    class SlowNotifier:
        def send_alert(self, alert) -> bool:
            started.set()
            assert release.wait(2)
            return True

    manager.notifiers = [SlowNotifier()]
    try:
        manager.check_metric("cpu_usage", 86)
        assert started.wait(1)
        manager.check_metric("cpu_usage", 99)
        # This line is reachable while delivery remains blocked on release.
        assert not release.is_set()
        active = [alert for alert in manager.active_alerts.values() if alert.status.value == "active"]
        assert len(active) == 1
        assert active[0].severity == AlertSeverity.CRITICAL
    finally:
        release.set()
        manager.close()


@pytest.mark.asyncio
async def test_network_replay_cache_isolated_and_rejects_unverified_input() -> None:
    import orjson

    node = ZmqNode("receiver", 0)
    received = []
    node.set_handler(lambda message, sender: received.append(sender))
    node.set_message_validator(lambda message, sender: message.get("verified") is True)
    now = time.time()
    try:
        for index in range(MAX_REPLAY_ENTRIES + 1):
            payload = orjson.dumps({"timestamp": now, "nonce": str(index), "verified": False})
            await _handle_received_message(node, [b"untrusted", payload])
        assert node.peer_replay_buffers == {}
        node.peer_replay_buffers["busy"] = {(now, str(i)) for i in range(MAX_REPLAY_ENTRIES)}
        await _handle_received_message(node, [b"busy", orjson.dumps(
            {"timestamp": now, "nonce": "overflow", "verified": True})])
        await _handle_received_message(node, [b"healthy", orjson.dumps(
            {"timestamp": now, "nonce": "accepted", "verified": True})])
        assert received == ["healthy"]
        await _handle_received_message(node, [b"healthy", b"x" * (MAX_MESSAGE_BYTES + 1)])
        await _handle_received_message(node, [b"healthy", b"", b"{}"])
        assert received == ["healthy"]
    finally:
        await node.stop()


@pytest.mark.asyncio
async def test_receiving_socket_sets_message_size_bound() -> None:
    node = ZmqNode("size-bound", 0)
    await node.start()
    try:
        assert node.router.getsockopt(zmq.MAXMSGSIZE) == MAX_MESSAGE_BYTES
    finally:
        await node.stop()
        await asyncio.sleep(0)
