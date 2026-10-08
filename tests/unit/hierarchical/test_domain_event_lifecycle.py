"""Regression coverage for domain event state transitions and rejection."""

import copy
import json
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from hierachain.domains.chains.domain_chain import DomainChain
from hierachain.domains.chains.metrics import OperationMetricsTracker
from hierachain.domains.chains.tx_manager import TransactionManager
from hierachain.domains.events.event_creators import create_resource_allocation
from hierachain.domains.utils.cross_chain_validator import (
    CrossChainValidator,
    ProofValidator,
    _build_default_validation_rules,
)
from hierachain.serialization import loads_json


def _chain() -> DomainChain:
    chain = DomainChain.__new__(DomainChain)
    chain.name = "domain-test"
    chain.domain_type = "generic"
    chain.chain = []
    chain.pending_events = []
    chain.entity_registry = {}
    chain.domain_rules = {}
    chain.event_handlers = {}
    chain._default_event_handler_methods = {}
    chain.lock = threading.RLock()
    chain.completed_operations = 0
    chain._domain_projection_healthy = True
    chain._domain_projection_errors = []
    chain._register_default_handlers()
    chain._setup_default_business_rules()
    chain._metrics = OperationMetricsTracker()
    chain.add_event = Mock(return_value="recorded")
    return chain


def test_registration_json_restores_unicode_and_nested_values() -> None:
    chain = _chain()
    initial = {"name": "Thiết bị 🌱", "nested": {"measurements": [0.00001, 2**80 + 1, None]}}
    assert chain.register_entity("asset-1", initial)
    recorded = chain.add_event.call_args.args[0]
    assert isinstance(recorded["details"]["initial_data_json"], str)
    assert loads_json(recorded["details"]["initial_data_json"]) == initial
    chain.pending_events = [recorded]
    assert chain.rebuild_domain_state()
    assert chain.entity_registry["asset-1"]["name"] == initial["name"]
    assert chain.entity_registry["asset-1"]["nested"] == initial["nested"]


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf")])
def test_registration_rejects_values_that_cannot_round_trip(invalid: int | float) -> None:
    chain = _chain()
    assert not chain.register_entity("asset-1", {"nested": {"measurements": [invalid]}})
    chain.add_event.assert_not_called()
    assert chain.entity_registry == {}


def test_resource_lifecycle_and_unregistered_entity_rejection() -> None:
    chain = _chain()
    append = chain.add_event
    assert not chain.allocate_resource("source", "equipment", "resource-1")
    append.assert_not_called()

    assert chain.register_entity("source", {})
    assert chain.register_entity("target", {})
    append.reset_mock()

    assert chain.allocate_resource("source", "equipment", "resource-1", "reserved")
    assert chain.get_entity_info("source")["reserved_resources"] == ["resource-1"]
    assert chain.allocate_resource("source", "equipment", "resource-1", "assigned")
    assert chain.get_entity_info("source")["reserved_resources"] == []
    assert chain.get_entity_info("source")["allocated_resources"] == ["resource-1"]

    assert chain.allocate_resource(
        "source", "equipment", "resource-1", "transferred",
        details={"target_entity_id": "target"},
    )
    assert chain.get_entity_info("source")["allocated_resources"] == []
    assert chain.get_entity_info("target")["allocated_resources"] == ["resource-1"]
    assert chain.allocate_resource("target", "equipment", "resource-1", "released")
    assert chain.get_entity_info("target")["allocated_resources"] == []

    recorded = append.call_count
    assert not chain.allocate_resource("target", "equipment", "resource-1", "released")
    assert append.call_count == recorded


def test_transfer_requires_registered_target_and_does_not_append() -> None:
    chain = _chain()
    assert chain.register_entity("source", {})
    assert chain.allocate_resource("source", "equipment", "resource-1")
    append = chain.add_event
    append.reset_mock()

    missing_target = create_resource_allocation(
        "source", "equipment", "resource-1", "transferred"
    )
    assert not missing_target.is_valid()
    assert not chain.allocate_resource(
        "source", "equipment", "resource-1", "transferred",
        details={"target_entity_id": "unknown"},
    )
    append.assert_not_called()
    assert chain.get_entity_info("source")["allocated_resources"] == ["resource-1"]


