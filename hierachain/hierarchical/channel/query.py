"""
Channel query utilities — PyArrow-based event filtering and expression building.
"""

import logging
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc

from hierachain.core.block import Block, table_to_list_of_dicts

logger = logging.getLogger(__name__)


def _filter_block_events(
    block: Block, filter_func, filter_expr
) -> list[dict[str, Any]]:
    if filter_expr is not None:
        try:
            filtered_table = block.events.filter(filter_expr)
            filtered_events = table_to_list_of_dicts(filtered_table)
            return [e for e in filtered_events if filter_func(e)]
        except (pa.ArrowInvalid, pa.ArrowTypeError, ValueError) as e:
            logger.error("Failed to filter block with Arrow: %s", e)

    if hasattr(block, "to_event_list"):
        block_events = block.to_event_list()
    else:
        block_events = table_to_list_of_dicts(block.events)

    return [event for event in block_events if filter_func(event)]


def _build_query_expression(query_params: dict[str, Any]) -> Any | None:
    try:
        filters = []
        param_map = {
            "event_type": "event",
            "entity_id": "entity_id",
            "start_time": "timestamp",
            "end_time": "timestamp",
        }

        for param, field in param_map.items():
            if param in query_params:
                filters.append(_build_single_filter(field, param, query_params[param]))

        if not filters:
            return None

        expr = filters[0]
        for f in filters[1:]:
            expr = expr & f
        return expr
    except (KeyError, TypeError, ValueError):
        return None


def _build_single_filter(field: str, param: str, value: Any) -> Any:
    if param == "start_time":
        return pc.field(field) >= value
    if param == "end_time":
        return pc.field(field) <= value
    return pc.field(field) == value


def _check_details_match(event: dict[str, Any], key: str, value: Any) -> bool:
    detail_key = key.split(".", 1)[1]
    details = event.get("details", {})
    actual_val = details.get(detail_key)

    if not isinstance(value, dict):
        return actual_val == str(value)

    return _evaluate_operators(actual_val, value)


def _evaluate_operators(actual_val: Any, operators: dict[str, Any]) -> bool:
    try:
        val_float = float(str(actual_val)) if actual_val is not None else None
        if val_float is None:
            return False

        op_map = {
            "gt": lambda v, target: v > target,
            "lt": lambda v, target: v < target,
            "gte": lambda v, target: v >= target,
            "lte": lambda v, target: v <= target,
        }

        for op, target_val in operators.items():
            if op in op_map and not op_map[op](val_float, target_val):
                return False
        return True
    except (ValueError, TypeError):
        return False


def _check_event_match(event: dict[str, Any], key: str, value: Any) -> bool:
    if key == "event_type":
        return event.get("event") == value
    if key == "entity_id":
        return event.get("entity_id") == value
    if key == "start_time":
        return event.get("timestamp", 0) >= value
    if key == "end_time":
        return event.get("timestamp", 0) <= value
    if key.startswith("details."):
        return _check_details_match(event, key, value)
    return True


def _create_query_filter(query_params: dict[str, Any]):
    def event_filter(event: dict[str, Any]) -> bool:
        return all(
            _check_event_match(event, k, v)
            for k, v in query_params.items()
            if k != "limit"
        )

    return event_filter
