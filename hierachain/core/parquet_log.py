"""
Parquet Log Module

This module provides functionality for handling Parquet-based logging, allowing
for writing and reading Parquet log files with segmentation support. It also
includes a custom logging handler for integration with Python's logging
framework.
"""

import atexit
import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import orjson
import pyarrow as pa
import pyarrow.parquet as pq

_lock = threading.Lock()
_SCHEMA = pa.schema([("timestamp", pa.float64()), ("data", pa.string())])
_ROW_GROUP_ROWS = 128
_SEGMENT_ROWS = 1024
_writers: dict[Path, tuple[pq.ParquetWriter, Path, int, list[dict[str, Any]]]] = {}


def _normalize_path(path: str | Path) -> Path:
    p = Path(path)
    return p if p.suffix == ".parquet" else p.with_suffix(".parquet")


def _segment_directory(path: Path) -> Path:
    return path.with_name(f"{path.name}.segments")


def _flush(path: Path) -> None:
    writer, _, _, pending = _writers[path]
    if pending:
        writer.write_table(pa.Table.from_pylist(pending, schema=_SCHEMA))
        pending.clear()


def _finish(path: Path) -> None:
    writer, temporary_path, _, _ = _writers[path]
    _flush(path)
    writer.close()
    final_path = (
        _segment_directory(path)
        / f"part-{time.time_ns():020d}-{uuid.uuid4().hex}.parquet"
    )
    os.replace(temporary_path, final_path)
    del _writers[path]


def _close_all() -> None:
    with _lock:
        for path in tuple(_writers):
            try:
                _finish(path)
            except Exception as e:
                logging.getLogger(__name__).debug(
                    "Failed to finalize parquet log segment: %s", e
                )


atexit.register(_close_all)


def write_parquet_log(path: str | Path, record: dict) -> None:
    p = _normalize_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "timestamp": float(record.get("timestamp", time.time())),
        "data": orjson.dumps(record, default=str).decode(),
    }
    with _lock:
        if p not in _writers:
            directory = _segment_directory(p)
            directory.mkdir(parents=True, exist_ok=True)
            temporary_path = directory / f".active-{uuid.uuid4().hex}.tmp"
            _writers[p] = (
                pq.ParquetWriter(temporary_path, _SCHEMA),
                temporary_path,
                0,
                [],
            )

        writer, temporary_path, count, pending = _writers[p]
        pending.append(row)
        count += 1
        _writers[p] = (writer, temporary_path, count, pending)
        if len(pending) >= _ROW_GROUP_ROWS or count >= _SEGMENT_ROWS:
            _flush(p)
        if count >= _SEGMENT_ROWS:
            _finish(p)


def read_parquet_log(path: str | Path) -> pa.Table:
    """Read legacy single-file logs and the segments written by this module."""
    p = _normalize_path(path)
    with _lock:
        if p in _writers:
            _finish(p)

    files = [p] if p.is_file() and p.stat().st_size else []
    files.extend(sorted(_segment_directory(p).glob("*.parquet")))
    if not files:
        return pa.Table.from_pylist([], schema=_SCHEMA)

    tables = [pq.read_table(file, schema=_SCHEMA) for file in files]
    return tables[0] if len(tables) == 1 else pa.concat_tables(tables)


class ParquetLogHandler(logging.Handler):
    def __init__(self, parquet_path: str | Path):
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
