"""Regression coverage for ERP transformers and scheduler status snapshots."""

import subprocess
import sys
from typing import Any

import pytest

from hierachain.core.utils import validate_event_structure
from hierachain.integration import EnterpriseIntegration, IntegrationError
from hierachain.integration.erp.change_detector import ChangeDetector
from hierachain.integration.erp.scheduler import SyncScheduler
from hierachain.integration.erp_ledger import (
    ERPIntegrationLedger,
    EventTranslator,
    MappingEngine,
    create_sap_integration_profile,
)
from hierachain.integration.types import SyncResult, SyncStatus


class _ManualTimer:
    """Timer test double that records deadlines without starting threads."""

    def __init__(self, interval: float, function: Any, args: tuple[Any, ...]) -> None:
        self.interval = interval
        self.function = function
        self.args = args
        self.daemon = False
        self.started = False
        self.cancelled = False

    def start(self) -> None:
        self.started = True

    def cancel(self) -> None:
        self.cancelled = True


def _failed_sync(profile_name: str, events_processed: int = 0) -> SyncResult:
    return SyncResult(
        profile_name=profile_name,
        status=SyncStatus.FAILED,
        events_processed=events_processed,
        errors=["synthetic sink failure"],
        start_time=100.0,
        end_time=101.0,
    )


def test_sap_profile_transforms_status_quantity_and_date() -> None:
    integration = ERPIntegrationLedger()
    profile = create_sap_integration_profile("sap-materials", {})
    try:
        integration.create_mapping_profile(
            profile["profile_name"], profile["erp_system"], profile["mapping_rules"],
        )
        event = integration.translate_erp_to_blockchain({
            "material": {
                "document_number": "DOC-001",
                "event_type": "created",
                "id": "MAT-001",
                "quantity": "12.50",
                "timestamp": "20260930123045",
            },
        }, "sap-materials")

        assert event["entity_id"] == "DOC-001"
        assert event["event"] == "creation"
        assert event["details"] == {
            "material_id": "MAT-001",
            "quantity": 12.5,
            "timestamp": "2026-09-30T12:30:45",
        }
    finally:
        integration.sync_scheduler.shutdown()


def test_sap_profile_registration_preserves_and_isolates_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    integration = ERPIntegrationLedger()
    config = {"endpoint": {"base_url": "https://erp.example.invalid", "tenant": "A"}}
    profile = create_sap_integration_profile("sap-profile", config)
    input_rules = profile["mapping_rules"]
    input_key_fields = profile["key_fields"]
    records = [
        {
            "material": {
                "document_number": "DOC-1",
                "event_type": "created",
                "id": "MAT-1",
                "quantity": "1.5",
                "timestamp": "20261003120000",
            }
        },
        {
            "material": {
                "document_number": "DOC-2",
                "event_type": "updated",
                "id": "MAT-2",
                "quantity": "2.5",
                "timestamp": "20261003120100",
            }
        },
    ]
    adapter_configs: list[dict[str, Any]] = []
    scheduled_tasks: list[Any] = []
    accepted_events: list[dict[str, Any]] = []

    class FixtureAdapter:
        def __init__(self, adapter_config: dict[str, Any]) -> None:
            adapter_configs.append(adapter_config)

        def get_changes_since_last_sync(self) -> list[dict[str, Any]]:
            return records

    class Sink:
        def add_event(self, event: dict[str, Any]) -> str:
            accepted_events.append(event)
            return f"accepted-{len(accepted_events)}"

    try:
        integration.register_adapter("sap", FixtureAdapter)
        integration.create_mapping_profile(
            profile["profile_name"],
            profile["erp_system"],
            profile["mapping_rules"],
            config=profile["config"],
            detect_changes=profile["detect_changes"],
            key_fields=profile["key_fields"],
        )

        config["endpoint"]["tenant"] = "mutated"
        input_rules["details.material_id"] = "material.changed_id"
        input_key_fields[0] = "missing.path"
        stored_profile = integration.mapping_engine.get_profile("sap-profile")
        assert stored_profile is not None
        assert stored_profile["config"]["endpoint"]["tenant"] == "A"
        assert stored_profile["mapping_rules"]["details.material_id"] == "material.id"
        assert stored_profile["detect_changes"] is True
        assert stored_profile["key_fields"] == ["material.document_number"]

        stored_profile["config"]["endpoint"]["tenant"] = "mutated-read"
        assert (
            integration.mapping_engine.get_profile("sap-profile")["config"]["endpoint"]["tenant"]
            == "A"
        )

        monkeypatch.setattr(
            integration.sync_scheduler,
            "schedule_task",
            lambda _name, task, _interval: scheduled_tasks.append(task) or "test-task",
        )
        integration.start_scheduled_sync("sap-profile", 60, chain=Sink())
        result = scheduled_tasks[0]()

        assert adapter_configs == [
            {"endpoint": {"base_url": "https://erp.example.invalid", "tenant": "A"}}
        ]
        assert result.status == SyncStatus.COMPLETED
        assert result.events_processed == 2
        assert len(accepted_events) == 2
        assert set(integration.change_detector.previous_states) == {
            "sap-profile:DOC-1",
            "sap-profile:DOC-2",
        }
    finally:
        integration.sync_scheduler.shutdown()