def test_rejected_append_skips_metrics_and_projection_failure_is_accepted() -> None:
    chain = _chain()
    accepted_events: list[dict] = []

    def accept(event: dict) -> str:
        accepted_events.append(copy.deepcopy(event))
        chain.pending_events.append(copy.deepcopy(event))
        return "recorded"

    chain.add_event = Mock(side_effect=accept)
    assert chain.register_entity("source", {})
    chain.add_event = Mock(side_effect=OSError("journal unavailable"))

    assert not chain.perform_quality_check("source", "inspection", "passed")
    assert chain.operation_metrics["quality_checks_passed"] == 0

    chain.add_event = Mock(side_effect=accept)
    chain.event_handlers["quality_check"] = Mock(side_effect=RuntimeError("handler failed"))
    assert chain.perform_quality_check("source", "inspection", "passed")
    assert chain.operation_metrics["quality_checks_passed"] == 1
    assert not chain.domain_projection_healthy
    append_count = chain.add_event.call_count
    assert not chain.perform_quality_check("source", "inspection", "passed")
    assert chain.add_event.call_count == append_count

    chain.event_handlers["quality_check"] = chain._handle_quality_check
    assert chain.rebuild_domain_state()
    assert chain.domain_projection_healthy
    assert chain.get_entity_info("source")["last_quality_check"]["result"] == "passed"


def test_rebuild_restores_json_registration_data_and_counts_distinct_stable_events() -> None:
    chain = _chain()
    registration = {
        "event_id": "registration-1",
        "entity_id": "asset-1",
        "event": "entity_registration",
        "timestamp": 1.0,
        "details": {
            "domain_type": "generic",
            "registered_by": "domain-test",
            "initial_status": "registered",
            "initial_data_json": json.dumps({"asset_type": "equipment"}),
        },
    }
    completion = {
        "event_id": "completion-1",
        "entity_id": "asset-1",
        "event": "operation_complete",
        "timestamp": 2.0,
        "details": {"operation_type": "inspect", "result": {}},
    }
    repeated_payload = {**completion, "event_id": "completion-2"}
    chain.chain = [
        SimpleNamespace(to_event_list=lambda: [registration, completion])
    ]
    chain.pending_events = [copy.deepcopy(completion), repeated_payload]

    assert chain.rebuild_domain_state()
    assert chain.get_entity_info("asset-1")["asset_type"] == "equipment"
    assert chain.completed_operations == 2


def test_domain_operation_updates_registry_and_rejects_overlap() -> None:
    chain = _chain()
    assert chain.register_entity("asset-1", {})

    assert chain.start_domain_operation("asset-1", "inspection")
    assert chain.get_entity_info("asset-1")["current_operation"] == "inspection"
    append_count = chain.add_event.call_count

    assert not chain.start_domain_operation("asset-1", "approval")
    assert chain.add_event.call_count == append_count
    assert chain.complete_domain_operation("asset-1", "inspection")
    assert "current_operation" not in chain.get_entity_info("asset-1")


def test_approval_validation_and_append_are_serialized_with_quality_updates() -> None:
    chain = _chain()
    assert chain.register_entity("asset-1", {})
    chain.entity_registry["asset-1"]["last_quality_check"] = {"result": "passed"}
    append_order: list[str] = []
    chain.add_event = Mock(
        side_effect=lambda event: append_order.append(event["event"]) or "recorded"
    )

    validation_entered = threading.Event()
    release_validation = threading.Event()
    quality_finished = threading.Event()
    approval_results: list[bool] = []
    quality_results: list[bool] = []
    errors: list[Exception] = []
    validate = chain.validate_domain_rules

    def pause_after_approval_validation(entity_id: str, operation: str) -> bool:
        result = validate(entity_id, operation)
        validation_entered.set()
        if not release_validation.wait(timeout=2):
            raise TimeoutError("approval validation barrier was not released")
        return result

    chain.validate_domain_rules = pause_after_approval_validation

    def approve() -> None:
        try:
            approval_results.append(
                chain.process_approval(
                    "asset-1", "release", "approved", "approver-1"
                )
            )
        except Exception as error:
            errors.append(error)

    def record_failed_quality_check() -> None:
        try:
            quality_results.append(
                chain.perform_quality_check("asset-1", "inspection", "failed")
            )
        except Exception as error:
            errors.append(error)
        finally:
            quality_finished.set()

    approval_thread = threading.Thread(target=approve)
    quality_thread = threading.Thread(target=record_failed_quality_check)
    approval_thread.start()
    assert validation_entered.wait(timeout=1)
    quality_thread.start()
    quality_finished_before_release = quality_finished.wait(timeout=0.05)
    release_validation.set()
    approval_thread.join(timeout=2)
    quality_thread.join(timeout=2)

    assert not approval_thread.is_alive()
    assert not quality_thread.is_alive()
    assert not errors
    assert not quality_finished_before_release
    assert approval_results == [True]
    assert quality_results == [True]
    assert append_order == ["approval", "quality_check"]


