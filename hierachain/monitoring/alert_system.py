"""
Alert System for HieraChain Ledger

This module provides comprehensive alerting and anomaly detection capabilities
for the risk management and performance monitoring systems. Supports real-time
alerts, anomaly detection, and integration with external notification systems.
"""

import time
import logging
import threading
import smtplib
import json
import statistics
from typing import Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from collections import deque, defaultdict
from datetime import datetime


class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertStatus(Enum):
    """Alert status states"""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class AlertCategory(Enum):
    """Alert categories"""
    RISK_MANAGEMENT = "risk_management"
    PERFORMANCE = "performance"
    SECURITY = "security"
    CONSENSUS = "consensus"
    STORAGE = "storage"
    SYSTEM = "system"
    CUSTOM = "custom"


@dataclass
class Alert:
    """Alert message structure"""
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
        """Convert alert to dictionary"""
        data = asdict(self)
        data['severity'] = self.severity.value
        data['category'] = self.category.value
        data['status'] = self.status.value
        return data
    
    def to_json(self) -> str:
        """Convert alert to JSON string"""
        return json.dumps(self.to_dict(), default=str)


@dataclass
class AlertRule:
    """Alert rule configuration"""
    rule_id: str
    name: str
    description: str
    category: AlertCategory
    metric_name: str
    condition: str  # "greater_than", "less_than", "equals", "anomaly"
    threshold: float | None
    severity: AlertSeverity
    enabled: bool = True
    cooldown_period: int = 300  # seconds
    escalation_time: int = 1800  # 30 minutes
    auto_resolve: bool = False
    suppress_duplicates: bool = True


class AnomalyDetector:
    """Anomaly detection for metric values"""
    
    def __init__(self, window_size: int = 100, sensitivity: float = 2.0) -> None:
        """
        Initialize anomaly detector.
        
        Args:
            window_size: Number of data points to keep for analysis
            sensitivity: Z-score threshold for anomaly detection
        """
        self.window_size = window_size
        self.sensitivity = sensitivity
        self.metric_histories: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=window_size)
        )
        
    def add_data_point(self, metric_name: str, value: float) -> None:
        """Add new data point for metric"""
        self.metric_histories[metric_name].append(
            {'timestamp': time.time(), 'value': value}
        )
    
    def is_anomaly(self, metric_name: str, value: float) -> Tuple[bool, float]:
        """
        Check if value is anomalous for given metric.
        
        Returns:
            Tuple of (is_anomaly, z_score)
        """
        history = self.metric_histories[metric_name]
        
        if len(history) < 10:  # Need minimum data points
            return False, 0.0
        
        values = [point['value'] for point in history]
        
        try:
            mean = statistics.mean(values)
            stdev = statistics.stdev(values)
            
            if stdev == 0:
                return False, 0.0
            
            z_score = abs((value - mean) / stdev)
            is_anomaly = z_score > self.sensitivity
            
            return is_anomaly, z_score
            
        except statistics.StatisticsError:
            return False, 0.0


