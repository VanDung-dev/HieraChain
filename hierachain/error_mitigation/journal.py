"""
Event Journal System for HieraChain.

This module provides a durability layer to ensure that events are
safely persisted to physical storage before being processed.
This protects against data loss during power failures, system crashes, or
rapid shutdowns.

Path/file helpers and the Arrow codec live in ``journal_io`` and
``journal_codec`` so this module keeps only the journal lifecycle.
"""

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

from hierachain.core.block import EVENT_SCHEMA as _EVENT_SCHEMA
from hierachain.error_mitigation.journal_codec import (
    _iterate_journal_batches,
    _pack_extra_fields,
    _process_details_field,
    _serialize_arrow_batch,
    _serialize_data_field,
    _unpack_row_data,
)
from hierachain.error_mitigation.journal_constants import (
    _JOURNAL_MAX_FILE_SIZE,
    _JOURNAL_MAX_FRAME_SIZE,
)
from hierachain.error_mitigation.journal_io import (
    _build_storage_path,
    _file_write_state,
    _is_parquet_file,
    _open_safe_file,
    _open_storage_directory,
    _rename_safe_file,
    _repair_truncated_active_file,
    _validate_storage_dir_input,
)

try:
    import fcntl
except ImportError:  # Keep package importable on platforms without POSIX locks.
    fcntl = None

logger = logging.getLogger(__name__)


class EventJournal:
    """
    Append-only journal for durable event logging using Apache Arrow.

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
        Initialize the event journal.

        Args:
            storage_dir: Directory to store journal files.
            active_log_name: Name of the active journal file.
        """
        if fcntl is None or not all(hasattr(os, flag) for flag in ("O_DIRECTORY", "O_NOFOLLOW")):
            raise RuntimeError("EventJournal requires POSIX file locks and no-follow directory opens")
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
        self._synced_file_state: tuple[int, int, int, int, int] | None = None

        # Ensure directory exists
        descriptor = _open_storage_directory(self.storage_path, create=True)
        os.close(descriptor)

        # Open the active log file
        self._open_journal()

    def _open_journal(self) -> None:
        """Open the active Arrow IPC journal for append-only writes."""
        self._synced_file_state = None
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
            self._write_poisoned = False
        except (OSError, ValueError, RuntimeError) as e:
            self._release_writer_lease()
            logger.critical("Failed to open event journal: %s", e)
            raise

    def _acquire_writer_lease(self) -> None:
        """Reject another owning instance/process before touching journal data."""
        if self._lease_file is not None:
            return
        if fcntl is None:
            raise RuntimeError("EventJournal requires POSIX file locks")
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
        self._synced_file_state = None
        if self._journal_file is not None:
            try:
                self._journal_file.close()
            except (OSError, ValueError) as e:
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
                except (OSError, ValueError, RuntimeError) as ex:
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
        self._synced_file_state = None
        try:
            if self._journal_file is None:
                raise OSError("Journal writer closed during append rollback")
            self._journal_file.flush()
            fd = self._journal_file.fileno()
            os.ftruncate(fd, start_offset)
            os.fsync(fd)
            self._synced_file_state = _file_write_state(fd)
            return True
        except (OSError, ValueError) as exc:
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
                        self._synced_file_state = None
                        append_started = True
                        written = self._journal_file.write(remaining)
                        if written is None or written <= 0:
                            raise OSError("Journal write made no progress")
                        remaining = remaining[written:]
                self._journal_file.flush()
                os.fsync(self._journal_file.fileno())
                self._synced_file_state = _file_write_state(self._journal_file.fileno())
                return True
            except (OSError, pa.ArrowException) as e:
                logger.critical("CRITICAL: Failed to write to event journal: %s", e)
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
                    self._synced_file_state = _file_write_state(self._journal_file.fileno())
                except (OSError, ValueError) as ex:
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
        ordered_files = sorted(
            set(files) - {self.active_log_file},
            key=self._journal_file_order,
        )
        if self.active_log_file.exists():
            ordered_files.append(self.active_log_file)
        return ordered_files

    def _journal_file_order(self, path: Path) -> tuple[int, int]:
        prefix = f"{self.active_log_file.stem}_"
        suffix = path.stem.removeprefix(prefix) if path.stem.startswith(prefix) else path.stem
        if suffix.startswith("legacy_"):
            suffix = suffix.removeprefix("legacy_")
            rank = 0
        else:
            rank = 1
        marker = suffix.split("_", 1)[0]
        try:
            timestamp = int(marker)
        except ValueError:
            timestamp = 0
        return rank, timestamp

    def _iter_parquet_file(self, path: Path) -> Generator[dict[str, Any], None, None]:
        if path.suffix == ".parquet":
            try:
                with _open_safe_file(path, "rb") as handle:
                    table = pq.read_table(handle, schema=self._schema)
                for batch in table.to_batches():
                    for row in batch.to_pylist():
                        yield _unpack_row_data(row)
            except (OSError, ValueError, pa.ArrowException) as exc:
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
        ACKed writes already cover their file state with fsync. Read-back syncs
        again only if that state is unknown or has changed, and still reads disk.
        """
        with self._lock:
            if self._journal_file is None:
                raise RuntimeError("Cannot read a closed event journal")
            self._journal_file.flush()
            file_state = _file_write_state(self._journal_file.fileno())
            if file_state != self._synced_file_state:
                # ACKed appends already synchronized this exact state. Reopen,
                # external changes, or uncertain writes require a fresh sync.
                self._synced_file_state = None
                os.fsync(self._journal_file.fileno())
                self._synced_file_state = _file_write_state(self._journal_file.fileno())
            # ponytail: enumerate archive names per tail read; compact archives
            # only when file-count profiling warrants a persistent manifest.
            files = self._get_journal_files()
            if not files or files[-1] != self.active_log_file:
                raise ValueError("Active journal file is missing")
            active_state = self.active_log_file.stat()
            if (active_state.st_dev, active_state.st_ino) != file_state[:2]:
                raise ValueError("Active journal file was replaced")
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
                logger.info("Event journal cleared (Arrow format).")
            except OSError as e:
                logger.error("Failed to clear journal: %s", e)


# Backward-compatible alias; the event ledger calls this an event journal.
TransactionJournal = EventJournal
