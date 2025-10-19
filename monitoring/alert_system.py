"""
Alert System for Hierarchical Blockchain Framework

This module provides comprehensive alerting and anomaly detection capabilities
for the risk management and performance monitoring systems. Supports real-time
alerts, anomaly detection, and integration with external notification systems.
"""

import time
import logging
import threading
import smtplib
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from collections import deque, defaultdict
import statistics
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
    metric_name: Optional[str] = None
    current_value: Optional[float] = None
    threshold_value: Optional[float] = None
    status: AlertStatus = AlertStatus.ACTIVE
    acknowledgment_time: Optional[float] = None
    resolved_time: Optional[float] = None
    escalation_level: int = 0
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
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
    threshold: Optional[float]
    severity: AlertSeverity
    enabled: bool = True
    cooldown_period: int = 300  # seconds
    escalation_time: int = 1800  # 30 minutes
    auto_resolve: bool = False
    suppress_duplicates: bool = True


class AnomalyDetector:
    """Anomaly detection for metric values"""
    
    def __init__(self, window_size: int = 100, sensitivity: float = 2.0):
        """
        Initialize anomaly detector.
        
        Args:
            window_size: Number of data points to keep for analysis
            sensitivity: Z-score threshold for anomaly detection
        """
        self.window_size = window_size
        self.sensitivity = sensitivity
        self.metric_histories: Dict[str, deque] = defaultdict(lambda: deque(maxlen=window_size))
        
    def add_data_point(self, metric_name: str, value: float):
        """Add new data point for metric"""
        self.metric_histories[metric_name].append({
            'timestamp': time.time(),
            'value': value
        })
    
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
    
    def __init__(self, smtp_config: Dict[str, Any]):
        """
        Initialize email notifier.
        
        Args:
            smtp_config: SMTP configuration dictionary
        """
        self.smtp_server = smtp_config.get('server', 'localhost')
        self.smtp_port = smtp_config.get('port', 587)
        self.username = smtp_config.get('username')
        self.password = smtp_config.get('password')
        self.from_email = smtp_config.get('from_email', 'alerts@blockchain.local')
        self.use_tls = smtp_config.get('use_tls', True)
        self.enabled = smtp_config.get('enabled', False)
        
    def send_alert(self, alert: Alert, recipients: List[str]) -> bool:
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
            logging.error(f"Failed to send email alert: {str(email_ex)}")
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
                <div style="background-color: {color}; color: white; padding: 15px; border-radius: 5px;">
                    <h2 style="margin: 0;">{alert.title}</h2>
                    <p style="margin: 5px 0 0 0;">Severity: {alert.severity.value.upper()}</p>
                </div>
                
                <div style="padding: 20px; border: 1px solid #ddd; border-top: none;">
                    <p><strong>Description:</strong> {alert.description}</p>
                    <p><strong>Source:</strong> {alert.source_component}</p>
                    <p><strong>Category:</strong> {alert.category.value}</p>
                    <p><strong>Timestamp:</strong> {datetime.fromtimestamp(alert.timestamp)}</p>
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
                    <small>This is an automated alert from the Hierarchical Blockchain monitoring system.</small>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html


class WebhookNotifier:
    """Webhook notification handler"""
    
    def __init__(self, webhook_config: Dict[str, Any]):
        """Initialize webhook notifier"""
        self.webhook_url = webhook_config.get('url')
        self.headers = webhook_config.get('headers', {'Content-Type': 'application/json'})
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
            logging.error(f"Failed to send webhook alert: {str(webhook_ex)}")
            return False


