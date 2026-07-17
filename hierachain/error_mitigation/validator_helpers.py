"""
Shared helper functions for HieraChain validators.
"""

import orjson
import os
import logging
from typing import Any
from datetime import datetime

import pyarrow as pa
import pyarrow.compute as pc

from hierachain.error_mitigation.validator_exceptions import ValidationError

logger = logging.getLogger(__name__)


def _log_scaling_event(event: dict[str, Any]) -> None:
    try:
        log_entry = orjson.dumps(event, option=orjson.OPT_INDENT_2).decode()
        logger.info("Scaling event logged: %s", log_entry)
        os.makedirs("log/error_mitigation", exist_ok=True)
        with open("log/error_mitigation/consensus_scaling.log", "a") as f:
            f.write(f"{datetime.now().isoformat()}: {log_entry}\n")
    except (IOError, OSError, ValueError) as ex:
        logger.error("Failed to log scaling event: %s", ex)


def _is_string_type(type_: pa.DataType) -> bool:
    return pa.types.is_string(type_) or pa.types.is_large_string(type_)


def _is_list_type(type_: pa.DataType) -> bool:
    return pa.types.is_list(type_) or pa.types.is_large_list(type_)


def _validate_arrow_structure(data: pa.Table | pa.RecordBatch) -> None:
    if "event" not in data.schema.names:
        return
    required_fields = ["entity_id", "event", "timestamp"]
    missing = [f for f in required_fields if f not in data.schema.names]
    if missing:
        logger.error("Missing required fields %s in Arrow event data", missing)


def _check_legacy_structure(data: Any) -> None:
    if not isinstance(data, dict) or "event" not in data:
        return
    required_fields = ["entity_id", "event", "timestamp"]
    for field in required_fields:
        if field not in data:
            logger.error("Missing required field '%s' in event data", field)


def _serialize_data_content(data: Any) -> str:
    if hasattr(data, "to_pylist"):
        return orjson.dumps(data.to_pylist(), option=orjson.OPT_SORT_KEYS).decode()
    if hasattr(data, "ToString"):
        return str(data)
    try:
        return orjson.dumps(data, option=orjson.OPT_SORT_KEYS).decode()
    except TypeError:
        return str(data)


def _check_forbidden_terms_in_array(
    array: pa.Array, field_name: str, forbidden_terms: list[str],
) -> None:
    utf8_lower = getattr(pc, "utf8_lower")
    match_substring = getattr(pc, "match_substring")
    any_op = getattr(pc, "any")

    lower_data = utf8_lower(array)
    for term in forbidden_terms:
        matches = match_substring(lower_data, term)
        if any_op(matches).as_py():
            error_msg = f"Forbidden crypto term '{term}' found in column '{field_name}'"
            logger.error(error_msg)
            raise ValidationError(error_msg)


def _write_audit_log(audit_entry: dict[str, Any]) -> None:
    try:
        os.makedirs("log/error_mitigation", exist_ok=True)
        with open("log/error_mitigation/api_audit.log", "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat()}: {orjson.dumps(audit_entry).decode()}\n")
    except (IOError, OSError) as ex:
        logger.error("Failed to write audit log: %s", ex)
