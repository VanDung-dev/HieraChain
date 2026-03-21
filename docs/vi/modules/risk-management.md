---
title: "Risk Management module"
description: "Phát hiện, chấm điểm và giảm thiểu rủi ro: risk_analyzer, mitigation_strategies, audit_logger — bám sát hierachain/risk_management/*."
icon: material/alert-circle
---

# Risk Management Module (`hierachain/risk_management/*`)

## Mục đích

Giám sát và quản trị rủi ro trong quá trình vận hành hệ thống: phát hiện bất thường, chấm điểm rủi ro, kích hoạt chiến lược giảm thiểu và ghi audit.

## Kiến trúc & khái niệm

* Risk Analyzer: `hierachain/risk_management/risk_analyzer.py` — phân tích tín hiệu/metrics/sự kiện để phát hiện rủi ro.
* Mitigation Strategies: `hierachain/risk_management/mitigation_strategies.py` — tập hợp chiến lược phản ứng (giảm tải, cô lập, tạm ngưng, degrade…).
* Audit Logger: `hierachain/risk_management/audit_logger.py` — ghi vết chuẩn hóa phục vụ kiểm toán.

## API công khai (Public API)

Mô tả chữ ký tiêu biểu (mang tính tài liệu):

```python
class RiskAnalyzer:
  analyze_consensus_risks(data) -> list[RiskAssessment]  # Kiểm tra số lượng node BFT, timeout
  analyze_security_risks(data) -> list[RiskAssessment]   # Hết hạn certificate, brute force
  analyze_performance_risks(data) -> list[RiskAssessment] # CPU/RAM cao, tràn event pool
  analyze_storage_risks(data) -> list[RiskAssessment]     # Kích thước World State, sao lưu quá hạn

class MitigationStrategies:
  # Các chiến lược tự động
  add_validator_nodes(params)       # Thêm node để đảm bảo n >= 3f + 1
  renew_certificates(params)        # Gia hạn chứng chỉ sắp hết hạn
  scale_processing_capacity(params) # Mở rộng tài nguyên khi tải cao
  execute_backup(params)            # Sao lưu dữ liệu khẩn cấp
  implement_rate_limiting(params)   # Chặn brute force
```

Ví dụ sử dụng (mô tả):

```python
analyzer = RiskAnalyzer()
score = analyzer.analyze_event({"event": "production_complete", "details": {}})
if score.get("risk", 0) > 0.8:
  MitigationStrategies().apply("degrade_service", {"reason": "high_risk"})
  AuditLogger().log("mitigation", {"strategy": "degrade_service", "score": score})
```

## Cấu hình

* Có thể kết hợp với `settings.RATE_LIMIT_ENABLED` hoặc guard để giảm tải khi rủi ro cao.
* Tích hợp `monitoring/performance_monitor.py` làm nguồn metrics.

## Tính năng & hạn chế

* Tính năng: phát hiện sớm, phản ứng nhanh, ghi audit.
* Hạn chế: cần tuỳ chỉnh rule/model theo domain; mặc định chỉ là khung.

## Bảo mật & quyền truy cập

* Audit không ghi lộ dữ liệu nhạy cảm; tham chiếu `security/secure_logging.py`, `security/sanitization.py`.

## Xử lý lỗi & khắc phục

* Nếu chiến lược giảm thiểu thất bại, ghi audit và fallback sang chiến lược an toàn hơn.

## Hiệu năng

* Phân tích theo lô (batch) hoặc theo dòng (stream) tùy quy mô; tránh block luồng chính.

## Liên quan

* Monitoring: [Monitoring](monitoring.md)
* Error Mitigation: [Error Mitigation](error-mitigation.md)
* Config (tham chiếu): [Config](../reference/config.md)

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * Thành phần nằm tại `hierachain/risk_management/{risk_analyzer.py, mitigation_strategies.py, audit_logger.py}`.

    **DECISION**

    * Gắn Risk Management với Monitoring để có nguồn metrics tin cậy; mọi hành động giảm thiểu phải ghi audit.

    **ASSUMPTION**

    * Hệ thống có yêu cầu kiểm toán và phân tích nguyên nhân (post‑mortem) sau sự cố.

    **INVARIANT**

    * Mọi quyết định giảm thiểu phải có log/audit tương ứng; không bỏ ghi vết.

    **EDGE CASES**

    * False positive/negative từ phân tích rủi ro → cần ngưỡng linh hoạt và whitelist/override theo môi trường.
