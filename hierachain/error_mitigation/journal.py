"""
Transaction Journal System for HieraChain.

This module provides a durability layer to ensure that transactions are
safely persisted to physical storage before being processed.
This protects against data loss during power failures, system crashes, or
rapid shutdowns.
"""

import json
import logging
import os
import re
import struct
import threading
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any, BinaryIO

import pyarrow as pa
import pyarrow.parquet as pq

from hierachain.serialization import dumps_json, loads_json

try:
    import fcntl
except ImportError:  # Keep package importable on platforms without POSIX locks.
    fcntl = None

from hierachain.core.block import EVENT_SCHEMA as _EVENT_SCHEMA

logger = logging.getLogger(__name__)

_JOURNAL_MAX_FILE_SIZE = 100 * 1024 * 1024
_JOURNAL_MAX_FRAME_SIZE = _JOURNAL_MAX_FILE_SIZE
_JOURNAL_DATA_MARKER = "__hrc_journal_v1__"


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
        raise ValueError(
            "Security: Storage path %s must be within %s",
            abs_path_str, data_root
        )
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


def _read_next_batch(f: BinaryIO) -> bytes | None:
    """Read the next length-prefixed batch from file."""
    len_bytes = f.read(4)
    if not len_bytes:
        return None

    if len(len_bytes) < 4:
        raise ValueError("Truncated journal file (incomplete length prefix)")

    msg_len = struct.unpack("<I", len_bytes)[0]
    if msg_len > _JOURNAL_MAX_FRAME_SIZE:
        raise ValueError(f"Journal frame length {msg_len} exceeds maximum")
    batch_data = f.read(msg_len)

    if len(batch_data) < msg_len:
        raise ValueError("Truncated journal file (incomplete batch data)")

    return batch_data


def _open_storage_directory(path: Path, create: bool = False) -> int:
    """Walk the directory using pinned descriptors and reject every symlink."""
    absolute = path.absolute()
    descriptor = os.open(absolute.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for component in absolute.parts[1:]:
            if create:
                try:
                    os.mkdir(component, mode=0o700, dir_fd=descriptor)
                    os.fsync(descriptor)
                except FileExistsError:
                    pass
            next_descriptor = os.open(
                component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor,
            )
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except OSError as exc:
        os.close(descriptor)
        raise ValueError("Security: journal directory contains an unsafe path component") from exc


def _open_safe_file(path: Path, mode: str, buffering: int = -1) -> BinaryIO:
    descriptor = _open_storage_directory(path.parent)
    try:
        def opener(name: str, flags: int) -> int:
            return os.open(path.name, flags | os.O_NOFOLLOW, mode=0o600, dir_fd=descriptor)
        handle = open(path, mode, buffering=buffering, opener=opener)
        try:
            if any(flag in mode for flag in ("a", "w", "x")):
                os.fsync(descriptor)
            return handle
        except OSError:
            handle.close()
            raise
    finally:
        os.close(descriptor)


def _rename_safe_file(source: Path, target: Path) -> None:
    if source.parent != target.parent:
        raise ValueError("Security: journal rename must stay within its directory")
    descriptor = _open_storage_directory(source.parent)
    try:
        os.rename(source.name, target.name, src_dir_fd=descriptor, dst_dir_fd=descriptor)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _repair_truncated_active_file(path: Path) -> None:
    """Discard an incomplete final frame before the active file is opened for append."""
    file_size = path.stat().st_size
    valid_end = 0
    with _open_safe_file(path, "r+b", buffering=0) as handle:
        while valid_end < file_size:
            handle.seek(valid_end)
            length_bytes = handle.read(4)
            if len(length_bytes) < 4:
                break

            frame_length = struct.unpack("<I", length_bytes)[0]
            if frame_length > _JOURNAL_MAX_FRAME_SIZE:
                raise ValueError(f"Journal frame length {frame_length} exceeds maximum")

            payload_start = valid_end + 4
            if frame_length > file_size - payload_start:
                break
            valid_end = payload_start + frame_length

        if valid_end != file_size:
            handle.truncate(valid_end)
            handle.flush()
            os.fsync(handle.fileno())


def _serialize_arrow_batch(batch: pa.RecordBatch) -> bytes:
    """Serialize one record batch as a self-contained Arrow IPC stream."""
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, batch.schema) as writer:
        writer.write_batch(batch)
    return sink.getvalue().to_pybytes()


