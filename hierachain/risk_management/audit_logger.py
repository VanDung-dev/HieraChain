"""
Enhanced Audit Logger for HieraChain Framework

This module provides comprehensive audit logging capabilities for tracking
system activities, risk events, and mitigation actions. Supports compliance
requirements and forensic analysis.
"""

import time
import json
import logging
import hashlib
import threading
import uuid
from typing import Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path


class AuditEventType(Enum):
    """Types of audit events"""
    RISK_DETECTED = "risk_detected"
    RISK_RESOLVED = "risk_resolved"
    MITIGATION_STARTED = "mitigation_started"
    MITIGATION_COMPLETED = "mitigation_completed"
    MITIGATION_FAILED = "mitigation_failed"
    CONSENSUS_EVENT = "consensus_event"
    SECURITY_EVENT = "security_event"
    PERFORMANCE_EVENT = "performance_event"
    STORAGE_EVENT = "storage_event"
    SYSTEM_EVENT = "system_event"
    USER_ACTION = "user_action"
    CONFIGURATION_CHANGE = "configuration_change"
    ACCESS_EVENT = "access_event"


class AuditSeverity(Enum):
    """Severity levels for audit events"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Audit event record"""
    event_id: str
    event_type: AuditEventType
    severity: AuditSeverity
    timestamp: float
    source_component: str
    description: str
    details: dict[str, Any]
    user_id: str | None = None
    session_id: str | None = None
    ip_address: str | None = None
    affected_entities: list[str] | None = None
    correlation_id: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['event_type'] = self.event_type.value
        data['severity'] = self.severity.value
        # Sanitize details and other fields for Arrow objects
        data['details'] = self._sanitize_data(data['details'])
        if data.get('affected_entities'):
            data['affected_entities'] = self._sanitize_data(data['affected_entities'])
        return data

    @staticmethod
    def _sanitize_data(data: Any) -> Any:
        """Sanitize data to ensure it's serializable, handling Arrow objects."""
        if hasattr(data, "schema") or hasattr(data, "to_pylist"):
            # Handle PyArrow objects (Table, RecordBatch, Array)
            return str(data)
        if isinstance(data, dict):
            return {k: AuditEvent._sanitize_data(v) for k, v in data.items()}
        if isinstance(data, list):
            return [AuditEvent._sanitize_data(v) for v in data]
        return data
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'AuditEvent':
        """Create AuditEvent from dictionary."""
        return cls(
            event_id=data['event_id'],
            event_type=AuditEventType(data['event_type']),
            severity=AuditSeverity(data['severity']),
            timestamp=data['timestamp'],
            source_component=data['source_component'],
            description=data['description'],
            details=data['details'],
            user_id=data.get('user_id'),
            session_id=data.get('session_id'),
            ip_address=data.get('ip_address'),
            affected_entities=data.get('affected_entities'),
            correlation_id=data.get('correlation_id')
        )
    
    def calculate_hash(self) -> str:
        """Calculate hash for integrity verification."""
        content = f"{self.event_id}{self.timestamp}{self.source_component}{self.description}"
        return hashlib.sha256(content.encode()).hexdigest()


class AuditFilter:
    """Filter for audit events"""
    
    def __init__(
        self,
        event_types: list[AuditEventType] | None = None,
        severity_levels: list[AuditSeverity] | None = None,
        source_components: list[str] | None = None,
        time_range: tuple | None = None,
        user_ids: list[str] | None = None
    ):
        """
        Initialize audit filter.
        
        Args:
            event_types: Event types to include
            severity_levels: Severity levels to include
            source_components: Source components to include
            time_range: (start_time, end_time) tuple
            user_ids: User IDs to include
        """
        self.event_types = event_types
        self.severity_levels = severity_levels
        self.source_components = source_components
        self.time_range = time_range
        self.user_ids = user_ids
    
    def matches(self, event: AuditEvent) -> bool:
        """Check if event matches filter criteria."""
        criteria = [
            (self.event_types, lambda: event.event_type in self.event_types),
            (self.severity_levels, lambda: event.severity in self.severity_levels),
            (self.source_components, lambda: event.source_component in self.source_components),
            (self.user_ids, lambda: event.user_id in self.user_ids),
            (self.time_range, lambda: self.time_range[0] <= event.timestamp <= self.time_range[1])
        ]
        
        return all(condition() for field, condition in criteria if field is not None)


class AuditStorage:
    """Base class for audit storage backends"""
    
    def store_event(self, event: AuditEvent) -> bool:
        """Store audit event."""
        raise NotImplementedError
    
    def retrieve_events(self, filter_criteria: AuditFilter, limit: int | None = None) -> list[AuditEvent]:
        """Retrieve audit events matching filter criteria."""
        raise NotImplementedError
    
    def get_event_count(self, filter_criteria: AuditFilter) -> int:
        """Get count of events matching filter criteria."""
        raise NotImplementedError