class AlertManager:
    """
    Central alert management system for hierarchical blockchain framework.
    
    Manages alert rules, anomaly detection, notification routing, and
    alert lifecycle (creation, acknowledgment, escalation, resolution).
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize alert manager.
        
        Args:
            config: Alert system configuration
        """
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Alert storage
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.max_history_size = self.config.get('max_history_size', 10000)
        
        # Alert rules
        self.alert_rules: Dict[str, AlertRule] = {}
        self._initialize_default_rules()
        
        # Anomaly detection
        self.anomaly_detector = AnomalyDetector(
            window_size=self.config.get('anomaly_window_size', 100),
            sensitivity=self.config.get('anomaly_sensitivity', 2.0)
        )
        
        # Notification handlers
        self.notifiers: List[Any] = []
        self._initialize_notifiers()
        
        # Alert suppression and rate limiting
        self.last_alert_times: Dict[str, float] = {}
        self.escalation_timers: Dict[str, threading.Timer] = {}
        
        # Statistics
        self.stats = {
            'total_alerts': 0,
            'alerts_by_severity': defaultdict(int),
            'alerts_by_category': defaultdict(int),
            'notifications_sent': 0,
            'notifications_failed': 0
        }
    
    def _initialize_default_rules(self):
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
            self.alert_rules[rule.rule_id] = rule
    
    def _initialize_notifiers(self):
        """Initialize notification handlers"""
        # Email notifier
        if 'email' in self.config:
            self.notifiers.append(EmailNotifier(self.config['email']))
        
        # Webhook notifier
        if 'webhook' in self.config:
            self.notifiers.append(WebhookNotifier(self.config['webhook']))
    
    def add_alert_rule(self, rule: AlertRule):
        """Add new alert rule"""
        self.alert_rules[rule.rule_id] = rule
        self.logger.info(f"Added alert rule: {rule.name}")
    
    def check_metric(self, metric_name: str, value: float, source_component: str = "unknown"):
        """Check metric value against alert rules"""
        # Add to anomaly detection
        self.anomaly_detector.add_data_point(metric_name, value)
        
        # Check against defined rules
        for rule in self.alert_rules.values():
            if not rule.enabled or rule.metric_name != metric_name:
                continue
            
            should_alert = False
            
            if rule.condition == "greater_than" and rule.threshold is not None:
                should_alert = value > rule.threshold
            elif rule.condition == "less_than" and rule.threshold is not None:
                should_alert = value < rule.threshold
            elif rule.condition == "equals" and rule.threshold is not None:
                should_alert = abs(value - rule.threshold) < 0.001
            elif rule.condition == "anomaly":
                is_anomaly, z_score = self.anomaly_detector.is_anomaly(metric_name, value)
                should_alert = is_anomaly
            
            if should_alert:
                # Check cooldown period
                last_alert_time = self.last_alert_times.get(rule.rule_id, 0)
                if time.time() - last_alert_time < rule.cooldown_period:
                    continue
                
                # Create alert
                self.create_alert(
                    rule=rule,
                    current_value=value,
                    source_component=source_component
                )
    
    def create_alert(self, rule: AlertRule, current_value: Optional[float] = None,
                     source_component: str = "unknown", custom_description: Optional[str] = None):
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
        
        # Check for duplicate suppression
        if rule.suppress_duplicates:
            duplicate_found = False
            for existing_alert in self.active_alerts.values():
                if (existing_alert.category == alert.category and
                    existing_alert.metric_name == alert.metric_name and
                    existing_alert.status == AlertStatus.ACTIVE):
                    duplicate_found = True
                    break
            
            if duplicate_found:
                self.logger.debug(f"Suppressing duplicate alert: {alert.title}")
                return
        
        # Store alert
        self.active_alerts[alert_id] = alert
        self.alert_history.append(alert)
        
        # Trim history if needed
        if len(self.alert_history) > self.max_history_size:
            self.alert_history = self.alert_history[-self.max_history_size:]
        
        # Update statistics
        self.stats['total_alerts'] += 1
        self.stats['alerts_by_severity'][alert.severity.value] += 1
        self.stats['alerts_by_category'][alert.category.value] += 1
        
        # Update last alert time
        self.last_alert_times[rule.rule_id] = time.time()
        
        # Send notifications
        self._send_notifications(alert)
        
        # Schedule escalation if configured
        if rule.escalation_time > 0:
            timer = threading.Timer(
                rule.escalation_time,
                self._escalate_alert,
                args=(alert_id,)
            )
            timer.start()
            self.escalation_timers[alert_id] = timer
        
        # Log alert creation
        self.logger.warning(f"Alert created: {alert.title} (ID: {alert_id})")
    
    def _send_notifications(self, alert: Alert):
        """Send alert notifications"""
        recipients = self.config.get('email_recipients', [])
        
        for notifier in self.notifiers:
            try:
                if isinstance(notifier, EmailNotifier):
                    success = notifier.send_alert(alert, recipients)
                else:
                    success = notifier.send_alert(alert)
                
                if success:
                    self.stats['notifications_sent'] += 1
                else:
                    self.stats['notifications_failed'] += 1
                    
            except Exception as notify_ex:
                self.logger.error(f"Notification failed: {str(notify_ex)}")
                self.stats['notifications_failed'] += 1
    
    def acknowledge_alert(self, alert_id: str, user: Optional[str] = None) -> bool:
        """Acknowledge an alert"""
        if alert_id not in self.active_alerts:
            return False
        
        alert = self.active_alerts[alert_id]
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledgment_time = time.time()
        
        # Cancel escalation timer
        if alert_id in self.escalation_timers:
            self.escalation_timers[alert_id].cancel()
            del self.escalation_timers[alert_id]
        
        self.logger.info(f"Alert acknowledged: {alert_id} by {user or 'unknown'}")
        return True
    
    def resolve_alert(self, alert_id: str, user: Optional[str] = None) -> bool:
        """Resolve an alert"""
        if alert_id not in self.active_alerts:
            return False
        
        alert = self.active_alerts[alert_id]
        alert.status = AlertStatus.RESOLVED
        alert.resolved_time = time.time()
        
        # Remove from active alerts
        del self.active_alerts[alert_id]
        
        # Cancel escalation timer
        if alert_id in self.escalation_timers:
            self.escalation_timers[alert_id].cancel()
            del self.escalation_timers[alert_id]
        
        self.logger.info(f"Alert resolved: {alert_id} by {user or 'system'}")
        return True
    
    def _escalate_alert(self, alert_id: str):
        """Escalate an unacknowledged alert"""
        if alert_id not in self.active_alerts:
            return
        
        alert = self.active_alerts[alert_id]
        if alert.status == AlertStatus.ACTIVE:
            alert.escalation_level += 1
            
            # Create escalation alert
            escalation_alert = Alert(
                alert_id=f"{alert_id}_ESC_{alert.escalation_level}",
                timestamp=time.time(),
                severity=AlertSeverity.CRITICAL,
                category=alert.category,
                title=f"ESCALATED: {alert.title}",
                description=f"Alert has been escalated due to no acknowledgment. Original: {alert.description}",
                source_component=alert.source_component,
                escalation_level=alert.escalation_level
            )
            
            self._send_notifications(escalation_alert)
            self.logger.critical(f"Alert escalated: {alert_id} (level {alert.escalation_level})")
    
    def get_active_alerts(self, category: Optional[AlertCategory] = None,
                         severity: Optional[AlertSeverity] = None) -> List[Alert]:
        """Get active alerts with optional filtering"""
        alerts = list(self.active_alerts.values())
        
        if category:
            alerts = [a for a in alerts if a.category == category]
        
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        return alerts
    
    def get_alert_statistics(self) -> Dict[str, Any]:
        """Get alert system statistics"""
        return {
            **self.stats,
            'active_alerts': len(self.active_alerts),
            'alert_rules': len(self.alert_rules),
            'enabled_rules': len([r for r in self.alert_rules.values() if r.enabled])
        }
    
    def generate_report(self, format_type: str = "json",
                       include_history: bool = False) -> str:
        """Generate alert system report"""
        active_alerts = list(self.active_alerts.values())
        
        if format_type.lower() == "json":
            report_data = {
                'timestamp': time.time(),
                'statistics': self.get_alert_statistics(),
                'active_alerts': [alert.to_dict() for alert in active_alerts]
            }
            
            if include_history:
                report_data['alert_history'] = [alert.to_dict() for alert in self.alert_history[-100:]]
            
            return json.dumps(report_data, indent=2, default=str)
        
        elif format_type.lower() == "text":
            lines = [
                "Alert System Report",
                "=" * 40,
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"Active Alerts: {len(active_alerts)}",
                f"Total Alerts Generated: {self.stats['total_alerts']}",
                ""
            ]
            
            if active_alerts:
                lines.append("ACTIVE ALERTS:")
                lines.append("-" * 20)
                
                for alert in sorted(active_alerts, key=lambda x: x.timestamp, reverse=True):
                    severity_symbol = {
                        AlertSeverity.INFO: 'ℹ',
                        AlertSeverity.WARNING: '⚠',
                        AlertSeverity.CRITICAL: '✗',
                        AlertSeverity.EMERGENCY: '🚨'
                    }.get(alert.severity, '?')
                    
                    lines.append(f"  {severity_symbol} {alert.title}")
                    lines.append(f"    Created: {datetime.fromtimestamp(alert.timestamp)}")
                    lines.append(f"    Source: {alert.source_component}")
                    lines.append(f"    Status: {alert.status.value}")
                    lines.append("")
            else:
                lines.append("No active alerts.")
            
            return "\n".join(lines)
        
        else:
            raise ValueError(f"Unsupported report format: {format_type}")


if __name__ == "__main__":
    # Example usage and testing
    import argparse
    
    parser = argparse.ArgumentParser(description="Alert System Test")
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--test", action="store_true", help="Run test scenario")
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Load configuration
    config_data = {}
    if args.config:
        try:
            with open(args.config, 'r') as f:
                config_data = json.load(f)
        except Exception as config_ex:
            logging.error(f"Failed to load config: {config_ex}")
    
    # Create alert manager
    alert_manager = AlertManager(config_data)
    
    if args.test:
        # Test scenario
        print("Running alert system test...")
        
        # Simulate high CPU usage
        alert_manager.check_metric("cpu_usage", 90.0, "test_component")
        
        # Simulate consensus failure
        alert_manager.check_metric("consensus_success_rate", 85.0, "consensus_module")
        
        # Generate report
        report = alert_manager.generate_report("text")
        print("\n" + report)
        
        # Print statistics
        stats = alert_manager.get_alert_statistics()
        print(f"\nAlert Statistics: {stats}")
    else:
        print("Alert system initialized. Use --test flag to run test scenario.")