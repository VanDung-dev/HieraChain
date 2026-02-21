"""
Property-based fuzzing tests for HieraChain input validation.

Uses Hypothesis to generate random inputs and verify robust handling.
"""

import os
import shutil
import time
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

from hierachain.consensus import (
    OrderingService,
    OrderingNode,
    OrderingStatus,
)


# === Strategy Definitions ===

# Valid event-like dict
valid_event_strategy = st.fixed_dictionaries({
    "entity_id": st.text(min_size=1, max_size=100),
    "event": st.text(min_size=1, max_size=100),
    "timestamp": st.floats(min_value=0, max_value=2**31),
})

# Arbitrary dict (for chaos testing)
arbitrary_dict_strategy = st.dictionaries(
    keys=st.text(max_size=50),
    values=st.one_of(
        st.none(),
        st.booleans(),
        st.integers(),
        st.floats(allow_nan=False),
        st.text(max_size=100),
    ),
    max_size=20,
)


# === Helper Functions ===

def create_ordering_service():
    """Create OrderingService for fuzzing."""
    
    # Use project data directory to satisfy security constraints
    data_dir = os.path.join(os.getcwd(), "data", "test_fuzzing")
    os.makedirs(data_dir, exist_ok=True)

    node = OrderingNode(
        node_id="fuzz-node",
        endpoint="localhost:9999",
        is_leader=True,
        weight=1.0,
        status=OrderingStatus.ACTIVE,
        last_heartbeat=time.time()
    )
    config = {"storage_dir": data_dir}
    return OrderingService(nodes=[node], config=config)


def cleanup_service(service):
    """Cleanup OrderingService after test."""
    
    service.shutdown()
    data_dir = os.path.join(os.getcwd(), "data", "test_fuzzing")
    if os.path.exists(data_dir):
        shutil.rmtree(data_dir, ignore_errors=True)


# === Fuzzing Tests ===

@given(event_data=arbitrary_dict_strategy)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
def test_receive_event_handles_arbitrary_dict(event_data):
    """Verify receive_event doesn't crash on arbitrary dict input."""
    service = create_ordering_service()
    try:
        service.receive_event(event_data, "fuzz-channel", "fuzz-org")
    except (ValueError, TypeError, RuntimeError, PermissionError):
        pass  # Expected for invalid input
    except Exception as e:
        cleanup_service(service)
        pytest.fail(f"Unexpected exception: {type(e).__name__}: {e}")
    finally:
        cleanup_service(service)


@given(channel_id=st.text(max_size=100), org=st.text(max_size=100))
@settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow], deadline=None)
def test_receive_event_handles_arbitrary_strings(channel_id, org):
    """Verify channel_id and org string validation."""
    service = create_ordering_service()
    try:
        event = {"entity_id": "test", "event": "fuzz", "timestamp": time.time()}
        service.receive_event(event, channel_id, org)
    except (ValueError, TypeError, RuntimeError, PermissionError):
        pass
    finally:
        cleanup_service(service)


@given(
    non_dict=st.one_of(
        st.none(),
        st.integers(),
        st.text(max_size=50),
        st.lists(st.integers(), max_size=5),
    )
)
@settings(max_examples=30)
def test_receive_event_rejects_non_dict(non_dict):
    """Verify non-dict input is rejected with ValueError."""
    service = create_ordering_service()
    try:
        with pytest.raises((ValueError, TypeError)):
            service.receive_event(non_dict, "channel", "org")
    finally:
        cleanup_service(service)


@given(
    timestamp=st.one_of(
        st.none(),
        st.text(max_size=20),
        st.floats(allow_nan=True, allow_infinity=True),
        st.integers(min_value=-10**10, max_value=10**15),
    )
)
@settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow], deadline=None)
def test_receive_event_handles_invalid_timestamp(timestamp):
    """Verify handling of invalid timestamp values."""
    service = create_ordering_service()
    try:
        event = {"entity_id": "test", "event": "fuzz", "timestamp": timestamp}
        service.receive_event(event, "channel", "org")
    except (ValueError, TypeError, RuntimeError, PermissionError):
        pass  # Expected for invalid timestamp
    finally:
        cleanup_service(service)
