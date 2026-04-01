---
title: "Monitoring module"
description: "Giám sát hiệu năng và cảnh báo: PerformanceMonitor, metrics, alert system — bám sát hierachain/monitoring/*."
icon: material/chart-line
---

# Monitoring Module (`hierachain/monitoring/*`)

## Mục đích

Theo dõi tình trạng hệ thống (CPU, RAM, thông lượng sự kiện/khối) và phát hiện sớm tình trạng bất thường để cảnh báo hoặc giảm tải.

## Kiến trúc & khái niệm

* Trình giám sát: `hierachain/monitoring/performance_monitor.py` — thu thập số liệu thời gian thực.
* Thước đo: `performance_metrics.py` — định nghĩa/tổng hợp metrics.
* Cảnh báo: `alert_system.py` — quy tắc cảnh báo, tích hợp kênh thông báo.
* Tích hợp middleware: `security/resource_guard.py` có thể dùng metrics để quyết định từ chối request khi quá tải.

## API công khai (mô tả khái quát)

```yaml
AlertSystem:
  add_rule(name, predicate, action)
  evaluate(metrics)
```

### Performance Metrics & Monitor

**File**: `hierachain/monitoring/performance_monitor.py`, `performance_metrics.py`

Thu thập và tổng hợp chỉ số hệ thống:

```python
from hierachain.monitoring.performance_monitor import PerformanceMonitor

monitor = PerformanceMonitor(interval=5.0)
monitor.start_monitoring()

# Lấy metrics hiện tại
stats = monitor.get_current_metrics()
print(f"CPU: {stats.cpu_usage}%, RAM: {stats.memory_usage}%")
```

### Alert System

**File**: `hierachain/monitoring/alert_system.py`

Hệ thống cảnh báo dựa trên ngưỡng chỉ số:

```python
from hierachain.monitoring.alert_system import AlertSystem

alerts = AlertSystem()

# Thêm quy tắc cảnh báo
alerts.add_rule(
    name="High CPU",
    predicate=lambda m: m["cpu_usage"] > 90.0,
    action=lambda m: print(f"ALERT: CPU is too high! {m['cpu_usage']}%")
)

# Đánh giá metrics
alerts.evaluate(stats)
```

### Ví dụ (mô tả):

```python
from hierachain.monitoring.performance_monitor import PerformanceMonitor
mon = PerformanceMonitor()
mon.start_monitoring()
metrics = mon.get_current_metrics()
```

## Tính năng & hạn chế

* Tính năng: thu thập định kỳ, tích hợp guard, dễ mở rộng điểm đo.
* Hạn chế: yêu cầu thread/timer; cần tối ưu overhead ở môi trường tải cao.

## Bảo mật & quyền truy cập

* Metrics có thể lộ thông tin vận hành; chỉ cung cấp cho vai trò phù hợp.

## Hiệu năng

* Lấy mẫu (sampling) với chu kỳ phù hợp; tránh tần suất quá dày.

## Liên quan

* Resource Guard: [Security](security.md)
* API: [API](api.md)

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * Các tệp hiện diện: `hierachain/monitoring/{performance_monitor.py, performance_metrics.py, alert_system.py}`.
    * `ResourceGuardMiddleware` sử dụng `PerformanceMonitor` để quyết định từ chối request khi CPU/RAM vượt ngưỡng.

    **DECISION**

    * Kết nối giám sát với guard để chủ động giảm tải khi gần ngưỡng.

    **ASSUMPTION**

    * Hệ thống log/metrics backend (Prometheus/ELK) có thể được tích hợp bổ sung.

    **INVARIANT**

    * Thu thập metrics không được làm gián đoạn xử lý chính; overhead phải kiểm soát được.

    **EDGE CASES**

    * Đồng hồ hệ thống lệch dẫn đến timestamp metrics sai; cần đồng bộ NTP.
    * Tần suất lấy mẫu quá dày gây nhiễu và tốn CPU.
