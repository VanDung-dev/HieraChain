"""
Data Validator for HieraChain Framework

This module provides data validation utilities for Arrow tables and events,
ensuring data integrity and schema compliance.
"""

import json
import logging
from enum import Enum
from typing import Any, Callable, Optional, Tuple
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
    FIELD_TYPES = {
        'entity_id': str,
        'event': str,
        'timestamp': (int, float),
        'details': (dict, type(None)),
    }
    
    def __init__(
        self,
        level: ValidationLevel = ValidationLevel.RELAXED,
        auto_fix: bool = False,
        custom_validators: Optional[dict[str, Callable]] = None
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
        self,
        event: dict[str, Any],
        index: int = 0
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
        
        # Check required fields
        for field in self.REQUIRED_FIELDS:
            if field not in event or event[field] is None:
                if self.auto_fix and field == 'timestamp':
                    import time
                    fixed_event['timestamp'] = time.time()
                    result.add_fix(f"Event[{index}]: Auto-added timestamp")
                else:
                    result.add_error(
                        f"Event[{index}]: Missing required field '{field}'"
                    )
        
        # Type checking
        if self.level in (ValidationLevel.STRICT, ValidationLevel.RELAXED):
            for field, expected_types in self.FIELD_TYPES.items():
                if field in fixed_event and fixed_event[field] is not None:
                    if not isinstance(fixed_event[field], expected_types):
                        actual_type = type(fixed_event[field]).__name__
                        if self.auto_fix and field == 'entity_id':
                            fixed_event['entity_id'] = str(fixed_event['entity_id'])
                            result.add_fix(
                                f"Event[{index}]: Converted entity_id to string"
                            )
                        elif self.auto_fix and field == 'timestamp':
                            try:
                                fixed_event['timestamp'] = float(
                                    fixed_event['timestamp']
                                )
                                result.add_fix(
                                    f"Event[{index}]: Converted timestamp to float"
                                )
                            except (ValueError, TypeError):
                                result.add_error(
                                    f"Event[{index}]: Cannot convert timestamp"
                                )
                        else:
                            result.add_error(
                                f"Event[{index}]: Field '{field}' expected "
                                f"{expected_types}, got {actual_type}"
                            )
        
        # STRICT mode: additional checks
        if self.level == ValidationLevel.STRICT:
            # Check entity_id is not empty
            if fixed_event.get('entity_id') == '':
                result.add_error(f"Event[{index}]: entity_id cannot be empty")
            
            # Check event type is not empty
            if fixed_event.get('event') == '':
                result.add_error(f"Event[{index}]: event type cannot be empty")
            
            # Check timestamp is positive
            ts = fixed_event.get('timestamp')
            if ts is not None and ts < 0:
                result.add_error(f"Event[{index}]: timestamp cannot be negative")
            
            # Check details JSON serializable
            details = fixed_event.get('details')
            if details is not None:
                try:
                    json.dumps(details)
                except (TypeError, ValueError) as e:
                    result.add_error(
                        f"Event[{index}]: details not JSON serializable: {e}"
                    )
        
        # Run custom validators
        for field, validator in self.custom_validators.items():
            if field in fixed_event:
                try:
                    valid, message = validator(fixed_event[field])
                    if not valid:
                        result.add_error(f"Event[{index}]: {message}")
                except Exception as e:
                    result.add_warning(
                        f"Event[{index}]: Custom validator failed: {e}"
                    )
        
        return result, fixed_event
    
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
        
        # Check required columns exist
        required_columns = ['entity_id', 'event', 'timestamp']
        for col in required_columns:
            if col not in table.column_names:
                result.add_error(f"Missing required column: {col}")
        
        # Check row count
        if len(table) == 0:
            result.add_warning("Table is empty")
        
        # Check for null values in required columns
        if self.level == ValidationLevel.STRICT:
            for col in required_columns:
                if col in table.column_names:
                    null_count = table[col].null_count
                    if null_count > 0:
                        result.add_error(
                            f"Column '{col}' has {null_count} null values"
                        )
        
        return result
    
    @staticmethod
    def validate_consistency(
            events_list: list[dict[str, Any]],
        table: pa.Table
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
        
        # Check row count matches
        if len(events_list) != len(table):
            result.add_error(
                f"Row count mismatch: list has {len(events_list)}, "
                f"table has {len(table)}"
            )
        
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
    validator = DataValidator(
        level=ValidationLevel.RELAXED,
        auto_fix=True
    )
    result, fixed = validator.validate_events_batch(events)
    return fixed, result
