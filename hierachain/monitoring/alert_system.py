"""
Alert System for HieraChain Ledger.

"""

from __future__ import annotations

import time
import os
import smtplib
import logging
import threading
import json
import statistics
from collections import deque, defaultdict
from datetime import datetime
from typing import Any, cast
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from hierachain.monitoring.types import (
    AlertSeverity,
    AlertStatus,
    AlertCategory,
    Alert,
    AlertRule,
)

logger = logging.getLogger(__name__)


# =====================================================================
# Anomaly Detection Component
# =====================================================================

class AnomalyDetector:
    def __init__(self, window_size: int = 100, sensitivity: float = 2.0) -> None:
        self.window_size = window_size
        self.sensitivity = sensitivity
        self.metric_histories: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=window_size)
        )

    def add_data_point(self, metric_name: str, value: float) -> None:
        self.metric_histories[metric_name].append(
            {'timestamp': time.time(), 'value': value}
        )

    def is_anomaly(self, metric_name: str, value: float) -> tuple[bool, float]:
        history = self.metric_histories[metric_name]
        if len(history) < 10:
            return False, 0.0
        values = [point['value'] for point in history]
        try:
            mean = statistics.mean(values)
            stdev = statistics.stdev(values)
            if stdev == 0:
                return False, 0.0
            z_score = abs((value - mean) / stdev)
            return z_score > self.sensitivity, z_score
        except statistics.StatisticsError:
            return False, 0.0


# =====================================================================
# Notification Adapters Component
# =====================================================================

class EmailNotifier:
    smtp_server: str
    smtp_port: int
    username: str | None
    password: str | None

    def __init__(self, smtp_config: dict[str, Any]) -> None:
        _set_smtp_from_env(self, smtp_config)
        self.from_email = smtp_config.get('from_email', 'alerts@blockchain.local')
        self.use_tls = smtp_config.get('use_tls', True)
        self.enabled = smtp_config.get('enabled', False)

    def send_alert(self, alert: Alert, recipients: list[str]) -> bool:
        if not self.enabled or not recipients:
            return False
        try:
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = f"[{alert.severity.value.upper()}] {alert.title}"
            body = _format_alert_email(alert)
            msg.attach(MIMEText(body, 'html'))
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


class WebhookNotifier:
    def __init__(self, webhook_config: dict[str, Any]) -> None:
        self.webhook_url = webhook_config.get('url')
        self.headers = webhook_config.get(
            'headers', {'Content-Type': 'application/json'}
        )
        self.enabled = webhook_config.get('enabled', False)

    def send_alert(self, alert: Alert) -> bool:
        webhook_url = self.webhook_url
        if not self.enabled or not webhook_url:
            return False
        try:
            import httpx
            payload = alert.to_dict()
            response = httpx.post(
                cast(str, webhook_url),
                json=payload,
                headers=self.headers,
                timeout=10
            )
            return response.status_code < 400
        except Exception as webhook_ex:
            logging.error("Failed to send webhook alert: %s", str(webhook_ex))
            return False


def _set_smtp_from_env(notifier_instance: EmailNotifier, smtp_config: dict[str, Any]) -> None:
    notifier_instance.smtp_server = smtp_config.get('server', 'localhost')
    notifier_instance.smtp_port = smtp_config.get('port', 587)
    notifier_instance.username = os.environ.get('HRC_SMTP_USERNAME', smtp_config.get('username'))
    notifier_instance.password = os.environ.get('HRC_SMTP_PASSWORD', smtp_config.get('password'))
    if notifier_instance.password in ("default_password", "password", "admin"):
        logging.warning(
            "SMTP Password is set to a weak default value. "
            "Please change it via HRC_SMTP_PASSWORD."
        )


