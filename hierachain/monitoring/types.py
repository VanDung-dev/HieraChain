"""
Monitoring — Shared types, enums, and value objects.

Enums and dataclasses used across alert and performance monitoring subsystems.
"""

from __future__ import annotations

import time
import json
import statistics
from typing import Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import deque


# ── Alert System Types ───────────────────────────────────────────

class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertStatus(Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class AlertCategory(Enum):
    RISK_MANAGEMENT = "risk_management"
    PERFORMANCE = "performance"
    SECURITY = "security"
    CONSENSUS = "consensus"
    STORAGE = "storage"
    SYSTEM = "system"
    CUSTOM = "custom"


@dataclass
class Alert:
    alert_id: str
    timestamp: float
    severity: AlertSeverity
    category: AlertCategory
    title: str
    description: str
    source_component: str
    metric_name: str | None = None
    current_value: float | None = None
    threshold_value: float | None = None
    status: AlertStatus = AlertStatus.ACTIVE
    acknowledgment_time: float | None = None
    resolved_time: float | None = None
    escalation_level: int = 0
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data['severity'] = self.severity.value
        data['category'] = self.category.value
        data['status'] = self.status.value
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


@dataclass
class AlertRule:
    rule_id: str
    name: str
    description: str
    category: AlertCategory
    metric_name: str
    condition: str
    threshold: float | None
    severity: AlertSeverity
    enabled: bool = True
    cooldown_period: int = 300
    escalation_time: int = 1800
    auto_resolve: bool = False
    suppress_duplicates: bool = True


# ── Performance Monitor Types ────────────────────────────────────

class MetricType(Enum):
    SYSTEM = "system"
    BLOCKCHAIN = "blockchain"
    CONSENSUS = "consensus"
    SECURITY = "security"
    STORAGE = "storage"
    NETWORK = "network"
    CUSTOM = "custom"


class MetricUnit(Enum):
    PERCENTAGE = "percentage"
    BYTES = "bytes"
    SECONDS = "seconds"
    COUNT = "count"
    RATE = "rate"
    THROUGHPUT = "throughput"


@dataclass
class MetricValue:
    timestamp: float
    value: float
    unit: MetricUnit
    metadata: dict[str, Any] | None = None


@dataclass
class PerformanceMetric:
    name: str
    metric_type: MetricType
    unit: MetricUnit
    description: str
    threshold_warning: float | None = None
    threshold_critical: float | None = None
    history_size: int = 1000
    values: deque[MetricValue] = field(default_factory=deque)

    def __post_init__(self):
        self.values = deque(self.values, maxlen=self.history_size)

    def add_value(self, value: float, metadata: dict[str, Any] | None = None):
        metric_value = MetricValue(
            timestamp=time.time(),
            value=value,
            unit=self.unit,
            metadata=metadata
        )
        self.values.append(metric_value)

    def get_current_value(self) -> float | None:
        return self.values[-1].value if self.values else None

    def get_average(self, duration_seconds: int | None = None) -> float | None:
        if not self.values:
            return None
        if duration_seconds is None:
            values = [v.value for v in self.values]
        else:
            cutoff_time = time.time() - duration_seconds
            values = [v.value for v in self.values if v.timestamp >= cutoff_time]
        return statistics.mean(values) if values else None

    def get_max(self, duration_seconds: int | None = None) -> float | None:
        if not self.values:
            return None
        if duration_seconds is None:
            values = [v.value for v in self.values]
        else:
            cutoff_time = time.time() - duration_seconds
            values = [v.value for v in self.values if v.timestamp >= cutoff_time]
        return max(values) if values else None

    def is_threshold_exceeded(self) -> tuple[bool, str]:
        current_value = self.get_current_value()
        if current_value is None:
            return False, "no_data"
        if self.threshold_critical and current_value >= self.threshold_critical:
            return True, "critical"
        elif self.threshold_warning and current_value >= self.threshold_warning:
            return True, "warning"
        return False, "normal"


# ── Performance Metrics Types ────────────────────────────────────

@dataclass
class MetricSample:
    timestamp: float
    duration_ms: float
    data_size_bytes: int = 0
    row_count: int = 0
    operation: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricAggregation:
    count: int = 0
    total_duration_ms: float = 0.0
    min_duration_ms: float = float('inf')
    max_duration_ms: float = 0.0
    total_bytes: int = 0
    total_rows: int = 0

    @property
    def avg_duration_ms(self) -> float:
        return self.total_duration_ms / self.count if self.count > 0 else 0.0

    @property
    def throughput_rows_per_sec(self) -> float:
        total_seconds = self.total_duration_ms / 1000
        return self.total_rows / total_seconds if total_seconds > 0 else 0.0

    @property
    def throughput_bytes_per_sec(self) -> float:
        total_seconds = self.total_duration_ms / 1000
        return self.total_bytes / total_seconds if total_seconds > 0 else 0.0

    def add_sample(self, sample: MetricSample) -> None:
        self.count += 1
        self.total_duration_ms += sample.duration_ms
        self.min_duration_ms = min(self.min_duration_ms, sample.duration_ms)
        self.max_duration_ms = max(self.max_duration_ms, sample.duration_ms)
        self.total_bytes += sample.data_size_bytes
        self.total_rows += sample.row_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "total_duration_ms": round(self.total_duration_ms, 2),
            "avg_duration_ms": round(self.avg_duration_ms, 2),
            "min_duration_ms": round(self.min_duration_ms, 2) if self.count > 0 else 0,
            "max_duration_ms": round(self.max_duration_ms, 2),
            "total_bytes": self.total_bytes,
            "total_rows": self.total_rows,
            "throughput_rows_per_sec": round(self.throughput_rows_per_sec, 2),
            "throughput_bytes_per_sec": round(self.throughput_bytes_per_sec, 2)
        }