def _is_parquet_file(path: Path) -> bool:
    """Identify legacy Parquet by its leading magic, even when its footer is damaged."""
    try:
        with _open_safe_file(path, "rb") as handle:
            return handle.read(4) == b"PAR1"
    except OSError:
        return False


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

    def __init__(
        self, storage_dir: str = "data/journal", active_log_name: str = "current.arrow"
    ) -> None:
        """
        Initialize the Transaction Journal.

        Args:
            storage_dir: Directory to store journal files.
            active_log_name: Name of the active journal file.
        """
        if fcntl is None or not all(hasattr(os, flag) for flag in ("O_DIRECTORY", "O_NOFOLLOW")):
            raise RuntimeError("TransactionJournal requires POSIX file locks and no-follow directory opens")
        # Strictly validate storage_dir input string first
        _validate_storage_dir_input(storage_dir)

        data_root = Path("data").absolute()

        # Build a safe storage path anchored to data_root from sanitized components
        self.storage_path = _build_storage_path(data_root, storage_dir)

        # Enforce storage_path stays within data_root as an additional guard
        in_root = (
            os.path.commonpath(
                [str(data_root), str(self.storage_path)]
            ) == str(data_root)
        )
        if not in_root:
            raise ValueError(
                "Security: Storage path %s must be within %s",
                self.storage_path, data_root
            )

        safe_log_name = os.path.basename(active_log_name)
        self._validate_filename(safe_log_name)

        # Build active log file path strictly inside storage_path
        self.active_log_file = self.storage_path / safe_log_name
        self._legacy_active_file = (
            self.active_log_file.with_suffix(".parquet")
            if self.active_log_file.suffix != ".parquet"
            else None
        )

        try:
            self.active_log_file.relative_to(self.storage_path)
        except ValueError as exc:
            raise ValueError(
                f"Security: Log file path {self.active_log_file} "
                f"escapes storage directory {self.storage_path}"
            ) from exc

        if self.active_log_file.is_symlink():
            raise ValueError("Security: active log file cannot be a symlink")

        self._journal_file: BinaryIO | None = None
        self._lease_file: BinaryIO | None = None
        self._schema = _EVENT_SCHEMA
        self._lock = threading.Lock()
        self._write_poisoned = False

        # Ensure directory exists
        descriptor = _open_storage_directory(self.storage_path, create=True)
        os.close(descriptor)

        # Open the active log file
        self._open_journal()

    def _open_journal(self) -> None:
        """Open the active Arrow IPC journal for append-only writes."""
        self._acquire_writer_lease()
        try:
            if self.active_log_file.exists() and _is_parquet_file(self.active_log_file):
                legacy_file = self.storage_path / (
                    f"{self.active_log_file.stem}_legacy_{time.time_ns()}.parquet"
                )
                _rename_safe_file(self.active_log_file, legacy_file)
            if self.active_log_file.exists():
                _repair_truncated_active_file(self.active_log_file)
            self._journal_file = _open_safe_file(self.active_log_file, "ab", buffering=0)
        except Exception as e:
            self._release_writer_lease()
            logger.critical("Failed to open transaction journal: %s", e)
            raise

    def _acquire_writer_lease(self) -> None:
        """Reject another owning instance/process before touching journal data."""
        if self._lease_file is not None:
            return
        if fcntl is None:
            raise RuntimeError("TransactionJournal requires POSIX file locks")
        # Public journal filenames cannot start with a dot. Keep the lease
        # outside that namespace so an active *.lock file cannot rotate it.
        path = self.storage_path / f".writer_{self.active_log_file.stem}.lock"
        handle = _open_safe_file(path, "ab", buffering=0)
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.close()
            raise RuntimeError("Journal path already has an owning writer") from exc
        self._lease_file = handle

    def _release_writer_lease(self) -> None:
        handle = self._lease_file
        if handle is not None:
            self._lease_file = None
            handle.close()

    def _close_writer(self) -> None:
        if self._journal_file is not None:
            try:
                self._journal_file.close()
            except Exception as e:
                logger.debug("Error closing journal writer: %s", e)
            self._journal_file = None

    def _should_rotate(self) -> bool:
        try:
            return self.active_log_file.exists() and self.active_log_file.stat().st_size >= _JOURNAL_MAX_FILE_SIZE
        except OSError:
            return False

    def _rotate_if_needed(self) -> None:
        if not self._should_rotate():
            return
        try:
            self._close_writer()
            ts = time.time_ns()
            rotated = self.storage_path / f"{self.active_log_file.stem}_{ts}.arrow"
            _rename_safe_file(self.active_log_file, rotated)
            self._open_journal()
        except OSError as e:
            logger.error("Journal rotation failed: %s", e)
            if self._journal_file is None:
                try:
                    self._open_journal()
                except Exception as ex:
                    logger.debug("Error reopening journal after rotation failure: %s", ex)

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
            logger.error("Schema conversion error for event %s: %s", event_id, e)
            raise

    def _rollback_failed_append(self, start_offset: int) -> bool:
        """Remove a failed frame before allowing another append."""
        try:
            if self._journal_file is None:
                raise OSError("Journal writer closed during append rollback")
            self._journal_file.flush()
            fd = self._journal_file.fileno()
            os.ftruncate(fd, start_offset)
            os.fsync(fd)
            return True
        except Exception as exc:
            self._write_poisoned = True
            logger.critical(
                "Journal append rollback failed; refusing future writes until reopen: %s",
                exc,
            )
            return False

    def _write_event_to_file(self, event_data: dict[str, Any]) -> bool:
        """Perform actual file write operations."""
        with self._lock:
            if self._write_poisoned:
                logger.critical("Journal writer is poisoned; refusing append")
                return False
            if self._journal_file is None:
                self._open_journal()
            if self._journal_file is None:
                return False
            self._rotate_if_needed()
            if self._journal_file is None:
                return False
            try:
                start_offset = os.fstat(self._journal_file.fileno()).st_size
            except (OSError, ValueError) as e:
                logger.critical("Could not inspect journal before append: %s", e)
                return False
            append_started = False
            try:
                batch = self._dict_to_arrow_batch(event_data)
                payload = _serialize_arrow_batch(batch)
                if len(payload) > _JOURNAL_MAX_FRAME_SIZE:
                    raise OSError(
                        f"Serialized journal frame exceeds {_JOURNAL_MAX_FRAME_SIZE} bytes"
                    )
                for chunk in (struct.pack("<I", len(payload)), payload):
                    remaining = memoryview(chunk)
                    while remaining:
                        append_started = True
                        written = self._journal_file.write(remaining)
                        if written is None or written <= 0:
                            raise OSError("Journal write made no progress")
                        remaining = remaining[written:]
                self._journal_file.flush()
                os.fsync(self._journal_file.fileno())
                return True
            except (OSError, pa.ArrowException) as e:
                logger.critical("CRITICAL: Failed to write to transaction journal: %s", e)
                if append_started:
                    self._rollback_failed_append(start_offset)
                return False

    def flush(self) -> None:
        """Flush the journal file and synchronize it to disk."""
        with self._lock:
            if self._journal_file is not None:
                try:
                    self._journal_file.flush()
                    os.fsync(self._journal_file.fileno())
                except Exception as ex:
                    logger.debug("Error flushing journal on flush: %s", ex)

    def log_event(self, event_data: dict[str, Any]) -> bool:
        """Synchronously write and fsync an event before returning."""
        return self._write_event_to_file(event_data)

    def _get_journal_files(self) -> list[Path]:
        files = list(self.storage_path.glob(f"{self.active_log_file.stem}_*.parquet"))
        files += list(self.storage_path.glob(f"{self.active_log_file.stem}_*.arrow"))
        files += list(self.storage_path.glob(f"{self.active_log_file.stem}_*.log"))
        if self._legacy_active_file and self._legacy_active_file.exists():
            files.append(self._legacy_active_file)
        ordered_files = sorted(set(files) - {self.active_log_file})
        if self.active_log_file.exists():
            ordered_files.append(self.active_log_file)
        return ordered_files

    def _iter_parquet_file(self, path: Path) -> Generator[dict[str, Any], None, None]:
        if path.suffix == ".parquet":
            try:
                with _open_safe_file(path, "rb") as handle:
                    table = pq.read_table(handle, schema=self._schema)
                for batch in table.to_batches():
                    for row in batch.to_pylist():
                        yield _unpack_row_data(row)
            except Exception as exc:
                raise ValueError(f"Could not replay legacy Parquet journal {path}: {exc}") from exc
            return

        with _open_safe_file(path, "rb") as handle:
            yield from _iterate_journal_batches(handle, self._schema)

    def replay(self) -> Generator[dict[str, Any], None, None]:
        """
        Replay all events from the journal.
        Reads binary Arrow batches and yields them as Dictionaries.
        """
        self.flush()
        with self._lock:
            self._close_writer()
        files = self._get_journal_files()
        try:
            for jf in files:
                yield from self._iter_parquet_file(jf)
        finally:
            with self._lock:
                self._open_journal()

    def read_since(
        self, cursor: tuple[int, int] | None = None,
    ) -> tuple[list[dict[str, Any]], tuple[int, int]]:
        """Read durable frames after an inode/offset cursor, including rotated files.

        A removed or truncated cursor fails closed. Legacy Parquet is read only
        during the initial scan; subsequent reads start at a verified Arrow boundary.
        """
        with self._lock:
            if self._journal_file is None:
                raise RuntimeError("Cannot read a closed transaction journal")
            self._journal_file.flush()
            os.fsync(self._journal_file.fileno())
            # ponytail: enumerate archive names per tail read; compact archives
            # only when file-count profiling warrants a persistent manifest.
            files = self._get_journal_files()
            if not files or files[-1] != self.active_log_file:
                raise ValueError("Active journal file is missing")
            if cursor is not None:
                position = next((i for i, path in enumerate(files) if path.stat().st_ino == cursor[0]), None)
                if position is None:
                    raise ValueError("Journal cursor file is missing")
                files = files[position:]
                if cursor[1] > files[0].stat().st_size:
                    raise ValueError("Journal cursor file was truncated")
            records: list[dict[str, Any]] = []
            for i, path in enumerate(files):
                if path.suffix == ".parquet":
                    records.extend(self._iter_parquet_file(path))
                    continue
                with _open_safe_file(path, "rb") as handle:
                    if i == 0 and cursor is not None:
                        handle.seek(cursor[1])
                    records.extend(_iterate_journal_batches(handle, self._schema))
                    next_cursor = (path.stat().st_ino, handle.tell())
            return records, next_cursor

    def close(self) -> None:
        """Close the journal file handle."""
        with self._lock:
            self._close_writer()
            self._release_writer_lease()

    def clear(self) -> None:
        """Clear the current journal."""
        with self._lock:
            self._acquire_writer_lease()
            self._close_writer()
            try:
                for jf in self._get_journal_files():
                    try:
                        descriptor = _open_storage_directory(jf.parent)
                        try:
                            os.unlink(jf.name, dir_fd=descriptor)
                            os.fsync(descriptor)
                        finally:
                            os.close(descriptor)
                    except OSError:
                        pass
                self._open_journal()
                logger.info("Transaction journal cleared (Arrow format).")
            except OSError as e:
                logger.error("Failed to clear journal: %s", e)
