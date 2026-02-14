"""
Transaction Journal System for HieraChain.

This module provides a durability layer to ensure that transactions are
safely persisted to physical storage before being processed.
This protects against data loss during power failures, system crashes, or
rapid shutdowns.
"""

import os
import re
import logging
import struct
import json
from typing import Any, Generator, BinaryIO
from pathlib import Path
import pyarrow as pa

from hierachain.core import schemas

logger = logging.getLogger(__name__)


def _validate_path_component(comp: str) -> None:
    """Validate a single path component for security."""
    if comp in ("", ".", ".."):
        raise ValueError("Security: storage_dir contains invalid path components")
    if not re.match(r"^[a-zA-Z0-9_\-~.]+$", comp):
        raise ValueError(f"Security: storage_dir invalid component: {comp}")


def _get_clean_path_input(storage_dir: str) -> str:
    """Strip Windows drive prefix and leading slashes."""
    _s = storage_dir
    m = re.match(r"^([a-zA-Z]:[\\/])(.*)$", _s)
    if m:
        _s = m.group(2)
    return _s.lstrip("/")


def _validate_storage_dir_input(storage_dir: str) -> None:
    """
    Validate the provided storage_dir string strictly.
    - Disallow traversal tokens ('..')
    - Allow only alphanumeric, underscore, hyphen in each path component
    - Allow directory separators ('/' or '\\') between components
    """
    if not isinstance(storage_dir, str) or not storage_dir.strip():
        raise ValueError("Security: storage_dir must be a non-empty string")

    # Preserve the original error message expected by tests for traversal detection
    if ".." in storage_dir:
        raise ValueError("Security: Path traversal sequence ('..') not allowed.")

    # Allow only safe characters overall (components and separators)
    overall_pattern = r"^(?:[a-zA-Z]:[\\/]|/)?[a-zA-Z0-9_\-~./\\]+$"
    if not re.match(overall_pattern, storage_dir):
        raise ValueError(
            "Security: storage_dir contains invalid characters. "
            "Allowed: [a-zA-Z0-9_-], dot, tilde, and path separators"
        )

    # Validate each component is safe
    _s = _get_clean_path_input(storage_dir)
    components = re.split(r"[\\/]+", _s)
    for comp in components:
        _validate_path_component(comp)


def _build_absolute_storage_path(data_root: Path, abs_path_str: str) -> Path:
    """Build a safe path from an absolute string within data_root."""
    # Must be within data_root
    if os.path.commonpath([str(data_root), abs_path_str]) != str(data_root):
        raise ValueError(f"Security: Storage path {abs_path_str} must be within {data_root}")
    # Compute relative path string safely
    try:
        rel_str = os.path.relpath(abs_path_str, start=str(data_root))
    except (ValueError, OSError):
        rel_str = "."

    rel_parts = [] if rel_str in (".", "") else re.split(r"[\\/]+", rel_str)
    rel_parts = [p for p in rel_parts if p]

    # Validate each component
    safe_parts = []
    for comp in rel_parts:
        if comp in (".", "..") or not re.match(r"^[a-zA-Z0-9_\-~.]+$", comp):
            raise ValueError("Security: storage_dir invalid path components")
        safe_parts.append(comp)

    return data_root.joinpath(*safe_parts) if safe_parts else data_root


def _build_storage_path(data_root: Path, storage_dir: str) -> Path:
    """
    Build a safe storage path anchored strictly to data_root using sanitized
    components.
    """
    # Handle absolute paths explicitly
    if os.path.isabs(storage_dir):
        return _build_absolute_storage_path(data_root, os.path.normpath(storage_dir))

    # Relative path case
    _s = _get_clean_path_input(storage_dir)
    comps = [c for c in re.split(r"[\\/]+", _s) if c]
    if comps and comps[0].lower() == "data":
        comps = comps[1:]

    safe_parts = []
    for comp in comps:
        if comp in (".", "..") or not re.match(r"^[a-zA-Z0-9_\-~.]+$", comp):
            raise ValueError("Security: storage_dir invalid path components")
        safe_parts.append(comp)

    return data_root.joinpath(*safe_parts) if safe_parts else data_root


def _process_details_field(ev: dict[str, Any]) -> None:
    """Convert details dict to list of tuples for Arrow map type."""
    details = ev.get("details")
    if isinstance(details, dict):
        ev["details"] = [(k, str(v)) for k, v in details.items()]
    elif details is None:
        ev["details"] = []