def _format_alert_email(alert: Alert) -> str:
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
            <div style="background-color: {color}; color: white; padding: 15px; border-radius: 5px;">
                <h2 style="margin: 0;">{alert.title}</h2>
                <p style="margin: 5px 0 0 0;">Severity: {alert.severity.value.upper()}</p>
            </div>
            <div style="padding: 20px; border: 1px solid #ddd; border-top: none;">
                <p><strong>Description:</strong> {alert.description}</p>
                <p><strong>Source:</strong> {alert.source_component}</p>
                <p><strong>Category:</strong> {alert.category.value}</p>
                <p><strong>Timestamp:</strong> {datetime.fromtimestamp(alert.timestamp).strftime('%Y-%m-%d %H:%M:%S')}</p>
    """
    if alert.metric_name:
        html += f"<p><strong>Metric:</strong> {alert.metric_name}</p>"
    if alert.current_value is not None:
        html += f"<p><strong>Current Value:</strong> {alert.current_value}</p>"
    if alert.threshold_value is not None:
        html += f"<p><strong>Threshold:</strong> {alert.threshold_value}</p>"
    html += """
            </div>
            <div style="padding: 10px; background-color: #f8f9fa; border: 1px solid #ddd; border-top: none; border-radius: 0 0 5px 5px;">
                <small>This is an automated alert from the HieraChain monitoring system.</small>
            </div>
        </div>
    </body>
    </html>
    """
    return html


def _get_severity_symbol(severity: AlertSeverity) -> str:
    return {
        AlertSeverity.INFO: 'ℹ',
        AlertSeverity.WARNING: '⚠',
        AlertSeverity.CRITICAL: '✗',
        AlertSeverity.EMERGENCY: '🚨'
    }.get(severity, '?')


# =====================================================================
# AlertManager Component
# =====================================================================

class AlertManager:
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
        self.alert_rules[rule.rule_id] = rule
        self.logger.info(f"Added alert rule: {rule.name}")

    def check_metric(
        self, metric_name: str, value: float, source_component: str = "unknown"
    ) -> None:
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
        _create_alert(self, rule, current_value, source_component, custom_description)

    def send_alert(
        self,
        level: str,
        title: str,
        message: str,
        source: str,
        details: dict[str, Any] | None = None
    ) -> None:
        severity_map = {
            "info": AlertSeverity.INFO,
            "warning": AlertSeverity.WARNING,
            "critical": AlertSeverity.CRITICAL,
            "emergency": AlertSeverity.EMERGENCY,
        }
        severity = severity_map.get(level.lower(), AlertSeverity.INFO)
        category = AlertCategory.SYSTEM
        if "zk" in source.lower() or "proof" in source.lower():
            category = AlertCategory.SECURITY
        elif "consensus" in source.lower():
            category = AlertCategory.CONSENSUS
        elif "performance" in source.lower():
            category = AlertCategory.PERFORMANCE

        alert = Alert(
            alert_id=f"ALERT-{int(time.time() * 1000)}",
            timestamp=time.time(),
            severity=severity,
            category=category,
            title=title,
            description=message,
            source_component=source,
            metadata=details,
        )
        self.active_alerts[alert.alert_id] = alert
        self.alert_history.append(alert)
        self.stats['total_alerts'] += 1

        log_level_map = {
            AlertSeverity.INFO: logging.INFO,
            AlertSeverity.WARNING: logging.WARNING,
            AlertSeverity.CRITICAL: logging.CRITICAL,
            AlertSeverity.EMERGENCY: logging.CRITICAL,
        }
        self.logger.log(
            log_level_map.get(severity, logging.INFO),
            f"[{severity.value.upper()}] {title}: {message}"
        )
        _send_notifications(self, alert)

    def acknowledge_alert(self, alert_id: str, user: str | None = None) -> bool:
        return _acknowledge_alert(self, alert_id, user)

    def resolve_alert(self, alert_id: str, user: str | None = None) -> bool:
        return _resolve_alert(self, alert_id, user)

    def get_active_alerts(
        self,
        category: AlertCategory | None = None,
        severity: AlertSeverity | None = None
    ) -> list[Alert]:
        return _get_active_alerts(self, category, severity)

    def get_alert_statistics(self) -> dict[str, Any]:
        return _get_alert_statistics(self)

    def generate_report(
        self, format_type: str = "json", include_history: bool = False
    ) -> str:
        active_alerts = list(self.active_alerts.values())
        if format_type == "json":
            return _generate_json_report(self, active_alerts, include_history)
        if format_type == "text":
            return _generate_text_report(self, active_alerts)
        raise ValueError(f"Unsupported report format: {format_type}")


def _initialize_default_rules(manager: AlertManager) -> None:
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
    if 'email' in manager.config:
        manager.notifiers.append(EmailNotifier(manager.config['email']))
    if 'webhook' in manager.config:
        manager.notifiers.append(WebhookNotifier(manager.config['webhook']))


def _process_rule_for_metric(
    manager: AlertManager, rule: AlertRule, metric_name: str,
    value: float, source_component: str
) -> None:
    if not rule.enabled or rule.metric_name != metric_name:
        return
    if (
        _evaluate_rule_condition(manager, rule, value)
        and not _is_in_cooldown(manager, rule)
    ):
        _create_alert(manager, rule, value, source_component, None)


def _evaluate_rule_condition(
    manager: AlertManager, rule: AlertRule, value: float
) -> bool:
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
    last_alert_time = manager.last_alert_times.get(rule.rule_id, 0)
    return time.time() - last_alert_time < rule.cooldown_period


def _create_alert(
    manager: AlertManager, rule: AlertRule, current_value: float | None,
    source_component: str, custom_description: str | None
) -> None:
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
    for existing_alert in manager.active_alerts.values():
        if (
            existing_alert.category == alert.category
            and existing_alert.metric_name == alert.metric_name
            and existing_alert.status == AlertStatus.ACTIVE
        ):
            return True
    return False


def _trim_alert_history(manager: AlertManager) -> None:
    if len(manager.alert_history) > manager.max_history_size:
        manager.alert_history = manager.alert_history[-manager.max_history_size:]


def _update_alert_stats(manager: AlertManager, alert: Alert) -> None:
    manager.stats['total_alerts'] = cast(int, manager.stats['total_alerts']) + 1
    severity_stats = cast(defaultdict, manager.stats['alerts_by_severity'])
    severity_stats[alert.severity.value] += 1
    category_stats = cast(defaultdict, manager.stats['alerts_by_category'])
    category_stats[alert.category.value] += 1


def _schedule_alert_escalation(
    manager: AlertManager, alert_id: str, escalation_time: int
) -> None:
    timer = threading.Timer(
        escalation_time, _escalate_alert, args=(manager, alert_id)
    )
    timer.start()
    manager.escalation_timers[alert_id] = timer


def _send_notifications(manager: AlertManager, alert: Alert) -> None:
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
    alerts = list(manager.active_alerts.values())
    if category:
        alerts = [a for a in alerts if a.category == category]
    if severity:
        alerts = [a for a in alerts if a.severity == severity]
    return alerts


def _get_alert_statistics(manager: AlertManager) -> dict[str, Any]:
    return {
        **manager.stats,
        'active_alerts': len(manager.active_alerts),
        'alert_rules': len(manager.alert_rules),
        'enabled_rules': len([r for r in manager.alert_rules.values() if r.enabled])
    }


def _generate_json_report(
    manager: AlertManager, active_alerts: list[Alert], include_history: bool
) -> str:
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
