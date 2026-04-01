---
title: "Triển khai an toàn"
description: "Bật xác thực, CORS/HSTS, Rate Limit, API Key và Resource Guard; hướng dẫn cấu hình môi trường sản xuất cho HieraChain."
icon: material/shield-check
---

# Triển khai an toàn

Cấu hình HieraChain ở môi trường production với các biện pháp bảo vệ cơ bản (AUTH, CORS/HSTS, Rate Limit, API key) và bảo vệ tài nguyên (Resource Guard).

## Chuẩn bị môi trường

* Quản lý secrets bằng biến môi trường/secret manager (không commit .env lên VCS).
* Bật logging phù hợp (`LOG_LEVEL=INFO` hoặc `WARNING`).

## Bật xác thực API Key

Trong production, xác thực API key phải bật (theo `ProductionSettings`). Đối với môi trường dev/test, có thể bật thủ công:

```dotenv
# .env
HRC_AUTH_ENABLED=true
HRC_API_KEY_LOCATION=header
HRC_API_KEY_NAME=X-API-Key
```

Client cần gửi header:

```bash
X-API-Key: <your-secret-key>
```

Mã xác minh API key: `hierachain/security/verify/api_key_verifier.py`.

## Cấu hình CORS

Chỉ cho phép origin tin cậy trong production:

```dotenv
# .env
HRC_CORS_ALLOW_ALL=false
HRC_CORS_ORIGINS=https://admin.example.com,https://console.example.com
```

## Bật HSTS (HTTPS)

Thêm header HSTS để trình duyệt cưỡng bức HTTPS:

```dotenv
# .env
HRC_HSTS_ENABLED=true
HRC_HSTS_MAX_AGE=31536000
```

## Bật Rate Limiting

Giảm thiểu DoS ở cấp ứng dụng:

```dotenv
# .env
HRC_RATE_LIMIT=true
HRC_RATE_LIMIT_RPM=100
```

Lưu ý: triển khai thực tế nên kết hợp rate limit ở reverse proxy (Nginx/Envoy/API Gateway).

## Bảo vệ tài nguyên (Resource Guard)

Sử dụng middleware `ResourceGuardMiddleware` để từ chối request khi CPU/RAM vượt ngưỡng:

```python
# Ví dụ tích hợp (mang tính mô tả) trong FastAPI app
from fastapi import FastAPI
from hierachain.security.resource_guard import ResourceGuardMiddleware

app = FastAPI()
app.add_middleware(
    ResourceGuardMiddleware,
    memory_threshold_percent=85.0,
    cpu_threshold_percent=85.0,
)
```

Mô-đun: `hierachain/security/resource_guard.py`. Middleware này sử dụng `monitoring/performance_monitor.py` để lấy số liệu.

## Khởi động dịch vụ

```bash
python -m hierachain.api.server
```

Mặc định phục vụ tại `http://localhost:2661`. Đặt `HRC_API_HOST`/`HRC_API_PORT` nếu cần.

## Kiểm chứng nhanh

1. Thiếu API key (khi `HRC_AUTH_ENABLED=true`) → kỳ vọng 401/403:

    ```bash
    curl -i http://localhost:2661/api/v1/health
    ```

2. Có API key:

    ```bash
    curl -i -H "X-API-Key: <your-secret-key>" http://localhost:2661/api/v1/health
    ```

3. Tải nặng → ResourceGuard có thể trả 503 (nếu ngưỡng vượt quá).

## Secrets & cấu hình an toàn

* Không in secrets ra log/console.
* Dùng `python-dotenv` chỉ trong dev; production dùng hệ thống secrets (K8s Secret, Vault…).
* Kiểm tra `hierachain/security/secure_logging.py` và `security/sanitization.py` để tránh rò rỉ dữ liệu nhạy cảm.

## Production Checklist

Dưới đây là checklist nhanh để triển khai HieraChain trong production:

### Bắt buộc

```bash
# Thiết lập môi trường production
export HRC_ENV=production

# Bật xác thực
export HRC_AUTH_ENABLED=true

# Chính sách tin cậy P2P nghiêm ngặt
export HRC_P2P_TRUST_POLICY=strict
```

### Khuyến nghị

```bash
# Sử dụng biến môi trường cho master key
export HRC_MASTER_KEY_SOURCE=env

# Bật rate limiting
export HRC_RATE_LIMIT=true
export HRC_RATE_LIMIT_RPM=100

# Bật HSTS
export HRC_HSTS_ENABLED=true
```

### Optional (Enterprise)

```bash
# Sử dụng Vault bên ngoài
export HRC_VAULT_ADDR=https://vault.company.com

# Bật HSM cho key management
export HRC_HSM_ENABLED=true
```

### Kiểm tra cấu hình

Sau khi cấu hình, bạn có thể kiểm tra cấu hình bảo mật bằng cách:

```python
from hierachain.config.settings import check_security_config

warnings = check_security_config()
for w in warnings:
    print(f"WARNING: {w}")
```

!!! tip "Mẹo"
    * Chỉ WARN, không ngăn chặn dev dùng insecure mode (giữ flexibility)
    * Dev tự handle enterprise integrations (LDAP, HSM, SIEM) bên ngoài

## Liên quan

* Mô‑đun Security: [Security](../modules/security.md)
* Kiến trúc Bảo mật: [Bảo mật (chuyên sâu)](../architecture/security.md)
* Tham chiếu Cấu hình: [Config](../reference/config.md)

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * Các biến bảo mật/cấu hình đọc từ `hierachain/config/settings.py` (AUTH, CORS, HSTS, Rate Limit, API Key…).
    * `ResourceGuardMiddleware` từ chối yêu cầu khi tài nguyên hệ thống vượt ngưỡng.

    **DECISION**

    * Production phải bật AUTH, HSTS, CORS hạn chế, và (khuyến nghị) Rate Limit.
    * Dùng API key làm baseline; có thể nâng cấp lên OAuth/mTLS ở lớp edge/gateway.

    **ASSUMPTION**

    * Hệ thống triển khai sau reverse proxy có TLS terminator.
    * Secrets được quản trị bởi công cụ chuyên dụng (K8s Secret, Vault, AWS/GCP Secret Manager).

    **INVARIANT**

    * Yêu cầu thay đổi trạng thái phải qua xác thực khi `AUTH_ENABLED=true`.
    * Log không ghi lộ dữ liệu nhạy cảm.

    **EDGE CASES**

    * Thiếu/nhầm header API key → 401/403.
    * CORS cấu hình sai → lỗi preflight/blocked by CORS policy.
    * Ngưỡng ResourceGuard quá chặt → false positive 503; cần điều chỉnh phù hợp workload.