class EmailNotifier:
    """Email notification handler"""
    
    def __init__(self, smtp_config: dict[str, Any]) -> None:
        """
        Initialize email notifier.
        
        Args:
            smtp_config: SMTP configuration dictionary
        """
        import os
        self.smtp_server = smtp_config.get('server', 'localhost')
        self.smtp_port = smtp_config.get('port', 587)
        self.username = os.environ.get('HRC_SMTP_USERNAME', smtp_config.get('username'))
        self.password = os.environ.get('HRC_SMTP_PASSWORD', smtp_config.get('password'))
        
        if self.password in ("default_password", "password", "admin"):
            logging.warning(
                "SMTP Password is set to a weak default value. "
                "Please change it via HRC_SMTP_PASSWORD."
            )
            
        self.from_email = smtp_config.get('from_email', 'alerts@blockchain.local')
        self.use_tls = smtp_config.get('use_tls', True)
        self.enabled = smtp_config.get('enabled', False)
        
    def send_alert(self, alert: Alert, recipients: list[str]) -> bool:
        """Send alert via email"""
        if not self.enabled or not recipients:
            return False
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = f"[{alert.severity.value.upper()}] {alert.title}"
            
            # Create email body
            body = self._format_alert_email(alert)
            msg.attach(MIMEText(body, 'html'))
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                
                if self.username and self.password:
                    server.login(self.username, self.password)
                
                server.send_message(msg)
            
            return True
            
        except Exception as email_ex:
            logging.error("Failed to send email alert: %s", str(email_ex))
            return False
    
    @staticmethod
    def _format_alert_email(alert: Alert) -> str:
        """Format alert as HTML email"""
        severity_colors = {
            AlertSeverity.INFO: '#17a2b8',
            AlertSeverity.WARNING: '#ffc107',
            AlertSeverity.CRITICAL: '#dc3545',
            AlertSeverity.EMERGENCY: '#6f42c1'
        }
        
        color = severity_colors.get(alert.severity, '#6c757d')
        
        html = f"""
        <html>
        <body>
            <div style="font-family: Arial, sans-serif; max-width: 600px;">
                <div style="background-color: {
                    color
                }; color: white; padding: 15px; border-radius: 5px;">
                    <h2 style="margin: 0;">{alert.title}</h2>
                    <p style="margin: 5px 0 0 0;">Severity: {
                        alert.severity.value.upper()
                    }</p>
                </div>
                
                <div style="padding: 20px; border: 1px solid #ddd; border-top: none;">
                    <p><strong>Description:</strong> {alert.description}</p>
                    <p><strong>Source:</strong> {alert.source_component}</p>
                    <p><strong>Category:</strong> {alert.category.value}</p>
                    <p><strong>Timestamp:</strong> {
                        datetime.fromtimestamp(alert.timestamp).strftime(
                            '%Y-%m-%d %H:%M:%S'
                        )
                    }</p>
        """
        
        if alert.metric_name:
            html += f"<p><strong>Metric:</strong> {alert.metric_name}</p>"
        
        if alert.current_value is not None:
            html += f"<p><strong>Current Value:</strong> {alert.current_value}</p>"
        
        if alert.threshold_value is not None:
            html += f"<p><strong>Threshold:</strong> {alert.threshold_value}</p>"
        
        html += """
                </div>
                
                <div style="padding: 10px; background-color: #f8f9fa;
                border: 1px solid #ddd;border-top: none; border-radius: 0 0 5px 5px;">
                    <small>
                    This is an automated alert from the HieraChain monitoring system.
                    </small>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html


class WebhookNotifier:
    """Webhook notification handler"""
    
    def __init__(self, webhook_config: dict[str, Any]) -> None:
        """Initialize webhook notifier"""
        self.webhook_url = webhook_config.get('url')
        self.headers = webhook_config.get(
            'headers', {'Content-Type': 'application/json'}
        )
        self.enabled = webhook_config.get('enabled', False)
        
    def send_alert(self, alert: Alert) -> bool:
        """Send alert via webhook"""
        if not self.enabled or not self.webhook_url:
            return False
        
        try:
            import requests
            
            payload = alert.to_dict()
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers=self.headers,
                timeout=10
            )
            
            return response.status_code < 400
            
        except Exception as webhook_ex:
            logging.error("Failed to send webhook alert: %s", str(webhook_ex))
            return False


def _get_severity_symbol(severity: AlertSeverity) -> str:
    """Get emoji symbol for alert severity"""
    return {
        AlertSeverity.INFO: 'ℹ',
        AlertSeverity.WARNING: '⚠',
        AlertSeverity.CRITICAL: '✗',
        AlertSeverity.EMERGENCY: '🚨'
    }.get(severity, '?')


class AlertManager:
    """
    Central alert management system for HieraChain Ledger.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        self.active_alerts: dict[str, Alert] = {}
        self.alert_history: list[Alert] = []
        self.max_history_size = self.config.get('max_history_size', 10000)
        self.alert_rules: dict[str, AlertRule] = {}
        _initialize_default_rules(self)
        self.anomaly_detector = AnomalyDetector(
            window_size=self.config.get('anomaly_window_size', 100),
            sensitivity=self.config.get('anomaly_sensitivity', 2.0)
        )
        self.notifiers: list[Any] = []
        _initialize_notifiers(self)
        self.last_alert_times: dict[str, float] = {}
        self.escalation_timers: dict[str, threading.Timer] = {}
        self.stats = {
            'total_alerts': 0,
            'alerts_by_severity': defaultdict(int),
            'alerts_by_category': defaultdict(int),
            'notifications_sent': 0,
            'notifications_failed': 0
        }

    def add_alert_rule(self, rule: AlertRule) -> None:
        """Add new alert rule"""
        self.alert_rules[rule.rule_id] = rule
        self.logger.info(f"Added alert rule: {rule.name}")

    def check_metric(
        self, metric_name: str, value: float, source_component: str = "unknown"
    ) -> None:
        """Check metric for anomaly"""
        self.anomaly_detector.add_data_point(metric_name, value)
        for rule in self.alert_rules.values():
            _process_rule_for_metric(self, rule, metric_name, value, source_component)

    def create_alert(
        self,
        rule: AlertRule,
        current_value: float | None = None,
        source_component: str = "unknown",
        custom_description: str | None = None
    ) -> None:
        """Create new alert"""
        _create_alert(self, rule, current_value, source_component, custom_description)

    def acknowledge_alert(self, alert_id: str, user: str | None = None) -> bool:
        """Acknowledge alert"""
        return _acknowledge_alert(self, alert_id, user)

    def resolve_alert(self, alert_id: str, user: str | None = None) -> bool:
        """Resolve alert"""
        return _resolve_alert(self, alert_id, user)

    def get_active_alerts(
        self,
        category: AlertCategory | None = None,
        severity: AlertSeverity | None = None
    ) -> list[Alert]:
        """Get active alerts"""
        return _get_active_alerts(self, category, severity)

    def get_alert_statistics(self) -> dict[str, Any]:
        """Get alert statistics"""
        return _get_alert_statistics(self)

    def generate_report(
        self, format_type: str = "json", include_history: bool = False
    ) -> str:
        """Generate alert report"""
        format_type = format_type.lower()
        active_alerts = list(self.active_alerts.values())
        if format_type == "json":
            return _generate_json_report(self, active_alerts, include_history)
        if format_type == "text":
            return _generate_text_report(self, active_alerts)
        raise ValueError(f"Unsupported report format: {format_type}")