def test_operation_validation_and_status_snapshot_share_the_chain_lock() -> None:
    chain = _chain()
    assert chain.register_entity("asset-1", {})
    append_order: list[str] = []
    chain.add_event = Mock(
        side_effect=lambda event: append_order.append(event["event"]) or "recorded"
    )

    validation_entered = threading.Event()
    release_validation = threading.Event()
    status_finished = threading.Event()
    operation_results: list[bool] = []
    status_results: list[bool] = []
    errors: list[Exception] = []
    validate = chain.validate_domain_rules

    def pause_after_start_validation(entity_id: str, operation: str) -> bool:
        result = validate(entity_id, operation)
        validation_entered.set()
        if not release_validation.wait(timeout=2):
            raise TimeoutError("operation validation barrier was not released")
        return result

    chain.validate_domain_rules = pause_after_start_validation

    def start_operation() -> None:
        try:
            operation_results.append(
                chain.start_domain_operation("asset-1", "inspection")
            )
        except Exception as error:
            errors.append(error)

    def update_status() -> None:
        try:
            status_results.append(
                chain.update_entity_status("asset-1", "unregistered")
            )
        except Exception as error:
            errors.append(error)
        finally:
            status_finished.set()

    operation_thread = threading.Thread(target=start_operation)
    status_thread = threading.Thread(target=update_status)
    operation_thread.start()
    assert validation_entered.wait(timeout=1)
    status_thread.start()
    status_finished_before_release = status_finished.wait(timeout=0.05)
    release_validation.set()
    operation_thread.join(timeout=2)
    status_thread.join(timeout=2)

    assert not operation_thread.is_alive()
    assert not status_thread.is_alive()
    assert not errors
    assert not status_finished_before_release
    assert operation_results == [True]
    assert status_results == [True]
    assert append_order == ["operation_start", "status_update"]


def test_recovery_commit_rejects_mismatched_prepared_payload_and_role() -> None:
    chain = DomainChain.__new__(DomainChain)
    chain._tx_manager = TransactionManager()
    chain._tx_commit_lock = threading.RLock()
    prepared = {
        "entity_id": "asset-1",
        "operation_type": "inspect",
        "details": {"measurements": {"count": 1}},
    }
    assert chain._tx_manager.store_pending("tx-recovery", prepared, is_source=True)

    assert not chain.recover_committed_transaction(
        "tx-recovery",
        {
            "entity_id": "asset-1",
            "operation_type": "inspect",
            "details": {"measurements": {"count": 2}},
        },
        is_source=True,
    )
    assert not chain.recover_committed_transaction(
        "tx-recovery", prepared, is_source=False
    )
    assert not chain.pending_transactions["tx-recovery"]["recovery_commit"]

    assert chain.recover_committed_transaction(
        "tx-recovery", prepared, is_source=True
    )
    assert chain.pending_transactions["tx-recovery"]["recovery_commit"]


def test_malformed_event_details_are_reported_without_crashing_logic_pass() -> None:
    validator = CrossChainValidator.__new__(CrossChainValidator)
    validator.validation_rules = _build_default_validation_rules()
    results = {"inconsistencies": []}
    trace = {
        "orders": [{
            "entity_id": "asset-1",
            "event": "operation_start",
            "timestamp": 1.0,
            "details": None,
        }]
    }

    validator._process_entity_trace(trace, results)

    assert results["inconsistent_events"] == 1
    assert [item["type"] for item in results["inconsistencies"]] == [
        "invalid_event_structure"
    ]


def test_prepared_payload_is_detached_and_different_prepare_is_rejected() -> None:
    chain = DomainChain.__new__(DomainChain)
    chain._tx_manager = TransactionManager()
    chain._tx_commit_lock = threading.RLock()
    chain._transaction_event_markers = None
    chain.entity_registry = {"asset-1": {"status": "registered"}}
    chain.domain_rules = {}
    payload = {
        "entity_id": "asset-1",
        "operation_type": "inspect",
        "details": {"measurements": {"count": 1}},
    }

    assert chain.prepare_transaction("tx-payload-snapshot", payload, True)
    payload["details"]["measurements"]["count"] = 2
    exposed = chain.pending_transactions["tx-payload-snapshot"]
    exposed["payload"]["details"]["measurements"]["count"] = 3

    stored = chain.pending_transactions["tx-payload-snapshot"]["payload"]
    assert stored["details"]["measurements"]["count"] == 1
    assert not chain.prepare_transaction("tx-payload-snapshot", payload, True)


def test_missing_proof_fields_are_inconsistent() -> None:
    validator = ProofValidator.__new__(ProofValidator)
    for details in ({}, {"sub_chain_name": "sub"}, {"proof_hash": "abc"}):
        results = {"inconsistent_proofs": 0, "inconsistencies": []}
        validator._validate_single_proof({"details": details, "timestamp": 1.0}, results)
        assert results["inconsistent_proofs"] == 1
        assert results["inconsistencies"][0]["type"] == "missing_proof_fields"