def _pack_extra_fields(ev: dict[str, Any], raw_data: dict[str, Any]) -> None:
    """Pack fields not in schema into 'data' JSON field."""
    if "data" in ev and ev["data"]:
        return

    clean_event = {}
    schema_fields = ["entity_id", "event", "timestamp", "data", "details"]
    for k, v in raw_data.items():
        if k not in schema_fields and not isinstance(v, bytes):
            clean_event[k] = v

    if clean_event:
        ev["data"] = json.dumps(clean_event).encode("utf-8")


def _serialize_data_field(ev: dict[str, Any]) -> None:
    """Ensure 'data' is bytes, serializing if necessary."""
    data = ev.get("data")
    if data is None:
        ev["data"] = b""
        return

    if not isinstance(data, bytes):
        try:
            if isinstance(data, str):
                ev["data"] = data.encode("utf-8")
            else:
                ev["data"] = json.dumps(data).encode("utf-8")
        except (TypeError, ValueError) as e:
            logger.warning(f"Could not JSON serialize 'data' field: {e}. Using str().")
            ev["data"] = str(data).encode("utf-8")


def _read_next_batch(f: BinaryIO) -> bytes | None:
    """Read the next length-prefixed batch from file."""
    len_bytes = f.read(4)
    if not len_bytes:
        return None

    if len(len_bytes) < 4:
        logger.warning("Truncated journal file (incomplete length prefix).")
        return None

    msg_len = struct.unpack("<I", len_bytes)[0]
    batch_data = f.read(msg_len)

    if len(batch_data) < msg_len:
        logger.warning("Truncated journal file (incomplete batch data).")
        return None

    return batch_data


def _apply_extra_fields(row: dict[str, Any], extra_data: dict[str, Any]) -> None:
    """Merge extra data into row only for non-existent keys."""
    for k, v in extra_data.items():
        if k not in row:
            row[k] = v


def _unpack_extra_field_content(row: dict[str, Any], data_content: Any) -> None:
    """Unpack JSON data field into the row dictionary."""
    if not data_content:
        return
    try:
        extra_data = json.loads(data_content)
        if isinstance(extra_data, dict):
            _apply_extra_fields(row, extra_data)
    except (json.JSONDecodeError, TypeError):
        pass


def _unpack_row_data(row: dict[str, Any]) -> dict[str, Any]:
    """Unpack details and extra data from a record row."""
    # Unpack 'details' map back to dict
    if row.get("details"):
        row["details"] = dict(row["details"])

    # Unpack 'data' if it contains extra fields
    _unpack_extra_field_content(row, row.get("data"))

    return row


def _iterate_journal_batches(f: BinaryIO, schema: pa.Schema) -> Generator[dict[str, Any], None, None]:
    """Helper generator to iterate over batches in a journal file."""
    while True:
        batch_data = _read_next_batch(f)
        if batch_data is None:
            break

        try:
            batch = pa.ipc.read_record_batch(batch_data, schema)
            row = batch.to_pylist()[0]
            yield _unpack_row_data(row)
        except (pa.ArrowException, ValueError) as arrow_err:
            logger.error(f"Corrupted Arrow batch in journal: {arrow_err}")
            continue


