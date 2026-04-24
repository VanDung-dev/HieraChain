# WF-13: Risk Analysis & Alert Lifecycle

**Group**: E — Operational & Integration Layer
**Trigger**: `PerformanceMonitor` fires on schedule, or `AlertManager.check_metric()` called with a new metric value
**Output**: Active alerts dispatched via Email/Webhook; unacknowledged alerts auto-escalate
**Key modules**: `risk_management/risk_analyzer.py`, `monitoring/alert_system.py`, `monitoring/performance_monitor.py`

> [← WF-12: IPFS Storage](./wf-12-ipfs-storage.md) · [Back to Overview](../ARCHITECTURE.md) · [WF-14: ERP Integration →](./wf-14-erp-integration.md)

---

## Overview

HieraChain continuously monitors system health across **4 risk domains** (Consensus, Security, Performance, Storage). When thresholds are breached, `AlertManager` creates alerts, suppresses duplicates via cooldown, notifies via Email/Webhook, and auto-escalates unacknowledged alerts after a configurable timeout.

---

## Flow Diagram

```mermaid
sequenceDiagram
    autonumber
    participant PM as 📊 PerformanceMonitor
    participant RA as 🔍 RiskAnalyzer
    participant AM as 🚨 AlertManager
    participant AD as 📈 AnomalyDetector
    participant NTF as 📧 Email / Webhook Notifier

    PM->>RA: perform_comprehensive_analysis(system_data)

    par Consensus risks
        RA->>RA: analyze_consensus_risks()<br/>Check: node_count >= 3f+1, leader_timeout, msg_verify_rate
    and Security risks
        RA->>RA: analyze_security_risks()<br/>Check: cert_expiry, failed_auth, encryption_strength
    and Performance risks
        RA->>RA: analyze_performance_risks()<br/>Check: CPU%, memory%, event_pool_size
    and Storage risks
        RA->>RA: analyze_storage_risks()<br/>Check: world_state_size, backup_age
    end

    RA->>RA: Update active_risks + risk_history
    RA-->>PM: all_risks { consensus, security, performance, storage }

    PM->>AM: check_metric(metric_name, value, source)
    AM->>AD: add_data_point(metric_name, value)
    AM->>AM: _evaluate_rule_condition(rule, value)
    AM->>AM: _is_in_cooldown(rule)

    alt Threshold breached AND not in cooldown
        AM->>AM: _create_alert(rule, value, source)
        AM->>AM: _is_duplicate_alert() → suppress if duplicate
        AM->>AM: active_alerts[alert_id] = Alert
        AM->>NTF: _send_notifications(alert)
        NTF-->>AM: sent / failed

        Note over AM: Escalation timer starts (default 30 min)

        alt Alert not acknowledged within escalation_time
            AM->>AM: _escalate_alert(alert_id)<br/>alert.escalation_level += 1
            AM->>NTF: Re-notify with ESCALATED prefix
        end
    end

    Note over AM: Operator acknowledges or system auto-resolves

    AM->>AM: acknowledge_alert(alert_id) → ACKNOWLEDGED
    AM->>AM: resolve_alert(alert_id) → RESOLVED + remove from active_alerts
```

---

## Alert Severity Levels

| Severity | Trigger Example | Auto-Escalate After |
|:---------|:---------------|:--------------------|
| `INFO` | Normal metric fluctuation | Never |
| `WARNING` | CPU > 85%, minor risk detected | 30 minutes |
| `CRITICAL` | CPU > 95%, consensus success < 95% | Immediate (5 min) |
| `EMERGENCY` | Manual declaration or compound failure | Immediate |

---

## Risk Domains

| Domain | Key Metrics Checked |
|:-------|:--------------------|
| **Consensus** | `node_count >= 3f+1`, leader election time, message verification rate |
| **Security** | Certificate expiry (days remaining), failed authentication rate, encryption algorithm strength |
| **Performance** | CPU %, memory %, event pool queue size, block finalization latency |
| **Storage** | World state DB size, backup staleness (hours since last backup) |

---

## Step-by-Step Breakdown

| Step | Description |
|:-----|:------------|
| **1. Analysis** | `RiskAnalyzer.perform_comprehensive_analysis()` runs 4 domain checks in parallel |
| **2. Metric check** | `AlertManager.check_metric()` evaluates each incoming metric against defined rules |
| **3. Anomaly detection** | `AnomalyDetector` uses statistical baseline to flag outliers |
| **4. Cooldown check** | Rules have configurable cooldown period to suppress alert storms |
| **5. Duplicate check** | `_is_duplicate_alert()` suppresses if same rule + same source already active |
| **6. Notification** | Email and/or Webhook notifiers dispatch concurrently |
| **7. Escalation** | Unacknowledged alerts auto-escalate: `escalation_level += 1`, re-notified |
| **8. Lifecycle end** | Operator acknowledges → `ACKNOWLEDGED`; metric recovers → `RESOLVED` |

---

## Error Handling

| Condition | Behavior |
|:----------|:---------|
| Email notification fails | Logged as warning; Webhook notifier still attempted |
| Webhook endpoint unreachable | Retry once; log failure; alert marked `notification_failed` |
| Alert storm (too many duplicates) | Cooldown mechanism suppresses duplicates per rule |
| RiskAnalyzer raises exception | Exception caught, partial risk data returned, alert triggered for analysis failure |

---

## Key Classes & Methods

| Step | Class / Method | File |
|:-----|:--------------|:-----|
| Trigger analysis | `RiskAnalyzer.perform_comprehensive_analysis()` | `risk_management/risk_analyzer.py` |
| Metric check | `AlertManager.check_metric()` | `monitoring/alert_system.py` |
| Anomaly detection | `AnomalyDetector.is_anomaly()` | `monitoring/alert_system.py` |
| Create alert | `AlertManager._create_alert()` | `monitoring/alert_system.py` |
| Email notify | `EmailNotifier.send_alert()` | `monitoring/alert_system.py` |
| Webhook notify | `WebhookNotifier.send_alert()` | `monitoring/alert_system.py` |
| Escalate | `AlertManager._escalate_alert()` | `monitoring/alert_system.py` |
| Acknowledge | `AlertManager.acknowledge_alert()` | `monitoring/alert_system.py` |

---

## See Also

- [WF-5: Cluster Lockdown](./wf-05-cluster-lockdown.md) — unresolved critical alerts may trigger lockdown
- [WF-9: System Integrity Validation](./wf-09-integrity-validation.md) — DEGRADED integrity status triggers alerts here