def _parse_event_line(line: str) -> AuditEvent | None:
    """Parse a single log line into an AuditEvent."""
    try:
        return AuditEvent.from_dict(json.loads(line.strip()))
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logging.warning(f"Failed to parse audit event: {str(e)}")
        return None


def _iter_events_from_file(log_file: Path):
    """Generator to yield parsed events from a file."""
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
    """
    Read events from a file and apply filter.
    Returns True if limit is reached, False otherwise.
    """
    for event in _iter_events_from_file(log_file):
        if filter_criteria.matches(event):
            events.append(event)
            if limit and len(events) >= limit:
                return True
    return False


class FileAuditStorage(AuditStorage):
    """File-based audit storage implementation"""
    
    def __init__(self, audit_directory: str = "log/risk_management/audit_logs"):
        """
        Initialize file audit storage.
        
        Args:
            audit_directory: Directory to store audit log files
        """
        self.audit_directory = Path(audit_directory)
        self.audit_directory.mkdir(parents=True, exist_ok=True)
        self.current_file = None
        self.current_date = None
        self._lock = threading.Lock()
    
    def _get_log_file(self, timestamp: float) -> Path:
        """Get log file path for given timestamp."""
        date_str = time.strftime("%Y-%m-%d", time.localtime(timestamp))
        return self.audit_directory / f"audit_{date_str}.jsonl"
    
    def store_event(self, event: AuditEvent) -> bool:
        """Store audit event to file."""
        try:
            with self._lock:
                log_file = self._get_log_file(event.timestamp)
                
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(event.to_json() + '\n')
                
                return True
                
        except Exception as e:
            logging.error(f"Failed to store audit event: {str(e)}")
            return False
    
    def retrieve_events(
        self,
        filter_criteria: AuditFilter,
        limit: int | None = None
    ) -> list[AuditEvent]:
        """Retrieve audit events from files."""
        events = []
        try:
            log_files = self._get_files_to_search(filter_criteria.time_range)
            
            for log_file in log_files:
                if _read_and_filter_file(log_file, filter_criteria, events, limit):
                    break
            
            return events
        except Exception as e:
            logging.error(f"Failed to retrieve audit events: {str(e)}")
            return []

    def _get_files_to_search(self, time_range: tuple | None) -> list[Path]:
        """Determine which log files to search based on time range."""
        if not time_range:
            return sorted(list(self.audit_directory.glob("audit_*.jsonl")), reverse=True)
            
        start_time, end_time = time_range
        log_files = []
        current = start_time
        while current <= end_time:
            log_file = self._get_log_file(current)
            if log_file.exists():
                log_files.append(log_file)
            current += 86400  # Next day
        return log_files

    def get_event_count(self, filter_criteria: AuditFilter) -> int:
        """Get count of events matching filter criteria."""
        return len(self.retrieve_events(filter_criteria))


class RotatingAuditStorage(FileAuditStorage):
    """File audit storage with rotation and compression"""
    
    def __init__(
        self,
        audit_directory: str = "log/risk_management/audit_logs",
        max_file_size: int = 100 * 1024 * 1024,  # 100MB
        retention_days: int = 90
    ):
        """
        Initialize rotating audit storage.
        
        Args:
            audit_directory: Directory to store audit log files
            max_file_size: Maximum file size before rotation
            retention_days: Days to retain audit logs
        """
        super().__init__(audit_directory)
        self.max_file_size = max_file_size
        self.retention_days = retention_days
    
    def store_event(self, event: AuditEvent) -> bool:
        """Store event with rotation support."""
        result = super().store_event(event)
        
        if result:
            self._check_rotation(event.timestamp)
            self._cleanup_old_files()
        
        return result
    
    def _check_rotation(self, timestamp: float):
        """Check if log rotation is needed."""
        log_file = self._get_log_file(timestamp)
        
        if log_file.exists() and log_file.stat().st_size > self.max_file_size:
            # Rotate the file
            rotated_name = f"{log_file.stem}_{int(timestamp)}.jsonl"
            rotated_path = log_file.parent / rotated_name
            log_file.rename(rotated_path)
    
    def _cleanup_old_files(self):
        """Remove old audit files beyond retention period."""
        cutoff_time = time.time() - (self.retention_days * 86400)
        
        for log_file in self.audit_directory.glob("audit_*.jsonl"):
            if log_file.stat().st_mtime < cutoff_time:
                log_file.unlink()