class TransactionJournal:
    """
    Append-only journal for durable transaction logging using Apache Arrow.

    This class handles writing critical events to disk as serialized Arrow
    RecordBatches with synchronous flushing to guarantee persistence. Using
    Arrow provides faster IO and ensures schema consistency early in the
    pipeline.
    """

    @staticmethod
    def _validate_filename(name: str) -> None:
        """
        Validate filename against strict security rules (CWE-22).
        Allowed: alphanumeric, underscore, hyphen, single dot.
        """
        # Strict allowlist approach.
        pattern = r"^[a-zA-Z0-9_\-]+(\.[a-zA-Z0-9]+)?$"
        if not re.match(pattern, name):
            raise ValueError(
                f"Security: Invalid filename '{name}'. "
                "Allowed: [a-zA-Z0-9_-] and single optional extension."
            )

    def __init__(self, storage_dir: str = "data/journal", active_log_name: str = "current.log"):
        """
        Initialize the Transaction Journal.

        Args:
            storage_dir: Directory to store journal files.
            active_log_name: Name of the active journal file.
        """
        # Strictly validate storage_dir input string first
        _validate_storage_dir_input(storage_dir)

        data_root = Path("data").resolve()

        # Build a safe storage path anchored to data_root from sanitized components
        self.storage_path = _build_storage_path(data_root, storage_dir)

        # Enforce storage_path stays within data_root as an additional guard
        in_root = os.path.commonpath([str(data_root), str(self.storage_path)]) == str(data_root)
        if not in_root:
            raise ValueError(
                f"Security: Storage path {self.storage_path} "
                f"must be within {data_root}"
            )

        safe_log_name = os.path.basename(active_log_name)
        self._validate_filename(safe_log_name)

        # Build active log file path strictly inside storage_path
        self.active_log_file = self.storage_path / safe_log_name

        try:
            self.active_log_file.relative_to(self.storage_path)
        except ValueError as exc:
            raise ValueError(
                f"Security: Log file path {self.active_log_file} "
                f"escapes storage directory {self.storage_path}"
            ) from exc

        # Reject symlinks for both directory and file targets
        try:
            if self.storage_path.is_symlink():
                raise ValueError("Security: storage path cannot be a symlink")
            if self.active_log_file.exists() and self.active_log_file.is_symlink():
                raise ValueError("Security: active log file cannot be a symlink")
        except (OSError, RuntimeError) as e:
            logger.warning(f"Filesystem check failed, attempting creation anyway: {e}")

        self._file_handle: BinaryIO | None = None
        self._schema = schemas.get_event_schema()

        # Ensure directory exists
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Open the active log file
        self._open_journal()

    def _open_journal(self) -> None:
        """Open the journal file for appending (binary mode)."""
        try:
            # 'ab' mode for append binary
            self._file_handle = open(self.active_log_file, "ab")
        except (OSError, IOError) as e:
            logger.critical(f"Failed to open transaction journal: {e}")
            raise

    def _dict_to_arrow_batch(self, event_data: dict[str, Any]) -> pa.RecordBatch:
        """
        Convert a raw event dictionary to an Arrow RecordBatch.
        Handles packing of extra fields into 'data' binary column.
        """
        ev = event_data.copy()
        _process_details_field(ev)
        _pack_extra_fields(ev, event_data)
        _serialize_data_field(ev)

        # Create RecordBatch (size 1)
        try:
            pydict = {name: [ev.get(name)] for name in self._schema.names}
            batch = pa.record_batch(pydict, schema=self._schema)
            return batch
        except (pa.ArrowInvalid, pa.ArrowTypeError) as e:
            event_id = ev.get("event_id", "unknown")
            logger.error(f"Schema conversion error for event {event_id}: {e}")
            raise

    def log_event(self, event_data: dict[str, Any]) -> bool:
        """
        Durably log an event to the journal using Arrow format.

        Writes length-prefixed serialized batch: [Length (4 bytes)][Batch Bytes...]

        Args:
            event_data: The event dictionary to log.

        Returns:
            bool: True if logged and synced successfully.
        """
        if self._file_handle is None:
            self._open_journal()

        if self._file_handle is None:
            return False

        try:
            # 1. Convert to Arrow Batch
            batch = self._dict_to_arrow_batch(event_data)

            # 2. Serialize Batch to IPC message (buffer)
            serialized_batch = batch.serialize()

            # 3. Write Length Prefix (4 bytes, little endian)
            length_prefix = struct.pack("<I", len(serialized_batch))
            self._file_handle.write(length_prefix)

            # 4. Write Data
            self._file_handle.write(serialized_batch)

            # 5. Flush and Sync
            self._file_handle.flush()
            os.fsync(self._file_handle.fileno())

            return True

        except (OSError, IOError, pa.ArrowException) as e:
            logger.critical(f"CRITICAL: Failed to write to transaction journal: {e}")
            return False

    def replay(self) -> Generator[dict[str, Any], None, None]:
        """
        Replay all events from the journal.
        Reads binary Arrow batches and yields them as Dictionaries.
        """
        if not self.active_log_file.exists():
            return

        try:
            with open(self.active_log_file, "rb") as f:
                yield from _iterate_journal_batches(f, self._schema)
        except (OSError, IOError) as e:
            logger.error(f"Error replaying journal: {e}")

    def close(self):
        """Close the journal file handle."""
        if self._file_handle:
            try:
                self._file_handle.flush()
                self._file_handle.close()
            except (OSError, IOError) as e:
                logger.error(f"Error closing journal: {e}")
            finally:
                self._file_handle = None

    def clear(self):
        """Clear the current journal."""
        self.close()
        try:
            # Truncate file (binary mode)
            with open(self.active_log_file, "wb"):
                pass
            # Reopen
            self._open_journal()
            logger.info("Transaction journal cleared (Arrow format).")
        except (OSError, IOError) as e:
            logger.error(f"Failed to clear journal: {e}")
