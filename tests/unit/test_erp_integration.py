"""Regression coverage for ERP transformers and scheduler status snapshots."""

import subprocess
import sys
from typing import Any

import pytest

from hierachain.integration.erp_ledger import (
    ERPIntegrationLedger,
    EventTranslator,
    MappingEngine,
    create_sap_integration_profile,
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
