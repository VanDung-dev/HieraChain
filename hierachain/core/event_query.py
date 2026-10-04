"""Bounded event pages from indexed candidates or Arrow metadata columns."""

from bisect import bisect_right
from collections.abc import Iterable, Iterator
from copy import deepcopy
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc

from hierachain.core.block import table_to_list_of_dicts
from hierachain.core.utils import get_block_events

EVENT_QUERY_BATCH_SIZE = 1024


def _matches_event(
    event: Any, entity_id: str | None, event_type: str | None,
    from_timestamp: float | None, to_timestamp: float | None,
) -> bool:
    if isinstance(event, dict):
        event_entity = event.get("entity_id")
        event_kind = event.get("event_type") or event.get("event", "")
        timestamp = event.get("timestamp", 0)
    else:
        event_entity = getattr(event, "entity_id", None)
        event_kind = getattr(event, "event_type", None) or getattr(event, "event", "")
        timestamp = getattr(event, "timestamp", 0)
    return (
        (not entity_id or event_entity == entity_id)
        and (not event_type or event_kind == event_type)
        and (from_timestamp is None or timestamp >= from_timestamp)
        and (to_timestamp is None or timestamp <= to_timestamp)
    )


def _iter_block_rows(
    block: Any, start: int, entity_id: str | None,
    from_timestamp: float | None, to_timestamp: float | None,
) -> Iterator[tuple[int, Any]]:
    table = getattr(block, "events", None)
    if not isinstance(table, pa.Table):
        # Compatibility for external chains with list/object event storage.
        for index, event in enumerate(get_block_events(block)):
            if index >= start:
                yield index, event
        return
    for offset in range(start, len(table), EVENT_QUERY_BATCH_SIZE):
        chunk = table.slice(offset, EVENT_QUERY_BATCH_SIZE)
        mask = pa.array([True] * len(chunk))
        if entity_id:
            mask = pc.and_(mask, pc.equal(chunk["entity_id"], entity_id))
        timestamps = pc.fill_null(chunk["timestamp"], 0.0)
        if from_timestamp is not None:
            mask = pc.and_(mask, pc.greater_equal(timestamps, from_timestamp))
        if to_timestamp is not None:
            mask = pc.and_(mask, pc.less_equal(timestamps, to_timestamp))
        for index in pc.indices_nonzero(pc.fill_null(mask, False)).to_pylist():
            # Decode one selected payload at a time so the result limit can stop work.
            yield offset + index, table_to_list_of_dicts(chunk.slice(index, 1))[0]


def select_event_page(
    blocks: Iterable[Any], *, entity_id: str | None = None, event_type: str | None = None,
    from_timestamp: float | None = None, to_timestamp: float | None = None,
    limit: int = 100, after: tuple[int, int] | None = None,
    candidates: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return owned event payloads in ledger order; convert no discarded indexed payloads."""
    if limit <= 0 or (from_timestamp is not None and to_timestamp is not None and from_timestamp > to_timestamp):
        return []
    position = after if after is not None else (-1, -1)
    results = []
    if candidates is not None:
        start = bisect_right(candidates, position, key=lambda entry: (entry["block_index"], entry["event_index"]))
        for index in range(start, len(candidates)):
            entry = candidates[index]
            if _matches_event(entry["event"], entity_id, event_type, from_timestamp, to_timestamp):
                results.append(deepcopy(entry))
                if len(results) == limit:
                    break
        return results
    for block in blocks:
        if block.index < position[0]:
            continue
        start = position[1] + 1 if block.index == position[0] else 0
        for index, event in _iter_block_rows(block, start, entity_id, from_timestamp, to_timestamp):
            if _matches_event(event, entity_id, event_type, from_timestamp, to_timestamp):
                results.append({"block_index": block.index, "event_index": index, "event": deepcopy(event)})
                if len(results) == limit:
                    return results
    return results
