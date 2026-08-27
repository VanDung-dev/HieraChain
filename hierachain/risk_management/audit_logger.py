"""
Enhanced Audit Logger for HieraChain Ledger

Provides comprehensive audit logging capabilities for tracking
system activities, risk events, and mitigation actions.
"""

from __future__ import annotations

import time
import sqlite3
import orjson
import logging
import threading
import uuid
from typing import Any, Callable, cast
from pathlib import Path

from hierachain.risk_management.types import (
    AuditEvent,
    AuditEventType,
    AuditSeverity,
    AuditFilter,
)

logger = logging.getLogger(__name__)

__all__ = [
    "AuditEvent",
    "AuditEventType",
    "AuditSeverity",
    "AuditFilter",
    "AuditLogger",
    "AuditStorage",
    "FileAuditStorage",
    "RotatingAuditStorage",
    "DatabaseAuditStorage",
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
                    correlation_id TEXT
                )
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_events (timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_events (event_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_severity ON audit_events (severity)")
            conn.commit()
        finally:
            conn.close()

    def store_event(self, event: AuditEvent) -> bool:
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO audit_events 
                (event_id, event_type, severity, timestamp, source_component, description, details, user_id, session_id, ip_address, correlation_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.event_type.value,
                    event.severity.value,
                    event.timestamp,
                    event.source_component,
                    event.description,
                    orjson.dumps(event.details).decode() if event.details else None,
                    event.user_id,
                    event.session_id,
                    event.ip_address,
                    event.correlation_id,
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

    def retrieve_events(
        self, filter_criteria: AuditFilter, limit: int | None = None
    ) -> list[AuditEvent]:
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            query = "SELECT * FROM audit_events WHERE 1=1"
            params = []
            
            if filter_criteria.event_types:
                placeholders = ",".join("?" for _ in filter_criteria.event_types)
                query += f" AND event_type IN ({placeholders})"
                params.extend(t.value for t in filter_criteria.event_types)
            if filter_criteria.severity_levels:
                placeholders = ",".join("?" for _ in filter_criteria.severity_levels)
                query += f" AND severity IN ({placeholders})"
                params.extend(s.value for s in filter_criteria.severity_levels)
            if filter_criteria.time_range:
                start, end = filter_criteria.time_range
                query += " AND timestamp >= ? AND timestamp <= ?"
                params.extend([start, end])
                
            query += " ORDER BY timestamp DESC"
            if limit:
                query += " LIMIT ?"
                params.append(limit)
                
            cursor.execute(query, params)
            rows = cursor.fetchall()
            events = []
            for r in rows:
                ev_dict = dict(r)
                if ev_dict.get('details'):
                    ev_dict['details'] = orjson.loads(ev_dict['details'])
                else:
                    ev_dict['details'] = {}
                # Match enum types
                ev_dict['event_type'] = AuditEventType(ev_dict['event_type'])
                ev_dict['severity'] = AuditSeverity(ev_dict['severity'])
                events.append(AuditEvent.from_dict(ev_dict))
            return events
        except Exception as e:
            logging.error("Failed to retrieve audit events from DB: %s", str(e))
            return []
        finally:
            if conn:
                conn.close()

    def get_event_count(self, filter_criteria: AuditFilter) -> int:
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            query = "SELECT COUNT(*) FROM audit_events WHERE 1=1"
            params = []
            
            if filter_criteria.event_types:
                placeholders = ",".join("?" for _ in filter_criteria.event_types)
                query += f" AND event_type IN ({placeholders})"
                params.extend(t.value for t in filter_criteria.event_types)
            if filter_criteria.severity_levels:
                placeholders = ",".join("?" for _ in filter_criteria.severity_levels)
                query += f" AND severity IN ({placeholders})"
                params.extend(s.value for s in filter_criteria.severity_levels)
            if filter_criteria.time_range:
                start, end = filter_criteria.time_range
                query += " AND timestamp >= ? AND timestamp <= ?"
                params.extend([start, end])
                
            cursor.execute(query, params)
            count = cursor.fetchone()[0]
            return count
        except Exception as e:
            logging.error("Failed to count audit events in DB: %s", str(e))
            return 0
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



def _parse_event_line(line: str) -> AuditEvent | None:
    try:
        return AuditEvent.from_dict(orjson.loads(line.strip()))
    except (orjson.JSONDecodeError, KeyError, ValueError) as e:
        logging.warning("Failed to parse audit event: %s", str(e))
        return None


def _iter_events_from_file(log_file: Path):
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
            logging.error("Failed to retrieve audit events: %s", str(e))
            return []

    def _get_files_to_search(self, time_range: tuple | None) -> list[Path]:
        if not time_range:
            return sorted(
                list(self.audit_directory.glob("audit_*.jsonl")), reverse=True
            )
        start_time, end_time = time_range
        log_files = []
        current = start_time
        while current <= end_time:
            log_file = self._get_log_file(current)
            if log_file.exists():
                log_files.append(log_file)
            current += 86400
        return log_files

    def get_event_count(self, filter_criteria: AuditFilter) -> int:
        return len(self.retrieve_events(filter_criteria))


class RotatingAuditStorage(FileAuditStorage):
    def __init__(
        self,
        audit_directory: str = "log/risk_management/audit_logs",
        max_file_size: int = 100 * 1024 * 1024,
        retention_days: int = 90
    ):
        super().__init__(audit_directory)
        self.max_file_size = max_file_size
        self.retention_days = retention_days

    def store_event(self, event: AuditEvent) -> bool:
        result = super().store_event(event)
        if result:
            self._check_rotation(event.timestamp)
            self._cleanup_old_files()
        return result

    def _check_rotation(self, timestamp: float) -> None:
        log_file = self._get_log_file(timestamp)
        if log_file.exists() and log_file.stat().st_size > self.max_file_size:
            rotated_name = f"{log_file.stem}_{int(timestamp)}.jsonl"
            rotated_path = log_file.parent / rotated_name
            log_file.rename(rotated_path)

    def _cleanup_old_files(self) -> None:
        cutoff_time = time.time() - (self.retention_days * 86400)
        for log_file in self.audit_directory.glob("audit_*.jsonl"):
            if log_file.stat().st_mtime < cutoff_time:
                log_file.unlink()


def verify_integrity(events: list[AuditEvent]) -> bool:
    for event in events:
        expected_hash = event.calculate_hash()
        if not expected_hash:
            return False
    return True


class AuditLogger:
    def __init__(
        self,
        storage: AuditStorage | None = None,
        enable_real_time_alerts: bool = True
    ):
        self.storage = storage or FileAuditStorage("log/risk_management/audit_logs")
        self.enable_real_time_alerts = enable_real_time_alerts
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
            details={'risk_id': risk_id, 'risk_category': risk_category, **details},
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
            details={'action_id': action_id, 'status': status, **details},
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
            details={'consensus_event_type': event_type, **details}
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
            details={'security_event_type': event_type, **details},
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
                'metric_name': metric_name,
                'value': value,
                'threshold': threshold,
                **details
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
            details={'action': action, **details},
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
            success = self.storage.store_event(processed_event)
            if success:
                self._update_stats(processed_event)
                if self.enable_real_time_alerts:
                    self._process_alerts(processed_event)
            else:
                self.logger.error("Failed to store audit event: %s", event.event_id)
        except Exception as e:
            self.logger.error("Error logging audit event: %s", str(e))

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
                    self.logger.error(f"Alert handler failed: {str(e)}")

    def query_events(
        self, filter_criteria: AuditFilter, limit: int | None = None
    ) -> list[AuditEvent]:
        return self.storage.retrieve_events(filter_criteria, limit)

    def get_statistics(self) -> dict[str, Any]:
        return self._stats.copy()

    def generate_report(
        self,
        filter_criteria: AuditFilter,
        output_format: str = "json"
    ) -> str:
        events = self.storage.retrieve_events(filter_criteria)
        if output_format.lower() == "json":
            return orjson.dumps(
                [event.to_dict() for event in events],
                option=orjson.OPT_INDENT_2,
                default=str
            ).decode()
        elif output_format.lower() == "csv":
            lines = [
                "event_id,event_type,severity,timestamp,source_component,description"
            ]
            for event in events:
                lines.append(
                    f"{event.event_id},{event.event_type.value},"
                    f"{event.severity.value},{event.timestamp},"
                    f"{event.source_component},\"{event.description}\""
                )
            return "\n".join(lines)
        else:
            raise ValueError(f"Unsupported output format: {output_format}")
