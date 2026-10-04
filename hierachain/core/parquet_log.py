"""
Parquet Log Module

This module provides functionality for handling Parquet-based logging, allowing
for writing and reading Parquet log files with segmentation support. It also
includes a custom logging handler for integration with Python's logging
framework.
"""

import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from hierachain.serialization import dumps_json

_lock = threading.Lock()
_SCHEMA = pa.schema([("timestamp", pa.float64()), ("data", pa.string())])
_ROW_GROUP_ROWS = 128
_SEGMENT_ROWS = 1024
# Each active segment is published as a complete, durable snapshot before ACK.
# Only this bounded segment is rewritten; sealed segments are never rewritten.
_writers: dict[Path, tuple[Path, list[dict[str, Any]]]] = {}


def _normalize_path(path: str | Path) -> Path:
    p = Path(path)
    return p if p.suffix == ".parquet" else p.with_suffix(".parquet")


def _segment_directory(path: Path) -> Path:
    return path.with_name(f"{path.name}.segments")


def _sync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _finish(path: Path) -> None:
    # Every successful append is already published, including a valid footer.
    _writers.pop(path, None)


def write_parquet_log(path: str | Path, record: dict[str, Any]) -> None:
    """Publish a complete segment snapshot and fsync it before returning.

    A failed append can have been published if directory fsync failed. In that
    case the segment is sealed, so later appends cannot overwrite uncertain data.
    """
    p = _normalize_path(path)
    row = {
        "timestamp": float(record.get("timestamp", time.time())),
        "data": dumps_json(record, default=str),
    }
    with _lock:
        p.parent.mkdir(parents=True, exist_ok=True)
        directory = _segment_directory(p)
        directory.mkdir(parents=True, exist_ok=True)
        _sync_directory(directory.parent)
        final_path, prior = _writers.get(p, (
            directory / f"part-{time.time_ns():020d}-{uuid.uuid4().hex}.parquet", [],
        ))
        rows = [*prior, row]
        temporary_path = directory / f".active-{uuid.uuid4().hex}.tmp"
        try:
            pq.write_table(
                pa.Table.from_pylist(rows, schema=_SCHEMA), temporary_path,
                row_group_size=_ROW_GROUP_ROWS,
            )
            with temporary_path.open("rb") as file:
                os.fsync(file.fileno())
            os.replace(temporary_path, final_path)
            _sync_directory(directory)
        except Exception:
            _finish(p)
            raise
        finally:
            temporary_path.unlink(missing_ok=True)
        if len(rows) >= _SEGMENT_ROWS:
            _finish(p)
        else:
            _writers[p] = (final_path, rows)


def read_parquet_log(path: str | Path) -> pa.Table:
    """Read legacy logs and a consistent snapshot of published segments."""
    p = _normalize_path(path)
    with _lock:
        _finish(p)
        files = [p] if p.is_file() and p.stat().st_size else []
        files.extend(sorted(_segment_directory(p).glob("*.parquet")))
        if not files:
            return pa.Table.from_pylist([], schema=_SCHEMA)
        tables = [pq.read_table(file, schema=_SCHEMA) for file in files]
        return tables[0] if len(tables) == 1 else pa.concat_tables(tables)


class ParquetLogHandler(logging.Handler):
    def __init__(self, parquet_path: str | Path) -> None:
        super().__init__()
        self.parquet_path = _normalize_path(parquet_path)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            write_parquet_log(
                self.parquet_path,
                {
                    "level": record.levelname,
                    "logger": record.name,
                    "message": msg,
                    "created": record.created,
                },
            )
        except (OSError, pa.ArrowException, ValueError, TypeError):
            self.handleError(record)

    def close(self) -> None:
        try:
            with _lock:
                if self.parquet_path in _writers:
                    _finish(self.parquet_path)
        finally:
            super().close()
