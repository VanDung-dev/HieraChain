"""
API Validator for HieraChain Ledger.

Validates API endpoints and data for compliance, including
forbidden cryptocurrency term detection in Arrow and legacy data formats.
"""

from __future__ import annotations

import json
import hashlib
import time
import logging
from typing import Any, Union

import pyarrow as pa

from hierachain.error_mitigation.validator_exceptions import ValidationError, SecurityError, ConfigurationError
from hierachain.error_mitigation.consensus_validator import ConsensusValidator  # noqa: F401
from hierachain.error_mitigation.encryption_validator import EncryptionValidator  # noqa: F401
from hierachain.error_mitigation.resource_validator import ResourceValidator  # noqa: F401
from hierachain.error_mitigation.validator_helpers import (
    _is_string_type,
    _is_list_type,
    _validate_arrow_structure,
    _check_legacy_structure,
    _serialize_data_content,
    _check_forbidden_terms_in_array,
    _write_audit_log,
)

logger = logging.getLogger(__name__)


class APIValidator:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.endpoint_validation = config.get("endpoint_validation", "pre_call")
        self.command_audit = config.get("command_audit", True)
        self.forbidden_terms = [
            "transaction", "mining", "coin", "token", "wallet", "address",
            "sender", "receiver", "amount", "fee", "reward", "coinbase",
        ]
        logger.info("Initialized APIValidator")

    def _validate_arrow_recursive(self, data: Union[pa.Array, pa.ChunkedArray], field_name: str) -> None:
        try:
            if isinstance(data, pa.ChunkedArray):
                self._handle_arrow_chunked(data, field_name)
            else:
                self._dispatch_type_validation(data, field_name, data.type)
        except ValidationError:
            raise
        except (AttributeError, TypeError, pa.ArrowInvalid) as e:
            logger.warning("Recursive validation error on %s: %s", field_name, e)

    def _dispatch_type_validation(self, data: Any, field_name: str, type_: pa.DataType) -> None:
        handlers = [
            (_is_string_type, lambda d, f, _t: self._check_string_array(d, f)),
            (pa.types.is_map, lambda d, f, t: self._handle_arrow_map(d, f, t)),
            (_is_list_type, lambda d, f, _t: self._handle_arrow_list(d, f)),
            (pa.types.is_struct, lambda d, f, t: self._handle_arrow_struct(d, f, t)),
        ]
        for predicate, handler in handlers:
            if predicate(type_):
                handler(data, field_name, type_)
                return

    def _handle_arrow_chunked(self, data: pa.ChunkedArray, field_name: str) -> None:
        for chunk in data.chunks:
            self._validate_arrow_recursive(chunk, field_name)

    def _handle_arrow_map(self, data: pa.Array, field_name: str, type_: pa.DataType) -> None:
        if hasattr(data, "keys") and hasattr(data, "items"):
            self._validate_map_keys_values(data, field_name)
        else:
            self._fallback_map_validation(data, field_name, type_)

    def _validate_map_keys_values(self, data: pa.Array, field_name: str) -> None:
        keys = getattr(data, "keys")
        items = getattr(data, "items")
        self._validate_arrow_recursive(keys, f"{field_name}.keys")
        self._validate_arrow_recursive(items, f"{field_name}.values")

    def _fallback_map_validation(self, data: pa.Array, field_name: str, type_: pa.DataType) -> None:
        if not isinstance(type_, pa.MapType):
            return
        struct_fields = [pa.field("key", type_.key_type, nullable=False), pa.field("value", type_.item_type, nullable=True)]
        struct_type = pa.struct(struct_fields)
        list_type = pa.list_(struct_type)
        as_list = data.cast(list_type)
        if hasattr(as_list, "flatten"):
            flattened = getattr(as_list, "flatten")()
            self._validate_arrow_recursive(flattened, f"{field_name}.entry")

    def _handle_arrow_list(self, data: pa.Array, field_name: str) -> None:
        if hasattr(data, "flatten"):
            flattened = getattr(data, "flatten")()
            self._validate_arrow_recursive(flattened, f"{field_name}.nested")

    def _handle_arrow_struct(self, data: pa.StructArray, field_name: str, type_: pa.DataType) -> None:
        for i in range(type_.num_fields):
            field = type_.field(i)
            child = data.field(i)
            self._validate_arrow_recursive(child, f"{field_name}.{field.name}")

    def _check_string_array(self, array: pa.Array, field_name: str) -> None:
        _check_forbidden_terms_in_array(array, field_name, self.forbidden_terms)

    def validate_endpoint_data(self, data: Any) -> bool:
        try:
            self._dispatch_data_validation(data)
        except ValidationError:
            raise
        except (AttributeError, TypeError, pa.ArrowInvalid) as e:
            logger.warning("Validation complexity check failed: %s", e)
        logger.info("API endpoint data validation passed")
        return True

    def _dispatch_data_validation(self, data: Any) -> None:
        if hasattr(data, "schema") and isinstance(data, (pa.Table, pa.RecordBatch)):
            self._validate_arrow_object(data)
        else:
            self._validate_legacy_object(data)

    def _validate_arrow_object(self, data: Union[pa.Table, pa.RecordBatch]) -> None:
        self._validate_arrow_schema(data)
        for col_name in data.column_names:
            self._validate_arrow_recursive(data[col_name], col_name)
        _validate_arrow_structure(data)

    def _validate_arrow_schema(self, data: Union[pa.Table, pa.RecordBatch]) -> None:
        for name in data.schema.names:
            if any(term in name.lower() for term in self.forbidden_terms):
                error_msg = f"Forbidden cryptocurrency term '{name}' found in Arrow schema"
                logger.error(error_msg)
                raise ValidationError(error_msg)

    def _validate_legacy_object(self, data: Any) -> None:
        data_str = json.dumps(data).lower()
        for term in self.forbidden_terms:
            if term in data_str:
                error_msg = f"Forbidden cryptocurrency term '{term}' found in API data"
                logger.error(error_msg)
                raise ValidationError(error_msg)
        _check_legacy_structure(data)

    def audit_api_call(self, endpoint: str, data: Any, user_id: str | None = None) -> None:
        if not self.command_audit:
            return
        data_content = _serialize_data_content(data)
        audit_entry = {
            "event": "api_call_audit",
            "endpoint": endpoint,
            "user_id": user_id,
            "timestamp": time.time(),
            "data_hash": hashlib.sha256(data_content.encode()).hexdigest(),
        }
        logger.info("API call audited: %s", endpoint)
        _write_audit_log(audit_entry)


def validate_certificate(certificate: Any) -> None:
    if certificate.is_expired():
        raise SecurityError("Certificate validation failed: Certificate has expired")


def create_validator(validator_type: str, config: dict[str, Any]) -> Any:
    validators = {
        "consensus": ConsensusValidator,
        "encryption": EncryptionValidator,
        "resource": ResourceValidator,
        "api": APIValidator,
    }
    if validator_type not in validators:
        raise ValueError(f"Unknown validator type: {validator_type}")
    return validators[validator_type](config)
