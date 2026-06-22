"""
Notification adapters (Email, Webhook) for Alert System.
"""

from __future__ import annotations

import logging
import os
import smtplib
from typing import Any, cast
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

from hierachain.monitoring.types import Alert, AlertSeverity

logger = logging.getLogger(__name__)


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


def _set_smtp_from_env(self: EmailNotifier, smtp_config: dict[str, Any]) -> None:
    self.smtp_server = smtp_config.get('server', 'localhost')
    self.smtp_port = smtp_config.get('port', 587)
    self.username = os.environ.get('HRC_SMTP_USERNAME', smtp_config.get('username'))
    self.password = os.environ.get('HRC_SMTP_PASSWORD', smtp_config.get('password'))
    if self.password in ("default_password", "password", "admin"):
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
