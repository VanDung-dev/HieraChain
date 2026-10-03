"""Independent entity workflow state on different chains."""

from hierachain.domains.utils.cross_chain_validator import _check_logical_consistency


def test_parallel_chain_workflows_do_not_share_status_or_operation_state() -> None:
    trace = {
        "orders": [
            {"event": "operation_start", "timestamp": 1, "details": {"operation_type": "process"}},
            {"event": "status_update", "timestamp": 3, "details": {"old_status": "new", "new_status": "confirmed"}},
            {"event": "operation_complete", "timestamp": 5, "details": {"operation_type": "process"}},
        ],
        "inventory": [
            {"event": "operation_start", "timestamp": 2, "details": {"operation_type": "reserve"}},
            {"event": "status_update", "timestamp": 4, "details": {"old_status": "available", "new_status": "reserved"}},
            {"event": "operation_complete", "timestamp": 6, "details": {"operation_type": "reserve"}},
        ],
    }
    assert _check_logical_consistency(trace) == []


def test_invalid_transitions_within_one_chain_are_still_reported() -> None:
    trace = {"orders": [
        {"event": "operation_complete", "timestamp": 1, "details": {"operation_type": "process"}},
        {"event": "operation_start", "timestamp": 2, "details": {"operation_type": "process"}},
        {"event": "operation_start", "timestamp": 3, "details": {"operation_type": "process"}},
        {"event": "status_update", "timestamp": 4, "details": {"old_status": "new", "new_status": "confirmed"}},
        {"event": "status_update", "timestamp": 5, "details": {"old_status": "new", "new_status": "shipped"}},
    ]}
    assert {issue["type"] for issue in _check_logical_consistency(trace)} == {
        "operation_complete_without_start", "concurrent_operations", "status_inconsistency",
    }