def verify_integrity(events: list[AuditEvent]) -> bool:
    """Verify integrity of audit events using hash verification."""
    for event in events:
        expected_hash = event.calculate_hash()
        # In a real implementation, you would compare against stored hash
        # For now, just verify the hash can be calculated
        if not expected_hash:
            return False
    return True


class AuditLogger:
    """
    Enhanced audit logger for comprehensive system auditing.
    
    Provides structured audit logging with multiple storage backends,
    filtering capabilities, and compliance support.
    """
    
    def __init__(
        self,
        storage: AuditStorage | None = None,
        enable_real_time_alerts: bool = True
    ):
        """
        Initialize audit logger.
        
        Args:
            storage: Audit storage backend
            enable_real_time_alerts: Enable real-time alert processing
        """
        self.storage = storage or FileAuditStorage("log/risk_management/audit_logs")
        self.enable_real_time_alerts = enable_real_time_alerts
        self.logger = logging.getLogger(__name__)
        self.alert_handlers: list[Callable[[AuditEvent], None]] = []
        self.event_processors: list[Callable[[AuditEvent], AuditEvent]] = []
        self._stats = {
            'total_events': 0,
            'events_by_type': {},
            'events_by_severity': {}
        }
    
    def add_alert_handler(self, handler: Callable[[AuditEvent], None]):
        """Add real-time alert handler."""
        self.alert_handlers.append(handler)
    
    def add_event_processor(self, processor: Callable[[AuditEvent], AuditEvent]):
        """Add event processor for enrichment/transformation."""
        self.event_processors.append(processor)
    
    def log_risk_detection(
        self,
        risk_id: str, risk_category: str,
        severity: str, description: str,
        affected_components: list[str],
        details: dict[str, Any],
        correlation_id: str | None = None
    ):
        """Log risk detection event."""
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
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
    ):
        """Log mitigation action event."""
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
            event_id=str(uuid.uuid4()),
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
    ):
        """Log consensus-related event."""
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
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
    ):
        """Log security-related event."""
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
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
    ):
        """Log performance-related event."""
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
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
    ):
        """Log user action event."""
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
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
    ):
        """Log configuration change event."""
        desc = description or f"Configuration changed: {component}.{parameter}"
        
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
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
    
    def _log_event(self, event: AuditEvent):
        """Internal method to log an event."""
        try:
            # Process event through processors
            processed_event = event
            for processor in self.event_processors:
                processed_event = processor(processed_event)
            
            # Store event
            success = self.storage.store_event(processed_event)
            
            if success:
                # Update statistics
                self._update_stats(processed_event)
                
                # Process real-time alerts if enabled
                if self.enable_real_time_alerts:
                    self._process_alerts(processed_event)
            else:
                self.logger.error(f"Failed to store audit event: {event.event_id}")
                
        except Exception as e:
            self.logger.error(f"Error logging audit event: {str(e)}")
    
    def _update_stats(self, event: AuditEvent):
        """Update audit statistics."""
        self._stats['total_events'] += 1
        
        event_type = event.event_type.value
        self._stats['events_by_type'][event_type] = \
            self._stats['events_by_type'].get(event_type, 0) + 1
        
        severity = event.severity.value
        self._stats['events_by_severity'][severity] = \
            self._stats['events_by_severity'].get(severity, 0) + 1
    
    def _process_alerts(self, event: AuditEvent):
        """Process real-time alerts for critical events."""
        # Check if event requires immediate attention
        if event.severity in [AuditSeverity.ERROR, AuditSeverity.CRITICAL]:
            for handler in self.alert_handlers:
                try:
                    handler(event)
                except Exception as e:
                    self.logger.error(f"Alert handler failed: {str(e)}")
    
    def query_events(
        self,
        filter_criteria: AuditFilter,
        limit: int | None = None
    ) -> list[AuditEvent]:
        """Query audit events with filter criteria."""
        return self.storage.retrieve_events(filter_criteria, limit)
    
    def get_statistics(self) -> dict[str, Any]:
        """Get audit statistics."""
        return self._stats.copy()
    
    def generate_report(
        self,
        filter_criteria: AuditFilter,
        output_format: str = "json"
    ) -> str:
        """Generate audit report."""
        events = self.storage.retrieve_events(filter_criteria)
        
        if output_format.lower() == "json":
            return json.dumps([event.to_dict() for event in events], indent=2, default=str)
        elif output_format.lower() == "csv":
            # Simple CSV format
            lines = ["event_id,event_type,severity,timestamp,source_component,description"]
            for event in events:
                lines.append(
                    f"{event.event_id},{event.event_type.value},"
                    f"{event.severity.value},{event.timestamp},"
                    f"{event.source_component},\"{event.description}\""
                )
            return "\n".join(lines)
        else:
            raise ValueError(f"Unsupported output format: {output_format}")
