"""Arrow batch codec helpers for the event journal."""

import json
import logging
from collections.abc import Generator
from typing import Any, BinaryIO

import pyarrow as pa

from hierachain.error_mitigation.journal_constants import _JOURNAL_DATA_MARKER
from hierachain.error_mitigation.journal_io import _read_next_batch
from hierachain.serialization import dumps_json, loads_json

logger = logging.getLogger(__name__)


def _process_details_field(ev: dict[str, Any]) -> None:
    """Convert details dict to list of tuples for Arrow map type."""
    details = ev.get("details")
    if isinstance(details, dict):
        ev["details"] = [(k, str(v)) for k, v in details.items()]
    elif details is None:
        ev["details"] = []


def _pack_extra_fields(ev: dict[str, Any], raw_data: dict[str, Any]) -> None:
    """Pack fields outside the Arrow schema alongside the original data value."""
    schema_fields = ["entity_id", "event", "timestamp", "data", "details"]
    extra_fields = {
        key: value
        for key, value in raw_data.items()
        if key not in schema_fields and not isinstance(value, bytes)
    }
    original_details = raw_data.get("details")
    if not extra_fields and not isinstance(original_details, dict):
        return

    data_value = ev.get("data")
    if isinstance(data_value, bytes):
        try:
            data_value = loads_json(data_value)
        except json.JSONDecodeError:
            data_value = {"$binary": data_value.hex()}

    envelope = {_JOURNAL_DATA_MARKER: {
        "data": data_value, "extra": extra_fields, "fields": list(raw_data),
    }}
    if isinstance(original_details, dict):
        envelope[_JOURNAL_DATA_MARKER]["details"] = original_details
    try:
        ev["data"] = dumps_json(envelope).encode("utf-8")
    except (TypeError, ValueError):
        envelope[_JOURNAL_DATA_MARKER]["data"] = str(data_value)
        ev["data"] = dumps_json(envelope).encode("utf-8")


def _serialize_data_field(ev: dict[str, Any]) -> None:
    """Ensure 'data' is bytes, serializing if necessary."""
    data = ev.get("data")
    if data is None:
        ev["data"] = b"null"
        return

    if not isinstance(data, bytes):
        try:
            if isinstance(data, str):
                ev["data"] = data.encode("utf-8")
            else:
                ev["data"] = dumps_json(data).encode("utf-8")
        except (TypeError, ValueError) as e:
            logger.warning("Could not JSON serialize 'data' field: %s. Using str().", e)
            ev["data"] = str(data).encode("utf-8")


def _serialize_arrow_batch(batch: pa.RecordBatch) -> bytes:
    """Serialize one record batch as a self-contained Arrow IPC stream."""
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, batch.schema) as writer:
        writer.write_batch(batch)
    return sink.getvalue().to_pybytes()


def _apply_extra_fields(row: dict[str, Any], extra_data: dict[str, Any]) -> None:
    """Merge extra data into row only for non-existent keys."""
    for k, v in extra_data.items():
        if k not in row:
            row[k] = v


def _unpack_extra_field_content(row: dict[str, Any], data_content: Any) -> None:
    """Restore data and extra fields from the journal's binary JSON column."""
    if not data_content:
        row["data"] = None
        return
    try:
        decoded = loads_json(data_content)
    except (json.JSONDecodeError, TypeError):
        row["data"] = {"$binary": bytes(data_content).hex()}
        return

    if isinstance(decoded, dict):
        envelope = decoded.get(_JOURNAL_DATA_MARKER)
        if (
            isinstance(envelope, dict)
            and {"data", "extra"} <= set(envelope) <= {"data", "extra", "details", "fields"}
            and isinstance(envelope["extra"], dict)
            and ("details" not in envelope or isinstance(envelope["details"], dict))
            and ("fields" not in envelope or (
                isinstance(envelope["fields"], list)
                and all(isinstance(name, str) for name in envelope["fields"])
            ))
        ):
            row["data"] = envelope["data"]
            if "details" in envelope:
                row["details"] = envelope["details"]
            _apply_extra_fields(row, envelope["extra"])
            if "fields" in envelope:
                for name in set(row) - set(envelope["fields"]):
                    row.pop(name)
            return

        # Old journal frames stored only the packed extra-field object in this column.
        _apply_extra_fields(row, decoded)
    row["data"] = decoded


def _unpack_row_data(row: dict[str, Any]) -> dict[str, Any]:
    """Unpack details and extra data from a record row."""
    # Unpack 'details' map back to dict
    if row.get("details"):
        row["details"] = dict(row["details"])

    # Unpack 'data' if it contains extra fields
    _unpack_extra_field_content(row, row.get("data"))

    return row


def _iterate_journal_batches(
    f: BinaryIO, schema: pa.Schema
) -> Generator[dict[str, Any], None, None]:
    """Helper generator to iterate over batches in a journal file."""
    while True:
        batch_data = _read_next_batch(f)
        if batch_data is None:
            break

        try:
            try:
                batch = pa.ipc.read_record_batch(batch_data, schema)
            except (OSError, pa.ArrowException, ValueError):
                reader = pa.ipc.open_stream(batch_data)
                batch = reader.read_next_batch()
            for row in batch.to_pylist():
                yield _unpack_row_data(row)
        except (OSError, pa.ArrowException, StopIteration, ValueError) as arrow_err:
            raise ValueError(f"Corrupt Arrow batch in journal: {arrow_err}") from arrow_err