def test_change_detector_ignores_its_metadata_and_scopes_keys_by_profile() -> None:
    detector = ChangeDetector()
    sap_profile = {
        "profile_name": "sap-profile",
        "erp_system": "sap",
        "key_fields": ["material.document_number"],
    }
    record = {"material": {"document_number": "DOC-1", "quantity": 5}}

    first = detector.detect_changes(record, sap_profile)
    assert first["change_detected"] is True
    second = detector.detect_changes(record, sap_profile)
    same_entity_other_profile = detector.detect_changes(
        {"material": {"document_number": "DOC-1", "quantity": 5}},
        {**sap_profile, "profile_name": "sap-archive"},
    )

    assert second["change_detected"] is False
    assert "changes" not in second
    assert same_entity_other_profile["changes"] == {"type": "new_entity"}
    assert set(detector.previous_states) == {"sap-profile:DOC-1", "sap-archive:DOC-1"}


def test_scheduled_sync_requires_a_sink_before_fetching_records() -> None:
    integration = ERPIntegrationLedger()

    class Adapter:
        called = False

        def get_changes_since_last_sync(self) -> list[dict[str, Any]]:
            self.called = True
            return [{"id": "record-1"}]

    adapter = Adapter()
    try:
        result = integration._execute_sync("profile", {}, adapter, chain=None)
        assert result.status == SyncStatus.FAILED
        assert result.events_processed == 0
        assert "chain sink" in result.errors[0]
        assert adapter.called is False
        with pytest.raises(IntegrationError, match="chain sink"):
            integration.start_scheduled_sync("profile", 60)
    finally:
        integration.sync_scheduler.shutdown()


def test_scheduled_sync_persists_partial_delivery_failure_and_retries() -> None:
    now = [1000.0]
    timers: list[_ManualTimer] = []
    integration = ERPIntegrationLedger()
    integration.sync_scheduler.shutdown()
    scheduler = SyncScheduler(
        clock=lambda: now[0],
        timer_factory=lambda interval, function, args: (
            timers.append(_ManualTimer(interval, function, args)) or timers[-1]
        ),
    )
    integration.sync_scheduler = scheduler
    submitted: list[dict[str, Any]] = []

    class Adapter:
        def __init__(self, _config: dict[str, Any]) -> None:
            pass

        def get_changes_since_last_sync(self) -> list[dict[str, Any]]:
            return [
                {"id": "record-1", "entity_id": "ITEM-1", "event": "created"},
                {"id": "record-2", "entity_id": "ITEM-2", "event": "updated"},
            ]

    class Sink:
        def add_event(self, event: dict[str, Any]) -> str:
            submitted.append(event)
            if len(submitted) == 2:
                raise RuntimeError("storage rejected record")
            return "accepted-record-1"

    try:
        integration.register_adapter("fixture", Adapter)
        integration.create_mapping_profile(
            "partial-profile",
            "fixture",
            {"entity_id": "entity_id", "event": "event"},
        )
        integration.start_scheduled_sync("partial-profile", 600, chain=Sink())
        task = scheduler.tasks["partial-profile"]
        generation = task["generation"]
        assert timers[0].interval == 600
        scheduler._run_task_execution("partial-profile", generation)

        status = integration.get_sync_status("partial-profile")
        assert status["status"] == "failed"
        assert status["events_processed"] == 1
        assert status["retry_count"] == 1
        assert status["next_sync"] == now[0] + 30
        assert len(status["errors"]) == 1
        assert "record-2" in status["errors"][0]
        assert "storage rejected record" in status["errors"][0]
        assert len(submitted) == 2
    finally:
        scheduler.shutdown()


