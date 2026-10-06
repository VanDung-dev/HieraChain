"""Public monitoring and alert lifecycle contracts survive structural changes."""

import subprocess
import sys
import threading
from queue import Queue
from unittest.mock import Mock

import pytest

from hierachain.monitoring import AlertManager, PerformanceMonitor
from hierachain.monitoring.types import (
    Alert,
    AlertCategory,
    AlertRule,
    AlertSeverity,
    MetricType,
    MetricUnit,
    PerformanceMetric,
)
from hierachain.serialization import loads_json


@pytest.mark.parametrize(
    "condition, threshold, values",
    [
        ("greater_than", 0, [0, 1]),
        ("less_than", 0, [0, -1]),
        ("equals", 0, [1, 0]),
        ("anomaly", None, [1, 2] * 5 + [100]),
    ],
)
def test_alert_conditions_keep_zero_thresholds_and_anomaly_history(
    condition: str,
    threshold: float | None,
    values: list[float],
) -> None:
    manager = AlertManager()
    manager.alert_rules.clear()
    rule = AlertRule(
        "probe",
        "Probe",
        "Threshold probe",
        AlertCategory.PERFORMANCE,
        "probe",
        condition,
        threshold,
        AlertSeverity.WARNING,
        cooldown_period=0,
        escalation_time=0,
    )
    manager.add_alert_rule(rule)
    try:
        for value in values:
            manager.check_metric("probe", value, "test")
        active = manager.get_active_alerts()
        assert len(active) == 1
        assert active[0].current_value == values[-1]
        assert manager._notification_worker is None
    finally:
        manager.close()


def test_alert_lifecycle_cooldown_filters_and_reports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timer = Mock()
    timer_factory = Mock(return_value=timer)
    monkeypatch.setattr("hierachain.monitoring.alert_system.threading.Timer", timer_factory)
    manager = AlertManager()
    manager.alert_rules.clear()
    rule = AlertRule(
        "probe",
        "Probe",
        "Lifecycle probe",
        AlertCategory.SYSTEM,
        "probe",
        "greater_than",
        0,
        AlertSeverity.WARNING,
    )
    manager.add_alert_rule(rule)
    try:
        manager.check_metric("probe", 1)
        manager.check_metric("probe", 2)
        active = manager.get_active_alerts(AlertCategory.SYSTEM, AlertSeverity.WARNING)
        assert len(active) == 1
        alert_id = active[0].alert_id
        timer.start.assert_called_once()
        args, kwargs = timer_factory.call_args
        args[1](*kwargs["args"])
        assert active[0].escalation_level == 1
        assert manager.acknowledge_alert(alert_id, "operator")
        timer.cancel.assert_called_once()
        assert not manager.escalation_timers
        assert manager.resolve_alert(alert_id, "operator")
        assert not manager.get_active_alerts()
        assert not manager.resolve_alert("missing")
        report = loads_json(manager.generate_report(include_history=True))
        assert report["statistics"]["total_alerts"] == 1
        assert report["alert_history"][0]["status"] == "resolved"
        assert "No active alerts." in manager.generate_report("text")
        with pytest.raises(ValueError, match="Unsupported report"):
            manager.generate_report("csv")
    finally:
        manager.close()


def test_delivery_failure_and_full_queue_keep_alert_history() -> None:
    manager = AlertManager()
    manager._notification_queue = Queue(maxsize=1)
    started = threading.Event()
    release = threading.Event()
    delivered = []

    class Notifier:
        def send_alert(self, alert: Alert) -> bool:
            delivered.append(alert.alert_id)
            if alert.alert_id.startswith("probe-0_"):
                started.set()
                assert release.wait(3)
                raise OSError("delivery unavailable")
            return True

    manager.notifiers = [Notifier()]
    try:
        for index in range(3):
            rule = AlertRule(
                f"probe-{index}",
                "Probe",
                "Queue probe",
                AlertCategory.SYSTEM,
                f"probe-{index}",
                "greater_than",
                0,
                AlertSeverity.WARNING,
                escalation_time=0,
            )
            manager.create_alert(rule, 1)
            if index == 0:
                assert started.wait(2)
        assert len(manager.alert_history) == 3
        assert manager.get_alert_statistics()["notifications_failed"] == 1
    finally:
        release.set()
        manager.close(timeout=3)
    assert manager._notification_worker is not None
    assert not manager._notification_worker.is_alive()
    assert len(delivered) == 2
    stats = manager.get_alert_statistics()
    assert stats["notifications_failed"] == 2
    assert stats["notifications_sent"] == 1