def _initialize_default_rules(manager: AlertManager) -> None:
    """Initialize default alert rules"""
    default_rules = [
        AlertRule(
            rule_id="CPU_HIGH",
            name="High CPU Usage",
            description="CPU usage exceeds threshold",
            category=AlertCategory.PERFORMANCE,
            metric_name="cpu_usage",
            condition="greater_than",
            threshold=85.0,
            severity=AlertSeverity.WARNING
        ),
        AlertRule(
            rule_id="CPU_CRITICAL",
            name="Critical CPU Usage",
            description="CPU usage critically high",
            category=AlertCategory.PERFORMANCE,
            metric_name="cpu_usage",
            condition="greater_than",
            threshold=95.0,
            severity=AlertSeverity.CRITICAL
        ),
        AlertRule(
            rule_id="MEMORY_HIGH",
            name="High Memory Usage",
            description="Memory usage exceeds threshold",
            category=AlertCategory.PERFORMANCE,
            metric_name="memory_usage",
            condition="greater_than",
            threshold=85.0,
            severity=AlertSeverity.WARNING
        ),
        AlertRule(
            rule_id="CONSENSUS_FAILURE",
            name="Consensus Failure",
            description="Consensus success rate below threshold",
            category=AlertCategory.CONSENSUS,
            metric_name="consensus_success_rate",
            condition="less_than",
            threshold=95.0,
            severity=AlertSeverity.CRITICAL
        ),
        AlertRule(
            rule_id="RISK_DETECTED",
            name="Security Risk Detected",
            description="Security risk detected by risk analyzer",
            category=AlertCategory.SECURITY,
            metric_name="risk_count",
            condition="greater_than",
            threshold=0,
            severity=AlertSeverity.WARNING
        )
    ]
    for rule in default_rules:
        manager.alert_rules[rule.rule_id] = rule


def _initialize_notifiers(manager: AlertManager) -> None:
    """Initialize notifiers"""
    if 'email' in manager.config:
        manager.notifiers.append(EmailNotifier(manager.config['email']))
    if 'webhook' in manager.config:
        manager.notifiers.append(WebhookNotifier(manager.config['webhook']))


def _process_rule_for_metric(
    manager: AlertManager,
    rule: AlertRule,
    metric_name: str,
    value: float,
    source_component: str
) -> None:
    """Process rule for metric"""
    if not rule.enabled or rule.metric_name != metric_name:
        return
    if (
        _evaluate_rule_condition(manager, rule, value) and
        not _is_in_cooldown(manager, rule)
    ):
        _create_alert(
            manager=manager,
            rule=rule,
            current_value=value,
            source_component=source_component,
            custom_description=None
        )


