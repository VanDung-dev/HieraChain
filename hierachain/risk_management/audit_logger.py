"""
Enhanced Audit Logger for HieraChain Ledger

Provides comprehensive audit logging capabilities for tracking
system activities, risk events, and mitigation actions.
"""

from __future__ import annotations

import csv
import hashlib
import io
import logging
import os
import sqlite3
import struct
import threading
import time
import uuid
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, cast

import pyarrow as pa
import pyarrow.parquet as pq

from hierachain.adapters.database.audit_manifest import PostgresAuditManifest
from hierachain.config.settings import settings
from hierachain.risk_management.types import (
    AuditEvent,
    AuditEventType,
    AuditFilter,
    AuditSeverity,
)
from hierachain.serialization import dumps_canonical_json, dumps_json, loads_json

_AUDIT_SCHEMA = pa.schema([
    ("event_id", pa.string()),
    ("event_type", pa.string()),
    ("severity", pa.string()),
    ("timestamp", pa.float64()),
    ("source_component", pa.string()),
    ("description", pa.string()),
    ("details", pa.string()),
    ("user_id", pa.string()),
    ("session_id", pa.string()),
    ("ip_address", pa.string()),
    ("correlation_id", pa.string()),
    ("affected_entities", pa.string()),
])

_AUDIT_MAX_FILE_SIZE = 100 * 1024 * 1024

logger = logging.getLogger(__name__)

__all__ = [
    "ArrowAuditStorage",
    "AuditIntegrityStatus",
    "AuditEvent",
    "AuditEventType",
    "AuditFilter",
    "AuditLogger",
    "AuditReadResult",
    "AuditSeverity",
    "AuditStorage",
    "DatabaseAuditStorage",
    "FileAuditStorage",
    "verify_integrity",
]


class AuditStorage:
    def store_event(self, event: AuditEvent) -> bool:
        raise NotImplementedError

    def retrieve_events(
        self, filter_criteria: AuditFilter, limit: int | None = None
    ) -> list[AuditEvent]:
        raise NotImplementedError

    def get_event_count(self, filter_criteria: AuditFilter) -> int:
        raise NotImplementedError


def _audit_event_to_row(event: AuditEvent) -> dict[str, Any]:
    normalized = event.to_dict()
    return {
        "event_id": normalized["event_id"],
        "event_type": normalized["event_type"],
        "severity": normalized["severity"],
        "timestamp": normalized["timestamp"],
        "source_component": normalized["source_component"],
        "description": normalized["description"],
        "details": dumps_json(normalized["details"]) if normalized["details"] else "",
        "user_id": normalized["user_id"],
        "session_id": normalized["session_id"],
        "ip_address": normalized["ip_address"],
        "correlation_id": normalized["correlation_id"] or "",
        "affected_entities": (
            dumps_json(normalized["affected_entities"])
            if normalized["affected_entities"] is not None else ""
        ),
    }


def _row_to_audit_event(row: dict[str, Any]) -> AuditEvent:
    details = loads_json(row["details"]) if row.get("details") else {}
    affected = loads_json(row["affected_entities"]) if row.get("affected_entities") else None
    return AuditEvent(
        event_id=row["event_id"],
        event_type=AuditEventType(row["event_type"]),
        severity=AuditSeverity(row["severity"]),
        timestamp=row["timestamp"],
        source_component=row["source_component"],
        description=row["description"],
        details=details,
        user_id=row["user_id"],
        session_id=row["session_id"],
        ip_address=row["ip_address"],
        correlation_id=row["correlation_id"] or None,
        affected_entities=affected,
    )


