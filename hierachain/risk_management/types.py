"""
Risk Management — Shared types, enums, and value objects.

Enums and dataclasses used across the risk analysis, mitigation,
and audit logging subsystems.
"""

from __future__ import annotations

import orjson
import hashlib
from typing import Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum


# --- Risk Analyzer Types ---

class RiskSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskCategory(Enum):
    CONSENSUS = "consensus"
    SECURITY = "security"
    PERFORMANCE = "performance"
    STORAGE = "storage"
    OPERATIONAL = "operational"


@dataclass
class RiskAssessment:
    risk_id: str
    category: RiskCategory
    severity: RiskSeverity
    description: str
    impact: str
    likelihood: float
    mitigation_recommendations: list[str]
    detected_at: float
    affected_components: list[str]


# --- Mitigation Strategy Types ---

class MitigationStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class MitigationAction:
    action_id: str
    description: str
    execution_function: Callable[[dict[str, Any]], bool]
    priority: int
    estimated_duration: int
    requires_downtime: bool = False
    dependencies: list[str] | None = None


@dataclass
class MitigationResult:
    action_id: str
    status: MitigationStatus
    start_time: float
    end_time: float | None
    error_message: str | None
    output: dict[str, Any]


# --- Audit Logger Types ---

class AuditEventType(Enum):
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
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
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
        data = asdict(self)
        data['event_type'] = self.event_type.value
        data['severity'] = self.severity.value
        data['details'] = self._sanitize_data(data['details'])
        if data.get('affected_entities'):
            data['affected_entities'] = self._sanitize_data(data['affected_entities'])
        return data

    @staticmethod
    def _sanitize_data(data: Any) -> Any:
        if hasattr(data, "schema") or hasattr(data, "to_pylist"):
            return str(data)
        if isinstance(data, dict):
            return {k: AuditEvent._sanitize_data(v) for k, v in data.items()}
        if isinstance(data, list):
            return [AuditEvent._sanitize_data(v) for v in data]
        return data

    def to_json(self) -> str:
        return orjson.dumps(self.to_dict(), default=str).decode()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'AuditEvent':
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
        content = (
            f"{self.event_id}{self.timestamp}{self.source_component}{self.description}"
        )
        return hashlib.sha256(content.encode()).hexdigest()


class AuditFilter:
    def __init__(
        self,
        event_types: list[AuditEventType] | None = None,
        severity_levels: list[AuditSeverity] | None = None,
        source_components: list[str] | None = None,
        time_range: tuple | None = None,
        user_ids: list[str] | None = None
    ):
        self.event_types = event_types
        self.severity_levels = severity_levels
        self.source_components = source_components
        self.time_range = time_range
        self.user_ids = user_ids

    def matches(self, event: AuditEvent) -> bool:
        return (
            (self.event_types is None or event.event_type in self.event_types)
            and (self.severity_levels is None or event.severity in self.severity_levels)
            and (self.source_components is None or event.source_component in self.source_components)
            and (self.user_ids is None or event.user_id in self.user_ids)
            and (self.time_range is None or (self.time_range[0] <= event.timestamp <= self.time_range[1]))
        )
