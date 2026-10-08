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

Trong production, xác thực API key là bắt buộc. `HRC_AUTH_ENABLED=false`, thiếu file key hoặc file key không hợp lệ đều chặn khởi động. Cấu hình:

```dotenv
# .env
HRC_AUTH_ENABLED=true
HRC_API_KEY_LOCATION=header
HRC_API_KEY_NAME=X-API-Key
HRC_API_KEYS_FILE=/absolute/path/to/api-keys.json
HRC_API_KEY_REVOCATIONS_DB=/absolute/path/to/persistent/auth-state.sqlite3
```

Tạo key ban đầu và lưu metadata ở ngoài repository:

```bash
export HRC_API_KEYS_SOURCE_FILE="$HOME/.config/hierachain/api-keys.json"
python - <<'PY'
import json
import os
from pathlib import Path
from hierachain.security.key_manager import KeyManager

path = Path(os.environ["HRC_API_KEYS_SOURCE_FILE"])
path.parent.mkdir(parents=True, exist_ok=True)
manager = KeyManager()
api_key = manager.create_key(
    user_id="operator",
    permissions=["chains", "events", "proofs", "organizations:manage", "channels:manage"],
)
old_umask = os.umask(0o077)
try:
    path.write_text(json.dumps(manager.storage), encoding="utf-8")
finally:
    os.umask(old_umask)
path.chmod(0o600)
print(api_key)
PY
```

Lưu key được in ra vào kho secret của client. Với Docker Compose, đặt `HRC_API_KEYS_SOURCE_FILE` bằng đường dẫn file trên host; Compose mount file chỉ đọc tại `/run/secrets/hrc_api_keys` cho mọi node. Khi chạy trực tiếp, đặt `HRC_API_KEYS_FILE` bằng cùng đường dẫn tuyệt đối. Đặt `HRC_API_KEY_REVOCATIONS_DB` trên vùng lưu trữ ghi được và bền vững mà các worker cùng host dùng chung. Để chia sẻ revocation và lockout giữa các host, đặt cùng `HRC_AUTH_STATE_REDIS_URL` trên mọi node và bật Redis persistence. `KeyManager.revoke_key()` cập nhật trạng thái dùng chung ngay; hiện không có endpoint quản trị để thu hồi key. Để thay đổi map key, cập nhật file rồi tạo lại mọi container node Compose (hoặc khởi động lại từng tiến trình chạy trực tiếp); app không tự đọc lại file khi đang chạy.
Profile Compose `stress-test` tùy chọn cũng cần đặt `HRC_API_KEY` bằng một key đã cấp.

Client cần gửi header:

```bash
X-API-Key: <your-secret-key>
```

Mã xác minh API key: `hierachain/security/verify/api_key_verifier.py`. Client WebSocket cũng phải gửi header này.

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

## Bảo vệ tài nguyên (Lưu ý)

Không có `ResourceGuardMiddleware` hay `security/resource_guard.py` trong code. Bảo vệ DoS/limit thực tế là: `api/middleware.py:add_rate_limit` / `add_payload_limit`, và kiểm tra `HRC_RAM_CRITICAL_THRESHOLD` / `HRC_EVENT_POOL_MAX_SIZE` trong ordering/storage. Đừng import `ResourceGuardMiddleware` không tồn tại; hãy kết hợp rate limiting ở app với reverse-proxy.

## Khởi động dịch vụ

```bash
python -m hierachain.api.server
```

Mặc định phục vụ tại `http://localhost:2661`. Đặt `HRC_API_HOST`/`HRC_API_PORT` nếu cần.

## Kiểm chứng nhanh

1. Thiếu API key → kỳ vọng 401:

    ```bash
    curl -i http://localhost:2661/api/ledger/chains
    ```

2. Có API key:

    ```bash
    curl -i -H "X-API-Key: <your-secret-key>" http://localhost:2661/api/ledger/chains
    ```

3. Tải nặng → ResourceGuard có thể trả 503 (nếu ngưỡng vượt quá).

## Secrets & cấu hình an toàn

* Không ghi secret vào log của dịch vụ hoặc CI. Lệnh cấp key in key ban đầu một lần trên terminal của operator; lưu key vào kho secret của client.
* Dùng `python-dotenv` chỉ trong dev; production dùng hệ thống secrets (K8s Secret, Vault…).
* Kiểm tra `hierachain/security/secure_logging.py` và `security/sanitization.py` để tránh rò rỉ dữ liệu nhạy cảm.

## Production Checklist

Dưới đây là checklist nhanh để triển khai HieraChain trong production:

### Bắt buộc

```bash
# Thiết lập môi trường production
export HRC_ENV=production

# Cấu hình PostgreSQL tường minh khi dùng backend PostgreSQL
export HRC_STORAGE_BACKEND=postgres
export DATABASE_URL=postgresql+psycopg://user:password@db:5432/hierachain
# Có thể dùng HRC_DATABASE_URL thay cho DATABASE_URL

# Bật xác thực
export HRC_AUTH_ENABLED=true
export HRC_API_KEYS_FILE=/absolute/path/to/api-keys.json

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
# Sử dụng Vault bên ngoài (biến thực tế là HRC_VAULT_TOKEN / HRC_VAULT_PATH / HRC_VAULT_URL, không phải HRC_VAULT_ADDR)
export HRC_VAULT_TOKEN=your_token
export HRC_VAULT_PATH=/path/to/vault

# HSM không có cờ boolean HRC_HSM_ENABLED trong code; dùng interface KeyProvider + HRC_VAULT_* / tích hợp HSM bên ngoài
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