def _evaluate_rule_condition(
    manager: AlertManager, rule: AlertRule, value: float
) -> bool:
    """Evaluate rule condition"""
    if rule.condition == "greater_than" and rule.threshold is not None:
        return value > rule.threshold
    if rule.condition == "less_than" and rule.threshold is not None:
        return value < rule.threshold
    if rule.condition == "equals" and rule.threshold is not None:
        return abs(value - rule.threshold) < 0.001
    if rule.condition == "anomaly":
        is_anomaly, _ = manager.anomaly_detector.is_anomaly(rule.metric_name, value)
        return is_anomaly
    return False


def _is_in_cooldown(manager: AlertManager, rule: AlertRule) -> bool:
    """Check if rule is in cooldown"""
    last_alert_time = manager.last_alert_times.get(rule.rule_id, 0)
    return time.time() - last_alert_time < rule.cooldown_period


def _create_alert(
    manager: AlertManager,
    rule: AlertRule,
    current_value: float | None,
    source_component: str,
    custom_description: str | None
) -> None:
    """Create new alert"""
    alert_id = f"{rule.rule_id}_{int(time.time())}"
    alert = Alert(
        alert_id=alert_id,
        timestamp=time.time(),
        severity=rule.severity,
        category=rule.category,
        title=rule.name,
        description=custom_description or rule.description,
        source_component=source_component,
        metric_name=rule.metric_name,
        current_value=current_value,
        threshold_value=rule.threshold
    )
    if rule.suppress_duplicates and _is_duplicate_alert(manager, alert):
        manager.logger.debug(f"Suppressing duplicate alert: {alert.title}")
        return
    manager.active_alerts[alert_id] = alert
    manager.alert_history.append(alert)
    _trim_alert_history(manager)
    _update_alert_stats(manager, alert)
    manager.last_alert_times[rule.rule_id] = time.time()
    _send_notifications(manager, alert)
    if rule.escalation_time > 0:
        _schedule_alert_escalation(manager, alert_id, rule.escalation_time)
    manager.logger.warning(f"Alert created: {alert.title} (ID: {alert_id})")


def _is_duplicate_alert(manager: AlertManager, alert: Alert) -> bool:
    """Check if alert is a duplicate"""
    for existing_alert in manager.active_alerts.values():
        if (
            existing_alert.category == alert.category
            and existing_alert.metric_name == alert.metric_name
            and existing_alert.status == AlertStatus.ACTIVE
        ):
            return True
    return False


def _trim_alert_history(manager: AlertManager) -> None:
    """Trim alert history if necessary"""
    if len(manager.alert_history) > manager.max_history_size:
        manager.alert_history = manager.alert_history[-manager.max_history_size:]


def _update_alert_stats(manager: AlertManager, alert: Alert) -> None:
    """Update alert statistics"""
    manager.stats['total_alerts'] += 1
    manager.stats['alerts_by_severity'][alert.severity.value] += 1
    manager.stats['alerts_by_category'][alert.category.value] += 1


def _schedule_alert_escalation(
    manager: AlertManager, alert_id: str, escalation_time: int
) -> None:
    """Schedule alert escalation"""
    timer = threading.Timer(
        escalation_time, _escalate_alert, args=(manager, alert_id)
    )
    timer.start()
    manager.escalation_timers[alert_id] = timer


def _send_notifications(manager: AlertManager, alert: Alert) -> None:
    """Send notifications to notifiers"""
    recipients = manager.config.get('email_recipients', [])
    for notifier in manager.notifiers:
        success = _send_to_notifier(manager, notifier, alert, recipients)
        if success:
            manager.stats['notifications_sent'] += 1
        else:
            manager.stats['notifications_failed'] += 1


def _send_to_notifier(
    manager: AlertManager, notifier: Any, alert: Alert, recipients: list[str]
) -> bool:
    """Send alert to notifier"""
    try:
        if isinstance(notifier, EmailNotifier):
            return notifier.send_alert(alert, recipients)
        return notifier.send_alert(alert)
    except Exception as notify_ex:
        manager.logger.error(
            f"Notification failed for {type(notifier).__name__}: {str(notify_ex)}"
        )
        return False