def test_scheduler_retry_backoff_is_bounded_and_visible() -> None:
    now = [2000.0]
    timers: list[_ManualTimer] = []
    scheduler = SyncScheduler(
        clock=lambda: now[0],
        timer_factory=lambda interval, function, args: (
            timers.append(_ManualTimer(interval, function, args)) or timers[-1]
        ),
    )
    try:
        scheduler.schedule_task("profile", lambda: _failed_sync("profile", 2), 900)
        task = scheduler.tasks["profile"]
        task["max_retries"] = 2
        generation = task["generation"]

        for expected_retry, delay in ((1, 30), (2, 60)):
            scheduler._run_task_execution("profile", generation)
            status = scheduler.get_status("profile")
            assert status["status"] == "failed"
            assert status["events_processed"] == 2
            assert status["errors"] == ["synthetic sink failure"]
            assert status["retry_count"] == expected_retry
            assert status["next_sync"] == now[0] + delay
            assert timers[-1].interval == delay
            now[0] += delay

        scheduler._run_task_execution("profile", generation)
        exhausted = scheduler.get_status("profile")
        assert exhausted["status"] == "failed"
        assert exhausted["retry_count"] == 2
        assert exhausted["retry_exhausted"] is True
        assert exhausted["next_sync"] is None
        assert len(timers) == 3
    finally:
        scheduler.shutdown()


def test_scheduler_cancels_replaced_timer_and_rejects_stale_generations() -> None:
    timers: list[_ManualTimer] = []
    scheduler = SyncScheduler(
        clock=lambda: 3000.0,
        timer_factory=lambda interval, function, args: (
            timers.append(_ManualTimer(interval, function, args)) or timers[-1]
        ),
    )
    calls: list[str] = []
    success = SyncResult("profile", SyncStatus.COMPLETED, 1)
    try:
        old_id = scheduler.schedule_task(
            "profile", lambda: calls.append("old") or success, 60
        )
        old_generation = scheduler.tasks["profile"]["generation"]
        old_timer = timers[-1]

        new_id = scheduler.schedule_task(
            "profile", lambda: calls.append("new") or success, 60
        )
        new_generation = scheduler.tasks["profile"]["generation"]
        assert old_id != new_id
        assert old_generation != new_generation
        assert old_timer.cancelled is True

        old_timer.function(*old_timer.args)
        scheduler._run_task_execution("profile", old_generation)
        scheduler._handle_execution_result(
            "profile", _failed_sync("profile"), old_generation
        )
        assert calls == []
        assert scheduler.get_status("profile")["status"] == "idle"
        assert len(timers) == 2

        scheduler._run_task_execution("profile", new_generation)
        assert calls == ["new"]
        assert scheduler.get_status("profile")["status"] == "completed"
        assert len(timers) == 3
        assert scheduler.stop_task("profile") is True
        assert timers[-1].cancelled is True
    finally:
        scheduler.shutdown()


def test_manual_retry_invalidates_old_timer_and_rejects_active_overlap() -> None:
    timers: list[_ManualTimer] = []
    scheduler = SyncScheduler(
        clock=lambda: 4000.0,
        timer_factory=lambda interval, function, args: (
            timers.append(_ManualTimer(interval, function, args)) or timers[-1]
        ),
    )
    calls: list[str] = []
    try:
        scheduler.schedule_task(
            "profile",
            lambda: calls.append("run") or SyncResult("profile", SyncStatus.COMPLETED, 0),
            60,
        )
        original_timer = timers[-1]
        generation = scheduler.tasks["profile"]["generation"]

        scheduler.schedule_retry("profile")
        retry_timer = timers[-1]
        assert original_timer.cancelled is True
        assert retry_timer.interval == 30
        original_timer.function(*original_timer.args)
        assert calls == []
        assert scheduler.get_status("profile")["retry_count"] == 1

        scheduler.tasks["profile"]["status"] = SyncStatus.SYNCING
        scheduler.schedule_retry("profile")
        assert len(timers) == 2
        assert retry_timer.cancelled is False
        assert scheduler.tasks["profile"]["generation"] == generation
    finally:
        scheduler.shutdown()


@pytest.mark.parametrize(
    ("erp_system", "fixture_path"),
    [
        ("sap", "material"),
        ("oracle", "record"),
        ("microsoft_dynamics", "sales"),
    ],
)
def test_exported_erp_fixture_connectors_require_explicit_simulation_opt_in(
    erp_system: str, fixture_path: str
) -> None:
    with pytest.raises(IntegrationError, match="simulation-only"):
        EnterpriseIntegration.connect_to_erp(
            erp_system,
            {
                "url": "https://erp.example.invalid",
                "username": "synthetic-user",
                "password": "synthetic-password",
            },
        )

    connector = EnterpriseIntegration.connect_to_erp(
        erp_system, {"simulation_mode": True}
    )
    assert connector.is_connected() is True
    events = connector.get_events()
    assert len(events) == 1
    assert fixture_path in events[0]