class ArrowAuditStorage(AuditStorage):
    def __init__(self, audit_directory: str = "log/risk_management/audit_logs", active_name: str = "audit_current.parquet"):
        self.audit_directory = Path(audit_directory)
        self.audit_directory.mkdir(parents=True, exist_ok=True)
        self.active_log_file = self.audit_directory / active_name
        self._schema = _AUDIT_SCHEMA
        self._lock = threading.Lock()
        self._pq_writer: pq.ParquetWriter | None = None
        self._active_event_count: int | None = None
        self._open()

    def _open(self):
        try:
            self._archive_active_file()
            self._pq_writer = pq.ParquetWriter(self.active_log_file, self._schema)
            self._active_event_count = 0
        except OSError as e:
            logging.error("Failed to open audit journal: %s", e)
            raise

    def _archive_active_file(self):
        if not self.active_log_file.exists():
            return
        if self._active_event_count == 0 or self.active_log_file.stat().st_size == 0:
            self.active_log_file.unlink()
            return
        rotated = self.audit_directory / f"audit_{time.time_ns()}_{uuid.uuid4().hex}.parquet"
        self.active_log_file.rename(rotated)

    def _close_writer(self):
        if self._pq_writer is not None:
            self._pq_writer.close()
            self._pq_writer = None

    def _should_rotate(self) -> bool:
        try:
            return self.active_log_file.exists() and self.active_log_file.stat().st_size >= _AUDIT_MAX_FILE_SIZE
        except OSError:
            return False

    def _rotate_if_needed(self):
        if not self._should_rotate():
            return
        try:
            self._close_writer()
            self._archive_active_file()
            self._open()
        except OSError as e:
            logging.error("Audit rotation failed: %s", e)
            if self._pq_writer is None:
                try:
                    self._open()
                except Exception as ex:
                    logging.debug("Error reopening audit writer after rotation failure: %s", ex)

    def _get_files(self) -> list[Path]:
        files = sorted(path for path in self.audit_directory.glob("audit_*.parquet") if path != self.active_log_file)
        files += sorted(self.audit_directory.glob("audit_*.arrow"))
        files += sorted(self.audit_directory.glob("audit_*.log"))
        files += sorted(self.audit_directory.glob("audit_*.jsonl"))
        if self._active_event_count and self.active_log_file.exists() and self.active_log_file not in files:
            files.append(self.active_log_file)
        return sorted(set(files))

    def _seal_active_file(self) -> None:
        """Make current writes readable before a snapshot query or cleanup."""
        with self._lock:
            self._close_writer()
            self._archive_active_file()
            self._open()

    def _iter_parquet(self, path: Path) -> Iterator[AuditEvent]:
        if path.suffix == ".parquet":
            table = pq.read_table(path, schema=self._schema)
            for batch in table.to_batches():
                for row in batch.to_pylist():
                    yield _row_to_audit_event(row)
            return
        # Legacy Arrow archives use length-prefixed record batches. A damaged
        # Parquet file must never be reinterpreted as a legacy archive.
        with open(path, "rb") as stream:
            file_size = os.fstat(stream.fileno()).st_size
            while True:
                header = stream.read(4)
                if not header:
                    return
                if len(header) != 4:
                    raise RuntimeError("Truncated audit frame header")
                length = struct.unpack("<I", header)[0]
                if length == 0 or length > file_size - stream.tell():
                    raise RuntimeError("Truncated or invalid audit frame")
                payload = stream.read(length)
                batch = pa.ipc.read_record_batch(payload, self._schema)
                if batch.num_rows == 0:
                    raise RuntimeError("Empty audit frame")
                for row in batch.to_pylist():
                    yield _row_to_audit_event(row)

    def store_event(self, event: AuditEvent) -> bool:
        row = _audit_event_to_row(event)
        try:
            with self._lock:
                if self._pq_writer is None:
                    self._open()
                self._rotate_if_needed()
                if self._pq_writer is None:
                    return False
                pydict = {name: [row.get(name, "")] for name in self._schema.names}
                batch = pa.record_batch(pydict, schema=self._schema)
                table = pa.Table.from_batches([batch])
                self._pq_writer.write_table(table)
                self._active_event_count = (self._active_event_count or 0) + 1
                return True
        except Exception as e:
            logging.error("Failed to store audit event (parquet): %s", e)
            return False

    def retrieve_events(self, filter_criteria: AuditFilter, limit: int | None = None) -> list[AuditEvent]:
        events: list[AuditEvent] = []
        try:
            self._seal_active_file()
            for jf in reversed(self._get_files()):
                source = _iter_events_from_file(jf) if jf.suffix == ".jsonl" else self._iter_parquet(jf)
                for ev in source:
                    if filter_criteria.matches(ev):
                        events.append(ev)
                        if limit is not None and limit > 0 and len(events) >= limit:
                            return events
            return events
        except Exception as e:
            raise RuntimeError("Failed to retrieve audit archive") from e

    def get_event_count(self, filter_criteria: AuditFilter) -> int:
        """Count Parquet rows from metadata or bounded column batches."""
        if any(values == [] for values in (
            filter_criteria.event_types,
            filter_criteria.severity_levels,
            filter_criteria.source_components,
            filter_criteria.user_ids,
        )):
            return 0

        try:
            self._seal_active_file()
        except Exception as exc:
            raise RuntimeError("Failed to count audit archive") from exc
        event_types = (
            {value.value for value in filter_criteria.event_types}
            if filter_criteria.event_types is not None else None
        )
        severity_levels = (
            {value.value for value in filter_criteria.severity_levels}
            if filter_criteria.severity_levels is not None else None
        )
        sources = set(filter_criteria.source_components) if filter_criteria.source_components is not None else None
        users = set(filter_criteria.user_ids) if filter_criteria.user_ids is not None else None
        columns = [
            name for name, enabled in (
                ("event_type", event_types is not None),
                ("severity", severity_levels is not None),
                ("source_component", sources is not None),
                ("user_id", users is not None),
                ("timestamp", filter_criteria.time_range is not None),
            ) if enabled
        ]
        count = 0
        try:
            for path in self._get_files():
                if path.suffix == ".parquet":
                    parquet = pq.ParquetFile(path)
                    if not columns:
                        count += parquet.metadata.num_rows
                        continue
                    for batch in parquet.iter_batches(batch_size=4096, columns=columns):
                        for row in batch.to_pylist():
                            if event_types is not None and row["event_type"] not in event_types:
                                continue
                            if severity_levels is not None and row["severity"] not in severity_levels:
                                continue
                            if sources is not None and row["source_component"] not in sources:
                                continue
                            if users is not None and row["user_id"] not in users:
                                continue
                            if filter_criteria.time_range is not None:
                                start, end = filter_criteria.time_range
                                if not start <= row["timestamp"] <= end:
                                    continue
                            count += 1
                else:
                    events = _iter_events_from_file(path) if path.suffix == ".jsonl" else self._iter_parquet(path)
                    count += sum(filter_criteria.matches(event) for event in events)
            return count
        except Exception as exc:
            raise RuntimeError("Failed to count audit archive") from exc

    def cleanup_old_events(self, max_age_seconds: float) -> int:
        """Delete only Parquet archives whose every event predates the cutoff."""
        if max_age_seconds < 0:
            raise ValueError("max_age_seconds must be nonnegative")
        cutoff = time.time() - max_age_seconds
        self._seal_active_file()
        expired: list[tuple[Path, int]] = []
        try:
            for path in self._get_files():
                if path == self.active_log_file or path.suffix != ".parquet":
                    continue
                parquet = pq.ParquetFile(path)
                all_expired = all(
                    value is not None and value < cutoff
                    for batch in parquet.iter_batches(batch_size=4096, columns=["timestamp"])
                    for value in batch.column(0).to_pylist()
                )
                if all_expired:
                    expired.append((path, parquet.metadata.num_rows))
            for path, _ in expired:
                path.unlink()
            return sum(rows for _, rows in expired)
        except Exception as exc:
            raise RuntimeError("Failed to clean up audit archive") from exc

    def close(self):
        with self._lock:
            self._close_writer()