@pytest.mark.parametrize("enable_alerts", [True, False])
def test_monitor_callbacks_fail_independently_and_stop_wakes_long_interval(
    monkeypatch: pytest.MonkeyPatch,
    enable_alerts: bool,
) -> None:
    monitor = PerformanceMonitor({"collection_interval": 60, "enable_alerts": enable_alerts})
    for name in ("cpu", "memory", "disk", "network"):
        monkeypatch.setattr(monitor.system_collector, f"collect_{name}_metrics", lambda: {})
    collected = threading.Event()
    received = []

    def broken_callback() -> float:
        raise OSError("metric unavailable")

    def broken_handler(level: str, metric: PerformanceMetric, value: float) -> None:
        raise OSError("consumer unavailable")

    def healthy_handler(level: str, metric: PerformanceMetric, value: float) -> None:
        if metric.name == "healthy":
            received.append((level, value))

    def healthy_callback() -> float:
        collected.set()
        return 0

    monitor.add_custom_metric(
        "broken", MetricType.CUSTOM, MetricUnit.COUNT, "Broken callback", callback=broken_callback
    )
    monitor.add_custom_metric(
        "healthy",
        MetricType.CUSTOM,
        MetricUnit.COUNT,
        "Healthy callback",
        threshold_critical=0,
        callback=healthy_callback,
    )
    monitor.add_alert_handler(broken_handler)
    monitor.add_alert_handler(healthy_handler)
    try:
        monitor.start_monitoring()
        thread = monitor.monitoring_thread
        monitor.start_monitoring()
        assert monitor.monitoring_thread is thread
        assert collected.wait(2)
    finally:
        monitor.stop_monitoring()
    assert thread is not None and not thread.is_alive()
    assert received == ([("critical", 0)] if enable_alerts else [])
    assert monitor.get_current_metrics()["healthy"]["current_value"] == 0
    assert len(monitor.get_metric_history("healthy")) == 1
    assert monitor.get_current_metrics()["broken"]["current_value"] is None


def test_monitor_reports_history_and_health_score_keep_public_shapes() -> None:
    monitor = PerformanceMonitor()
    monitor.metrics.clear()
    assert monitor.get_health_score() == (0.0, "no_data")
    monitor.add_custom_metric(
        "probe", MetricType.CUSTOM, MetricUnit.COUNT, "Probe", threshold_warning=0, threshold_critical=2
    )
    monitor.metrics["probe"].add_value(0)
    assert monitor.get_health_score() == (50.0, "warning")
    history = monitor.get_metric_history("probe", 60)
    assert history[0]["value"] == 0
    assert monitor.get_metric_history("missing") == []
    report = loads_json(monitor.generate_report("JSON"))
    assert report["monitoring_status"] == "inactive"
    assert report["summary"] == {
        "total_metrics": 1,
        "critical_alerts": 0,
        "warning_alerts": 1,
        "normal_metrics": 0,
    }
    assert "probe: 0 count" in monitor.generate_report("text")
    with pytest.raises(ValueError, match="Unsupported report"):
        monitor.generate_report("csv")


@pytest.mark.parametrize(
    "symbol, module, other",
    [
        ("PerformanceMonitor", "performance_monitor", "alert_system"),
        ("AlertManager", "alert_system", "performance_monitor"),
    ],
)
def test_public_imports_load_monitoring_and_alerting_independently(
    symbol: str,
    module: str,
    other: str,
) -> None:
    script = f"""
import sys
from importlib import import_module
import hierachain.monitoring as package
assert "hierachain.monitoring.performance_monitor" not in sys.modules
assert "hierachain.monitoring.alert_system" not in sys.modules
cls = getattr(package, {symbol!r})
assert "hierachain.monitoring.{other}" not in sys.modules
assert cls is getattr(import_module("hierachain.monitoring.{module}"), {symbol!r})
namespace = {{}}
exec("from hierachain.monitoring import *", namespace)
assert all(name in namespace for name in package.__all__)
try:
    package.missing_export
except AttributeError:
    pass
else:
    raise AssertionError("unknown exports must raise AttributeError")
"""
    subprocess.run([sys.executable, "-c", script], check=True, timeout=10)