def _acknowledge_alert(manager: AlertManager, alert_id: str, user: str | None) -> bool:
    """Acknowledge alert"""
    if alert_id not in manager.active_alerts:
        return False
    alert = manager.active_alerts[alert_id]
    alert.status = AlertStatus.ACKNOWLEDGED
    alert.acknowledgment_time = time.time()
    if alert_id in manager.escalation_timers:
        manager.escalation_timers[alert_id].cancel()
        del manager.escalation_timers[alert_id]
    manager.logger.info(f"Alert acknowledged: {alert_id} by {user or 'unknown'}")
    return True


def _resolve_alert(manager: AlertManager, alert_id: str, user: str | None) -> bool:
    """Resolve alert"""
    if alert_id not in manager.active_alerts:
        return False
    alert = manager.active_alerts[alert_id]
    alert.status = AlertStatus.RESOLVED
    alert.resolved_time = time.time()
    del manager.active_alerts[alert_id]
    if alert_id in manager.escalation_timers:
        manager.escalation_timers[alert_id].cancel()
        del manager.escalation_timers[alert_id]
    manager.logger.info(f"Alert resolved: {alert_id} by {user or 'system'}")
    return True


def _escalate_alert(manager: AlertManager, alert_id: str) -> None:
    """Escalate alert to next level"""
    if alert_id not in manager.active_alerts:
        return
    alert = manager.active_alerts[alert_id]
    if alert.status == AlertStatus.ACTIVE:
        alert.escalation_level += 1
        escalation_alert = Alert(
            alert_id=f"{alert_id}_ESC_{alert.escalation_level}",
            timestamp=time.time(),
            severity=AlertSeverity.CRITICAL,
            category=alert.category,
            title=f"ESCALATED: {alert.title}",
            description=(
                "Alert has been escalated due to no acknowledgment. "
                f"Original: {alert.description}"
            ),
            source_component=alert.source_component,
            escalation_level=alert.escalation_level
        )
        _send_notifications(manager, escalation_alert)
        manager.logger.critical(
            f"Alert escalated: {alert_id} (level {alert.escalation_level})"
        )


def _get_active_alerts(
    manager: AlertManager,
    category: AlertCategory | None,
    severity: AlertSeverity | None
) -> list[Alert]:
    """Get active alerts"""
    alerts = list(manager.active_alerts.values())
    if category:
        alerts = [a for a in alerts if a.category == category]
    if severity:
        alerts = [a for a in alerts if a.severity == severity]
    return alerts


def _get_alert_statistics(manager: AlertManager) -> dict[str, Any]:
    """Get alert statistics"""
    return {
        **manager.stats,
        'active_alerts': len(manager.active_alerts),
        'alert_rules': len(manager.alert_rules),
        'enabled_rules': len([r for r in manager.alert_rules.values() if r.enabled])
    }


def _generate_json_report(
    manager: AlertManager,
    active_alerts: list[Alert],
    include_history: bool
) -> str:
    """Generate JSON-based alert report"""
    report_data = {
        'timestamp': time.time(),
        'statistics': _get_alert_statistics(manager),
        'active_alerts': [alert.to_dict() for alert in active_alerts]
    }
    if include_history:
        report_data['alert_history'] = [
            alert.to_dict() for alert in manager.alert_history[-100:]
        ]
    return json.dumps(report_data, indent=2, default=str)


def _generate_text_report(manager: AlertManager, active_alerts: list[Alert]) -> str:
    """Generate text-based alert report"""
    lines = [
        "Alert System Report",
        "=" * 40,
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Active Alerts: {len(active_alerts)}",
        f"Total Alerts Generated: {manager.stats['total_alerts']}",
        ""
    ]
    if active_alerts:
        lines.append("ACTIVE ALERTS:")
        lines.append("-" * 20)
        for alert in sorted(active_alerts, key=lambda x: x.timestamp, reverse=True):
            severity_symbol = _get_severity_symbol(alert.severity)
            lines.append(f"  {severity_symbol} {alert.title}")
            lines.append(f"    Created: {datetime.fromtimestamp(alert.timestamp)}")
            lines.append(f"    Source: {alert.source_component}")
            lines.append(f"    Status: {alert.status.value}")
            lines.append("")
    else:
        lines.append("No active alerts.")
    return "\n".join(lines)