@pytest.mark.parametrize(
    ("erp_system", "erp_event", "details"),
    [
        (
            "sap",
            {
                "material": {
                    "document_number": "MAT-1",
                    "event_type": "material_receipt",
                    "id": "MATERIAL-1",
                    "quantity": 4,
                }
            },
            {"material_id": "MATERIAL-1", "quantity": 4},
        ),
        (
            "oracle",
            {
                "record": {
                    "id": "REC-1",
                    "type": "purchase_order",
                    "total_value": 50,
                    "vendor": "VENDOR-1",
                }
            },
            {"total_value": 50, "vendor": "VENDOR-1"},
        ),
        (
            "microsoft_dynamics",
            {
                "sales": {
                    "order_id": "SO-1",
                    "event_type": "order_created",
                    "customer": "CUSTOMER-1",
                    "total": 25,
                }
            },
            {"customer": "CUSTOMER-1", "total": 25},
        ),
    ],
)
def test_legacy_default_mappings_create_nested_valid_events(
    erp_system: str, erp_event: dict[str, Any], details: dict[str, Any]
) -> None:
    converted = EnterpriseIntegration.erp_to_blockchain_event(
        erp_event, EnterpriseIntegration.create_default_mapping(erp_system)
    )

    assert converted["entity_id"]
    assert converted["event"]
    assert converted["details"] == details
    assert not any("." in key for key in converted)
    assert validate_event_structure(converted) is True


def test_registered_transformer_receives_profile_parameters() -> None:
    integration = ERPIntegrationLedger()
    calls: list[tuple[Any, dict[str, Any] | None]] = []

    def scale_quantity(value: Any, params: dict[str, Any] | None) -> float:
        calls.append((value, params))
        assert params is not None
        return float(value) * params["factor"]

    try:
        integration.mapping_engine.register_transformer("scale", scale_quantity)
        integration.create_mapping_profile("custom", "generic", {
            "entity_id": "id",
            "details.quantity": {
                "source_path": "quantity",
                "transformer": "scale",
                "params": {"factor": 2},
            },
        })
        event = integration.translate_erp_to_blockchain({"id": "E1", "quantity": "3.5"}, "custom")
        assert event["details"]["quantity"] == 7.0
        assert calls == [("3.5", {"factor": 2})]
    finally:
        integration.sync_scheduler.shutdown()


def test_scheduler_task_snapshots_complete_without_nested_lock() -> None:
    script = """
from unittest.mock import patch
from hierachain.integration.erp.scheduler import SyncScheduler

scheduler = SyncScheduler()
try:
    assert scheduler.get_all_tasks() == []
    assert scheduler.get_status('missing') == {'error': 'Task not found'}
    with patch.object(scheduler, '_schedule_next_execution'):
        scheduler.schedule_task('sap-materials', lambda: None, 60)
        scheduler.schedule_task('custom', lambda: None, 120)
    snapshot = scheduler.get_all_tasks()
    assert snapshot == [scheduler.get_status('sap-materials'), scheduler.get_status('custom')]
    snapshot[0]['status'] = 'changed'
    assert scheduler.get_status('sap-materials')['status'] == 'idle'
    assert scheduler.stop_task('sap-materials')
    assert len(scheduler.get_all_tasks()) == 1
    assert scheduler.stop_task('custom')
    assert scheduler.get_all_tasks() == []
finally:
    scheduler.shutdown()
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=5,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("registered", [False, True])
def test_unavailable_or_failed_transformer_never_returns_unconverted_value(
    registered: bool, caplog: pytest.LogCaptureFixture,
) -> None:
    engine = MappingEngine()

    def fail_conversion(value: Any, params: dict[str, Any] | None) -> Any:
        raise ValueError("conversion failed")

    if registered:
        engine.register_transformer("convert", fail_conversion)
    translator = EventTranslator(engine)
    event = translator.translate({"id": "E1", "quantity": "invalid"}, {
        "entity_id": "id",
        "details.quantity": {"source_path": "quantity", "transformer": "convert"},
    })
    assert event["entity_id"] == "E1"
    assert "details" not in event
    assert "Failed to map field details.quantity" in caplog.text
