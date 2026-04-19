"""
Data Validator for HieraChain Ledger

This module provides data validation utilities for Arrow tables and events,
ensuring data integrity and schema compliance.
"""

import time
import json
import logging
from enum import Enum
from typing import Any, Callable, Tuple
from dataclasses import dataclass, field

import pyarrow as pa

logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    """Validation strictness levels."""
    STRICT = "strict"      # All validation rules enforced
    RELAXED = "relaxed"    # Required fields only
    LENIENT = "lenient"    # Basic type checking only


@dataclass
class ValidationResult:
    """Result of a validation operation."""
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    auto_fixed: list[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        """Add an error message."""
        self.is_valid = False
        self.errors.append(message)
    
    def add_warning(self, message: str) -> None:
        """Add a warning message."""
        self.warnings.append(message)
    
    def add_fix(self, message: str) -> None:
        """Record an auto-fix that was applied."""
        self.auto_fixed.append(message)
    
    def merge(self, other: 'ValidationResult') -> None:
        """Merge another ValidationResult into this one."""
        if not other.is_valid:
            self.is_valid = False
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.auto_fixed.extend(other.auto_fixed)


class DataValidator:
    """
    Validates event data and Arrow tables.
    
    Features:
        - Schema compliance checking
        - Required field validation
        - Type checking
        - Custom validators
        - Auto-fix capabilities
    """
    
    # Required fields for events
    REQUIRED_FIELDS = ['entity_id', 'event', 'timestamp']
    
    # Field type expectations
    FIELD_TYPES: dict[str, Any] = {
        'entity_id': str,
        'event': str,
        'timestamp': (int, float),
        'details': (dict, type(None)),
    }

    def __init__(
        self,
        level: ValidationLevel = ValidationLevel.RELAXED,
        auto_fix: bool = False,
        custom_validators: dict[str, Callable] | None = None
    ):
        """
        Initialize validator.
        
        Args:
            level: Validation strictness level
            auto_fix: Whether to attempt auto-fixing issues
            custom_validators: Dict of field_name -> validator_function
        """
        self.level = level
        self.auto_fix = auto_fix
        self.custom_validators = custom_validators or {}
    
    def validate_event(
        self, event: dict[str, Any], index: int = 0
    ) -> Tuple[ValidationResult, dict[str, Any]]:
        """
        Validate a single event dict.
        
        Args:
            event: Event dictionary to validate
            index: Index for error messaging
            
        Returns:
            Tuple of (ValidationResult, possibly_fixed_event)
        """
        result = ValidationResult(is_valid=True)
        fixed_event = event.copy()
        
        # Delegate specific validation tasks to private helper methods
        self._validate_required_fields(fixed_event, index, result)
        self._validate_field_types(fixed_event, index, result)
        self._validate_strict_constraints(fixed_event, index, result)
        self._run_custom_validators(fixed_event, index, result)
        
        return result, fixed_event

    def _validate_required_fields(
        self, event: dict[str, Any], index: int, result: ValidationResult
    ) -> None:
        """Check for mandatory fields and perform auto-fixes if possible."""
        for fld in self.REQUIRED_FIELDS:
            self._check_single_required_field(event, index, result, fld)

    def _check_single_required_field(
        self,
        event: dict[str, Any],
        index: int,
        result: ValidationResult,
        fld: str
    ) -> None:
        """Check availability of a single required field."""
        if fld in event and event[fld] is not None:
            return

        if self.auto_fix and fld == 'timestamp':
            event['timestamp'] = time.time()
            result.add_fix(f"Event[{index}]: Auto-added timestamp")
        else:
            result.add_error(f"Event[{index}]: Missing required field '{fld}'")

    def _validate_field_types(
        self, event: dict[str, Any], index: int, result: ValidationResult
    ) -> None:
        """Validate all field types based on FIELD_TYPES mapping."""
        if self.level not in (ValidationLevel.STRICT, ValidationLevel.RELAXED):
            return

        for fld, expected_types in self.FIELD_TYPES.items():
            self._check_single_field_type(event, index, result, fld, expected_types)

    def _check_single_field_type(
        self,
        event: dict[str, Any],
        index: int,
        result: ValidationResult,
        fld: str,
        expected_types: Any
    ) -> None:
        """Check type of a single field if present."""
        if fld not in event or event[fld] is None:
            return
            
        if not isinstance(event[fld], expected_types):
            self._handle_type_fix(event, index, result, fld, expected_types)

    def _handle_type_fix(
        self,
        event: dict[str, Any],
        index: int,
        result: ValidationResult,
        fld_name: str,
        expected_types: Any
    ) -> None:
        """Attempt to fix common type mismatches."""
        actual_type = type(event[fld_name]).__name__
        if self.auto_fix and fld_name == 'entity_id':
            event['entity_id'] = str(event['entity_id'])
            result.add_fix(f"Event[{index}]: Converted entity_id to string")
        elif self.auto_fix and fld_name == 'timestamp':
            try:
                event['timestamp'] = float(event['timestamp'])
                result.add_fix(f"Event[{index}]: Converted timestamp to float")
            except (ValueError, TypeError):
                result.add_error(f"Event[{index}]: Cannot convert timestamp")
        else:
            msg = (
                f"Event[{index}]: Field '{fld_name}' "
                f"expected {expected_types}, got {actual_type}"
            )
            result.add_error(msg)

    def _validate_strict_constraints(
        self, event: dict[str, Any], index: int, result: ValidationResult
    ) -> None:
        """Additional integrity checks for STRICT validation level."""
        if self.level != ValidationLevel.STRICT:
            return

        _check_strict_id_and_type(event, index, result)
        _check_strict_timestamp(event, index, result)
        _check_strict_details(event, index, result)

    def _run_custom_validators(
        self, event: dict[str, Any], index: int, result: ValidationResult
    ) -> None:
        """Run any externally provided custom validation functions."""
        for fld, validator in self.custom_validators.items():
            _run_single_custom_validator(event, index, result, fld, validator)

    def validate_events_batch(
        self,
        events: list[dict[str, Any]]
    ) -> Tuple[ValidationResult, list[dict[str, Any]]]:
        """
        Validate a batch of events.
        
        Args:
            events: List of event dictionaries
            
        Returns:
            Tuple of (ValidationResult, list_of_fixed_events)
        """
        result = ValidationResult(is_valid=True)
        fixed_events = []
        
        for i, event in enumerate(events):
            event_result, fixed_event = self.validate_event(event, i)
            result.merge(event_result)
            fixed_events.append(fixed_event)
        
        return result, fixed_events
    
    def validate_table(self, table: pa.Table) -> ValidationResult:
        """
        Validate an Arrow table against expected schema.
        
        Args:
            table: PyArrow Table to validate
            
        Returns:
            ValidationResult
        """
        result = ValidationResult(is_valid=True)
        required_columns = ['entity_id', 'event', 'timestamp']
        
        # Decomposed checks
        _validate_table_structure(table, required_columns, result)
        self._validate_table_content(table, required_columns, result)

        return result

    def _validate_table_content(
        self, table: pa.Table, required_columns: list[str], result: ValidationResult
    ) -> None:
        """Check for data integrity within the table columns."""
        if self.level != ValidationLevel.STRICT:
            return

        for col in required_columns:
            if col in table.column_names:
                null_count = table[col].null_count
                if null_count > 0:
                    result.add_error(f"Column '{col}' has {null_count} null values")


def _check_strict_id_and_type(
    event: dict[str, Any], index: int, result: ValidationResult
) -> None:
    """Verify entity_id and event type are not empty."""
    if event.get('entity_id') == '':
        result.add_error(f"Event[{index}]: entity_id cannot be empty")

    if event.get('event') == '':
        result.add_error(f"Event[{index}]: event type cannot be empty")


def _check_strict_timestamp(
    event: dict[str, Any], index: int, result: ValidationResult
) -> None:
    """Verify timestamp is non-negative."""
    ts = event.get('timestamp')
    if isinstance(ts, (int, float)) and ts < 0:
        result.add_error(f"Event[{index}]: timestamp cannot be negative")


def _check_strict_details(
    event: dict[str, Any], index: int, result: ValidationResult
) -> None:
    """Verify details field is JSON serializable."""
    details = event.get('details')
    if details is None:
        return

    try:
        json.dumps(details)
    except (TypeError, ValueError) as e:
        result.add_error(f"Event[{index}]: details not JSON serializable: {e}")


def _run_single_custom_validator(
    event: dict[str, Any],
    index: int,
    result: ValidationResult,
    fld: str,
    validator: Callable
) -> None:
    """Execute a single custom validator for a field."""
    if fld not in event:
        return

    try:
        valid, message = validator(event[fld])
        if not valid:
            result.add_error(f"Event[{index}]: {message}")
    except Exception as e:
        result.add_warning(f"Event[{index}]: Custom validator failed: {e}")


def _validate_table_structure(
    table: pa.Table, required_columns: list[str], result: ValidationResult
) -> None:
    """Check for column existence and basic table metadata."""
    for col in required_columns:
        if col not in table.column_names:
            result.add_error(f"Missing required column: {col}")

    if len(table) == 0:
        result.add_warning("Table is empty")


def validate_consistency(
    events_list: list[dict[str, Any]], table: pa.Table
) -> ValidationResult:
    """
    Check consistency between events list and Arrow table.
    
    Args:
        events_list: Original events as list of dicts
        table: Arrow table representation
        
    Returns:
        ValidationResult
    """
    result = ValidationResult(is_valid=True)

    if len(events_list) != len(table):
        msg = f"Row count mismatch: list has {len(events_list)}, table has {len(table)}"
        result.add_error(msg)

    return result


def create_strict_validator() -> DataValidator:
    """Create a validator with strict settings."""
    return DataValidator(level=ValidationLevel.STRICT, auto_fix=False)


def create_lenient_validator(auto_fix: bool = True) -> DataValidator:
    """Create a validator with lenient settings and optional auto-fix."""
    return DataValidator(level=ValidationLevel.LENIENT, auto_fix=auto_fix)


def validate_and_fix_events(
    events: list[dict[str, Any]]
) -> Tuple[list[dict[str, Any]], ValidationResult]:
    """
    Convenience function to validate and auto-fix events.
    
    Args:
        events: List of event dictionaries
        
    Returns:
        Tuple of (fixed_events, validation_result)
    """
    validator = DataValidator(level=ValidationLevel.RELAXED, auto_fix=True)
    result, fixed = validator.validate_events_batch(events)
    return fixed, result
