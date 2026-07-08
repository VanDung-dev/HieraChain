"""
Test Arrow support for PolicyEngine, AuditLogger, Validator, and ErrorClassifier.

This test suite includes:
- Testing PolicyEngine's ability to evaluate conditions against Arrow objects.
- Testing AuditLogger's serialization of Arrow objects in AuditEvent details.
- Testing PolicyEngine's hashing of Arrow objects in context.
- Testing APIValidator's ability to handle Arrow objects in data validation.
- Testing ErrorClassifier's ability to sanitize Arrow metadata.
"""

import pytest
import pyarrow as pa
from unittest.mock import patch

from hierachain.security import PolicyCondition, ComparisonOperator
from hierachain.security.policy_engine import _hash_context
from hierachain.risk_management import AuditEvent, AuditEventType, AuditSeverity
from hierachain.error_mitigation import APIValidator, ErrorClassifier


def test_policy_engine_arrow_evaluation():
    """Test PolicyEngine evaluates conditions against Arrow objects."""
    # Create an Arrow Table simulating a context (StructScalar access)
    struct_array = pa.StructArray.from_arrays(
        [pa.array(["user123"]), pa.array([1000.50])],
        names=["user_id", "amount"]
    )
    scalar = struct_array[0]
    
    # ponytail: renamed transaction -> op to strictly comply with term policy
    context_arrow = {"op": scalar}
    condition_arrow = PolicyCondition(
        attribute="op.amount",
        operator=ComparisonOperator.GREATER_THAN,
        value=500.0
    )
    
    assert condition_arrow.evaluate(context_arrow) is True
    
    condition_fail = PolicyCondition(
        attribute="op.amount",
        operator=ComparisonOperator.GREATER_THAN,
        value=2000.0
    )
    assert condition_fail.evaluate(context_arrow) is False


def test_policy_engine_arrow_evaluation_null_values():
    """Test PolicyEngine evaluates conditions correctly when Arrow attributes are Null."""
    struct_array = pa.StructArray.from_arrays(
        [pa.array(["user456"]), pa.array([None], type=pa.float64())],
        names=["user_id", "amount"]
    )
    scalar = struct_array[0]
    context_arrow = {"op": scalar}
    condition = PolicyCondition(
        attribute="op.amount",
        operator=ComparisonOperator.GREATER_THAN,
        value=500.0
    )
    # Should safely return False or handle Null/None without crashing
    assert condition.evaluate(context_arrow) is False


def test_audit_logger_serialization():
    """Test AuditEvent serializes Arrow objects in details."""
    table = pa.Table.from_pydict({"col1": [1, 2], "col2": ["a", "b"]})
    
    # Using AuditEventType and AuditSeverity
    event = AuditEvent(
        event_id="test_id",
        timestamp=1.0,
        event_type=AuditEventType.SYSTEM_EVENT,
        severity=AuditSeverity.ERROR,
        source_component="test_component",
        description="Test event",
        details={"data": table},
        affected_entities=[table]
    )
    
    serialized = event.to_dict()
    
    # Check that details['data'] is a string representation of the table
    assert isinstance(serialized['details']['data'], str)
    # Representation might vary but should be string
    assert "pyarrow.Table" in serialized['details']['data'] or "Box" in serialized['details']['data'] or "Table" in serialized['details']['data']
    

def test_policy_engine_hashing():
    """Test PolicyEngine hashing handles Arrow objects."""
    # This uses the modified _hash_context with custom serializer
    table = pa.Table.from_pydict({"a": [1]})
    context = {"table": table, "id": 1}
    
    # Should not raise TypeError: Object of type Table is not JSON serializable
    hash_val = _hash_context(context)
    assert isinstance(hash_val, str)
    assert len(hash_val) > 0


def test_validator_sanitization():
    """Test APIValidator handles Arrow objects."""
    table = pa.Table.from_pydict({"a": [1]})
    
    validator = APIValidator({})
    # validate_endpoint_data works on Arrow objects according to file snippet
    result = validator.validate_endpoint_data(table)
    assert result is True
    
    # Test forbidden term in schema
    table_forbidden = pa.Table.from_pydict({"mining": [1]})
    from hierachain.error_mitigation.validator import ValidationError
    with pytest.raises(ValidationError):
        validator.validate_endpoint_data(table_forbidden)


def test_error_classifier_sanitization():
    """Test ErrorClassifier sanitizes Arrow metadata."""
    classifier = ErrorClassifier({})
    table = pa.Table.from_pydict({"a": [1]})
    metadata = {"info": table}
    
    # accessing private method or via classify_error
    # classify_error takes a dict
    error_data = {
        "error_type": "test_error",
        "message": "Something went wrong",
        "metadata": metadata
    }

    # We need to mock _log_classification because it writes to file/logger
    with patch('hierachain.error_mitigation.error_classifier._log_classification'):
        error_info = classifier.classify_error(error_data)
        
        # error_info.metadata should be sanitized
        sanitized = error_info.metadata
        assert isinstance(sanitized["info"], list)