class DatabaseAuditStorage(AuditStorage):
    """Persistent audit storage using SQLite database."""
    def __init__(self, db_path: str = "hierachain.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    source_component TEXT NOT NULL,
                    description TEXT NOT NULL,
                    details TEXT,  -- JSON string
                    user_id TEXT,
                    session_id TEXT,
                    ip_address TEXT,
                    correlation_id TEXT,
                    affected_entities TEXT
                )
                """
            )
            columns = {row[1] for row in cursor.execute("PRAGMA table_info(audit_events)")}
            if "affected_entities" not in columns:
                cursor.execute("ALTER TABLE audit_events ADD COLUMN affected_entities TEXT")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_events (timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_events (event_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_severity ON audit_events (severity)")
            conn.commit()
        finally:
            conn.close()

    def store_event(self, event: AuditEvent) -> bool:
        conn = None
        try:
            normalized = event.to_dict()
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO audit_events 
                (event_id, event_type, severity, timestamp, source_component, description, details, user_id, session_id, ip_address, correlation_id, affected_entities)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized["event_id"],
                    normalized["event_type"],
                    normalized["severity"],
                    normalized["timestamp"],
                    normalized["source_component"],
                    normalized["description"],
                    dumps_json(normalized["details"]) if normalized["details"] else None,
                    normalized["user_id"],
                    normalized["session_id"],
                    normalized["ip_address"],
                    normalized["correlation_id"],
                    (
                        dumps_json(normalized["affected_entities"])
                        if normalized["affected_entities"] is not None else None
                    ),
                )
            )
            conn.commit()
            return True
        except Exception as e:
            logging.error("Failed to store audit event in DB: %s", str(e))
            return False
        finally:
            if conn:
                conn.close()

    @staticmethod
    def _filter_sql(filter_criteria: AuditFilter) -> tuple[str, list[Any]]:
        """Build the same predicate for retrieval and count queries."""
        query = " WHERE 1=1"
        params: list[Any] = []
        for column, values in (
            ("event_type", filter_criteria.event_types),
            ("severity", filter_criteria.severity_levels),
            ("source_component", filter_criteria.source_components),
            ("user_id", filter_criteria.user_ids),
        ):
            if values is None:
                continue
            if not values:
                query += " AND 0=1"
                continue
            placeholders = ",".join("?" for _ in values)
            query += f" AND {column} IN ({placeholders})"
            params.extend(
                value.value if isinstance(value, (AuditEventType, AuditSeverity)) else value
                for value in values
            )
        if filter_criteria.time_range is not None:
            query += " AND timestamp >= ? AND timestamp <= ?"
            params.extend(filter_criteria.time_range)
        return query, params

    def retrieve_events(
        self, filter_criteria: AuditFilter, limit: int | None = None
    ) -> list[AuditEvent]:
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            predicate, params = self._filter_sql(filter_criteria)
            query = "SELECT * FROM audit_events" + predicate
            query += " ORDER BY timestamp DESC"
            if limit is not None and limit > 0:
                query += " LIMIT ?"
                params.append(limit)
                
            cursor.execute(query, params)
            rows = cursor.fetchall()
            events = []
            for r in rows:
                ev_dict = dict(r)
                if ev_dict.get('details'):
                    ev_dict['details'] = loads_json(ev_dict['details'])
                else:
                    ev_dict['details'] = {}
                if ev_dict.get('affected_entities'):
                    ev_dict['affected_entities'] = loads_json(ev_dict['affected_entities'])
                else:
                    ev_dict['affected_entities'] = None
                # Match enum types
                ev_dict['event_type'] = AuditEventType(ev_dict['event_type'])
                ev_dict['severity'] = AuditSeverity(ev_dict['severity'])
                events.append(AuditEvent.from_dict(ev_dict))
            return events
        except Exception as e:
            raise RuntimeError("Failed to retrieve audit events from DB") from e
        finally:
            if conn:
                conn.close()

    def get_event_count(self, filter_criteria: AuditFilter) -> int:
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            predicate, params = self._filter_sql(filter_criteria)
            query = "SELECT COUNT(*) FROM audit_events" + predicate
            cursor.execute(query, params)
            count = cursor.fetchone()[0]
            return count
        except Exception as e:
            raise RuntimeError("Failed to count audit events in DB") from e
        finally:
            if conn:
                conn.close()

    def cleanup_old_events(self, max_age_seconds: float) -> int:
        """Remove audit events older than max_age_seconds."""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cutoff = time.time() - max_age_seconds
            cursor.execute("DELETE FROM audit_events WHERE timestamp < ?", (cutoff,))
            deleted = cursor.rowcount
            conn.commit()
            return deleted
        except Exception as e:
            logging.error("Failed to cleanup audit events in DB: %s", str(e))
            return 0
        finally:
            if conn:
                conn.close()



def _parse_event_line(line: str) -> AuditEvent:
    try:
        return AuditEvent.from_dict(loads_json(line.strip()))
    except (KeyError, ValueError) as e:
        raise RuntimeError("Invalid audit event record") from e


def _iter_events_from_file(log_file: Path) -> Iterator[AuditEvent]:
    with open(log_file, 'r', encoding='utf-8') as f:
        for line in f:
            event = _parse_event_line(line)
            if event:
                yield event


def _read_and_filter_file(
    log_file: Path,
    filter_criteria: AuditFilter,
    events: list[AuditEvent],
    limit: int | None
) -> bool:
    for event in _iter_events_from_file(log_file):
        if filter_criteria.matches(event):
            events.append(event)
            if limit and len(events) >= limit:
                return True
    return False


class FileAuditStorage(AuditStorage):
    def __init__(self, audit_directory: str = "log/risk_management/audit_logs"):
        self.audit_directory = Path(audit_directory)
        self.audit_directory.mkdir(parents=True, exist_ok=True)
        self.current_file = None
        self.current_date = None
        self._lock = threading.Lock()

    def _get_log_file(self, timestamp: float) -> Path:
        date_str = time.strftime("%Y-%m-%d", time.localtime(timestamp))
        return self.audit_directory / f"audit_{date_str}.jsonl"

    def store_event(self, event: AuditEvent) -> bool:
        try:
            with self._lock:
                log_file = self._get_log_file(event.timestamp)
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(event.to_json() + '\n')
                return True
        except Exception as e:
            logging.error("Failed to store audit event: %s", str(e))
            return False

    def retrieve_events(
        self, filter_criteria: AuditFilter, limit: int | None = None
    ) -> list[AuditEvent]:
        events = []
        try:
            log_files = self._get_files_to_search(filter_criteria.time_range)
            for log_file in log_files:
                if _read_and_filter_file(log_file, filter_criteria, events, limit):
                    break
            return events
        except Exception as e:
            raise RuntimeError("Failed to retrieve audit events") from e

    def _get_files_to_search(self, time_range: tuple | None) -> list[Path]:
        if not time_range:
            return sorted(
                list(self.audit_directory.glob("audit_*.jsonl")), reverse=True
            )
        start_time, end_time = time_range
        current_day = datetime.fromtimestamp(start_time).date()
        end_day = datetime.fromtimestamp(end_time).date()
        log_files: list[Path] = []
        while current_day <= end_day:
            log_file = self._get_log_file_for_date(current_day)
            if log_file.exists():
                log_files.append(log_file)
            current_day += timedelta(days=1)
        return log_files

    def _get_log_file_for_date(self, current_day: date) -> Path:
        """Return the daily file for a local calendar date."""
        return self.audit_directory / f"audit_{current_day:%Y-%m-%d}.jsonl"

    def get_event_count(self, filter_criteria: AuditFilter) -> int:
        return len(self.retrieve_events(filter_criteria))


def verify_integrity(
    events: list[AuditEvent],
    expected_hashes: Mapping[str, str] | None = None,
) -> bool:
    """Compare events with a trusted digest manifest captured when they were written.

    Missing manifests, legacy events without digests, duplicate IDs, and incomplete
    manifests fail closed. Keep expected_hashes separate from the audit archive.
    """
    if expected_hashes is None or len(expected_hashes) != len(events):
        return False

    seen_ids: set[str] = set()
    for event in events:
        if event.event_id in seen_ids:
            return False
        expected_hash = expected_hashes.get(event.event_id)
        valid_hashes = {event.calculate_hash()}
        timestamp = event.timestamp
        if isinstance(timestamp, (int, float)) and float(timestamp).is_integer():
            # Older writers hashed integer timestamps before storage backends
            # normalized their REAL/float representation.
            legacy_data = event.to_dict()
            legacy_data["timestamp"] = int(timestamp)
            legacy_content = dumps_canonical_json(legacy_data, default=str)
            valid_hashes.add(hashlib.sha256(legacy_content).hexdigest())
        if expected_hash not in valid_hashes:
            return False
        seen_ids.add(event.event_id)
    return seen_ids == set(expected_hashes)


class AuditIntegrityStatus(str, Enum):
    """Integrity outcome for an audit read."""

    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    FAILED = "failed"


@dataclass(frozen=True)
class AuditReadResult:
    """Audit events with an explicit trusted-manifest verification outcome."""

    events: list[AuditEvent]
    integrity_status: AuditIntegrityStatus

    @property
    def is_verified(self) -> bool:
        return self.integrity_status is AuditIntegrityStatus.VERIFIED


class AuditLogger:
    def __init__(
        self,
        storage: AuditStorage | None = None,
        enable_real_time_alerts: bool = True,
        integrity_digest_writer: Callable[[str, str], None] | None = None,
        integrity_digest_reader: Callable[[], Mapping[str, str]] | None = None,
    ):
        write_manifest_url = (os.getenv("HRC_AUDIT_MANIFEST_WRITE_URL") or "").strip()
        read_manifest_url = (os.getenv("HRC_AUDIT_MANIFEST_READ_URL") or "").strip()
        if integrity_digest_writer is None and write_manifest_url:
            integrity_digest_writer = PostgresAuditManifest(write_manifest_url).write_digest
        if integrity_digest_reader is None and read_manifest_url:
            integrity_digest_reader = PostgresAuditManifest(read_manifest_url).load_hashes
        if integrity_digest_writer is None and settings.env == "production":
            raise RuntimeError("Production audit logging requires a trusted digest manifest writer")
        self.storage = storage or ArrowAuditStorage("log/risk_management/audit_logs")
        self.enable_real_time_alerts = enable_real_time_alerts
        self.integrity_digest_writer = integrity_digest_writer
        self.integrity_digest_reader = integrity_digest_reader
        self.logger = logging.getLogger(__name__)
        self.alert_handlers: list[Callable[[AuditEvent], None]] = []
        self.event_processors: list[Callable[[AuditEvent], AuditEvent]] = []
        self._stats: dict[str, Any] = {
            'total_events': 0,
            'events_by_type': {},
            'events_by_severity': {}
        }

    def add_alert_handler(self, handler: Callable[[AuditEvent], None]) -> None:
        self.alert_handlers.append(handler)

    def add_event_processor(
        self, processor: Callable[[AuditEvent], AuditEvent]
    ) -> None:
        self.event_processors.append(processor)

    def log_risk_detection(
        self,
        risk_id: str, risk_category: str,
        severity: str, description: str,
        affected_components: list[str],
        details: dict[str, Any],
        correlation_id: str | None = None
    ) -> None:
        event = AuditEvent(
            event_id=uuid.uuid4().hex,
            event_type=AuditEventType.RISK_DETECTED,
            severity=AuditSeverity(severity.lower()),
            timestamp=time.time(),
            source_component="risk_analyzer",
            description=f"Risk detected: {description}",
            details={**details, 'risk_id': risk_id, 'risk_category': risk_category},
            affected_entities=affected_components,
            correlation_id=correlation_id
        )
        self._log_event(event)

    def log_mitigation_action(
        self, action_id: str, status: str,
        description: str, details: dict[str, Any],
        correlation_id: str | None = None
    ) -> None:
        if status == "started":
            event_type = AuditEventType.MITIGATION_STARTED
            severity = AuditSeverity.INFO
        elif status == "completed":
            event_type = AuditEventType.MITIGATION_COMPLETED
            severity = AuditSeverity.INFO
        elif status == "failed":
            event_type = AuditEventType.MITIGATION_FAILED
            severity = AuditSeverity.ERROR
        else:
            event_type = AuditEventType.SYSTEM_EVENT
            severity = AuditSeverity.INFO

        event = AuditEvent(
            event_id=uuid.uuid4().hex,
            event_type=event_type,
            severity=severity,
            timestamp=time.time(),
            source_component="mitigation_manager",
            description=f"Mitigation {status}: {description}",
            details={**details, 'action_id': action_id, 'status': status},
            correlation_id=correlation_id
        )
        self._log_event(event)

    def log_consensus_event(
        self,
        event_type: str,
        description: str,
        details: dict[str, Any],
        severity: str = "info"
    ) -> None:
        event = AuditEvent(
            event_id=uuid.uuid4().hex,
            event_type=AuditEventType.CONSENSUS_EVENT,
            severity=AuditSeverity(severity.lower()),
            timestamp=time.time(),
            source_component="consensus",
            description=f"Consensus event: {description}",
            details={**details, 'consensus_event_type': event_type}
        )
        self._log_event(event)

    def log_security_event(
        self,
        event_type: str,
        description: str,
        details: dict[str, Any],
        user_id: str | None = None,
        ip_address: str | None = None,
        severity: str = "warning"
    ) -> None:
        event = AuditEvent(
            event_id=uuid.uuid4().hex,
            event_type=AuditEventType.SECURITY_EVENT,
            severity=AuditSeverity(severity.lower()),
            timestamp=time.time(),
            source_component="security",
            description=f"Security event: {description}",
            details={**details, 'security_event_type': event_type},
            user_id=user_id,
            ip_address=ip_address
        )
        self._log_event(event)

    def log_performance_event(
        self,
        metric_name: str,
        value: float,
        threshold: float,
        description: str,
        details: dict[str, Any],
        severity: str = "warning"
    ) -> None:
        event = AuditEvent(
            event_id=uuid.uuid4().hex,
            event_type=AuditEventType.PERFORMANCE_EVENT,
            severity=AuditSeverity(severity.lower()),
            timestamp=time.time(),
            source_component="performance_monitor",
            description=f"Performance event: {description}",
            details={
                **details,
                'metric_name': metric_name,
                'value': value,
                'threshold': threshold,
            }
        )
        self._log_event(event)

    def log_user_action(
        self,
        user_id: str,
        action: str,
        description: str,
        details: dict[str, Any],
        session_id: str | None = None,
        ip_address: str | None = None
    ) -> None:
        event = AuditEvent(
            event_id=uuid.uuid4().hex,
            event_type=AuditEventType.USER_ACTION,
            severity=AuditSeverity.INFO,
            timestamp=time.time(),
            source_component="api",
            description=f"User action: {description}",
            details={**details, 'action': action},
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address
        )
        self._log_event(event)

    def log_configuration_change(
        self,
        component: str,
        parameter: str,
        old_value: Any,
        new_value: Any,
        user_id: str | None = None,
        description: str | None = None
    ) -> None:
        desc = description or f"Configuration changed: {component}.{parameter}"
        event = AuditEvent(
            event_id=uuid.uuid4().hex,
            event_type=AuditEventType.CONFIGURATION_CHANGE,
            severity=AuditSeverity.INFO,
            timestamp=time.time(),
            source_component="configuration",
            description=desc,
            details={
                'component': component,
                'parameter': parameter,
                'old_value': old_value,
                'new_value': new_value
            },
            user_id=user_id
        )
        self._log_event(event)

    def _log_event(self, event: AuditEvent) -> None:
        try:
            processed_event = event
            for processor in self.event_processors:
                processed_event = processor(processed_event)
            digest = (
                processed_event.calculate_hash()
                if self.integrity_digest_writer is not None else None
            )
            if not self.storage.store_event(processed_event):
                raise RuntimeError(f"Failed to store audit event: {event.event_id}")
            if self.integrity_digest_writer is not None and digest is not None:
                self.integrity_digest_writer(processed_event.event_id, digest)
        except Exception as e:
            self.logger.error("Error logging audit event: %s", str(e))
            raise
        self._update_stats(processed_event)
        if self.enable_real_time_alerts:
            self._process_alerts(processed_event)

    def _update_stats(self, event: AuditEvent) -> None:
        self._stats['total_events'] += 1
        event_type = event.event_type.value
        events_by_type = cast(dict[str, int], self._stats['events_by_type'])
        events_by_type[event_type] = events_by_type.get(event_type, 0) + 1
        severity = event.severity.value
        events_by_severity = cast(dict[str, int], self._stats['events_by_severity'])
        events_by_severity[severity] = events_by_severity.get(severity, 0) + 1

    def _process_alerts(self, event: AuditEvent):
        if event.severity in [AuditSeverity.ERROR, AuditSeverity.CRITICAL]:
            for handler in self.alert_handlers:
                try:
                    handler(event)
                except Exception as e:
                    self.logger.error(f"Alert handler failed: {e!s}")

    def query_events(
        self, filter_criteria: AuditFilter, limit: int | None = None
    ) -> list[AuditEvent]:
        """Return archive events without implying trusted-manifest verification."""
        return self.storage.retrieve_events(filter_criteria, limit)

    def query_events_with_integrity(
        self, filter_criteria: AuditFilter, limit: int | None = None,
    ) -> AuditReadResult:
        """Read events and explicitly verify the complete archive when possible.

        Without a configured trusted digest reader, filtered events are returned
        with ``UNVERIFIED`` status. If a reader is configured, the complete
        archive is checked before filtered results are released. Manifest errors
        and mismatches return no events with ``FAILED`` status.
        """
        if self.integrity_digest_reader is None:
            return AuditReadResult(
                self.storage.retrieve_events(filter_criteria, limit),
                AuditIntegrityStatus.UNVERIFIED,
            )

        try:
            all_events = self.storage.retrieve_events(AuditFilter())
            expected_hashes = self.integrity_digest_reader()
            if not verify_integrity(all_events, expected_hashes):
                return AuditReadResult([], AuditIntegrityStatus.FAILED)
        except Exception:
            self.logger.exception("Could not verify audit archive against trusted manifest")
            return AuditReadResult([], AuditIntegrityStatus.FAILED)

        filtered = [event for event in all_events if filter_criteria.matches(event)]
        if limit is not None and limit > 0:
            filtered = filtered[:limit]
        return AuditReadResult(filtered, AuditIntegrityStatus.VERIFIED)

    def get_statistics(self) -> dict[str, Any]:
        return self._stats.copy()

    def generate_report(
        self,
        filter_criteria: AuditFilter,
        output_format: str = "json"
    ) -> str:
        """Serialize stored events without implying trusted-manifest verification."""
        events = self.storage.retrieve_events(filter_criteria)
        if output_format.lower() == "json":
            return dumps_json([event.to_dict() for event in events], indent=2, default=str)
        elif output_format.lower() == "csv":
            output = io.StringIO(newline="")
            writer = csv.writer(output)
            writer.writerow([
                "event_id", "event_type", "severity", "timestamp", "source_component", "description"
            ])
            for event in events:
                writer.writerow([
                    _spreadsheet_safe_cell(event.event_id), event.event_type.value,
                    event.severity.value, event.timestamp,
                    _spreadsheet_safe_cell(event.source_component),
                    _spreadsheet_safe_cell(event.description),
                ])
            return output.getvalue()
        else:
            raise ValueError(f"Unsupported output format: {output_format}")


def _spreadsheet_safe_cell(value: str) -> str:
    """Preserve CSV text while preventing spreadsheet formula evaluation."""
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value
