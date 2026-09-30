"""Regression coverage for domain event state transitions and rejection."""

from unittest.mock import Mock

from hierachain.domains.chains.domain_chain import DomainChain
from hierachain.domains.chains.metrics import OperationMetricsTracker
from hierachain.domains.events.event_creators import create_resource_allocation
from hierachain.domains.utils.cross_chain_validator import ProofValidator


def _chain() -> DomainChain:
    chain = DomainChain.__new__(DomainChain)
    chain.name = "domain-test"
    chain.domain_type = "generic"
    chain.entity_registry = {}
    chain.event_handlers = {}
    chain._register_default_handlers()
    chain._metrics = OperationMetricsTracker()
    chain.add_event = Mock(return_value="recorded")
    return chain


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


def test_failed_domain_event_does_not_increment_metrics() -> None:
    chain = _chain()
    assert chain.register_entity("source", {})
    chain.add_event = Mock(side_effect=OSError("journal unavailable"))

    assert not chain.perform_quality_check("source", "inspection", "passed")
    assert chain.operation_metrics["quality_checks_passed"] == 0

    chain.add_event = Mock(return_value="recorded")
    chain.event_handlers["quality_check"] = Mock(side_effect=RuntimeError("handler failed"))
    assert not chain.perform_quality_check("source", "inspection", "passed")
    assert chain.operation_metrics["quality_checks_passed"] == 0


def test_missing_proof_fields_are_inconsistent() -> None:
    validator = ProofValidator.__new__(ProofValidator)
    for details in ({}, {"sub_chain_name": "sub"}, {"proof_hash": "abc"}):
        results = {"inconsistent_proofs": 0, "inconsistencies": []}
        validator._validate_single_proof({"details": details, "timestamp": 1.0}, results)
        assert results["inconsistent_proofs"] == 1
        assert results["inconsistencies"][0]["type"] == "missing_proof_fields"
