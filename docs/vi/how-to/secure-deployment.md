---
title: "Triển khai an toàn"
description: "Bật xác thực, CORS/HSTS, Rate Limit, API Key và ordering limits; hướng dẫn cấu hình môi trường sản xuất cho HieraChain."
icon: material/shield-check
---

# Triển khai an toàn

Cấu hình xác thực API key, CORS, giới hạn tốc độ và giới hạn ordering trong HieraChain. Kết thúc HTTPS và cấu hình HSTS tại reverse proxy hoặc API gateway doanh nghiệp. Cấp signing identity và bản đồ khóa đáng tin cậy theo [Quickstart](../getting-started/quickstart.md) trước khi khởi tạo chain.

## Chuẩn bị môi trường

* Quản lý secrets bằng biến môi trường/secret manager (không commit .env lên VCS).
* Bật logging phù hợp (`LOG_LEVEL=INFO` hoặc `WARNING`).

## Bật xác thực API key

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

## Cấu hình HSTS tại proxy HTTPS

Đặt `Strict-Transport-Security` trên response HTTPS tại reverse proxy hoặc API gateway. HieraChain khai báo các cấu hình sau, nhưng HTTP middleware không dùng chúng để thêm header này:

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

## Giới hạn ordering

Không có `ResourceGuardMiddleware` hay `security/resource_guard.py` trong code. Bảo vệ DoS/limit thực tế là: `api/middleware.py:add_rate_limit` / `add_payload_limit`, và kiểm tra `HRC_RAM_CRITICAL_THRESHOLD` / `HRC_EVENT_POOL_MAX_SIZE` trong ordering/storage. Đừng import `ResourceGuardMiddleware` không tồn tại; hãy kết hợp rate limiting ở app với reverse-proxy.

## Khởi động dịch vụ

```bash
python -m hierachain
```

Mặc định phục vụ tại `http://localhost:2661`. Đặt `HRC_API_HOST`/`HRC_API_PORT` nếu cần.

## Kiểm tra

1. Thiếu API key → kỳ vọng 401:

    ```bash
    curl -i http://localhost:2661/api/ledger/chains
    ```

2. Có API key:

    ```bash
    curl -i -H "X-API-Key: <your-secret-key>" http://localhost:2661/api/ledger/chains
    ```

3. Kiểm tra payload/rate limit của API, lỗi Redis, giới hạn event pool/RAM trong ordering và log lỗi storage. Không có `ResourceGuardMiddleware` CPU/RAM ở API.

## Bí mật và cấu hình

* Không ghi secret vào log của dịch vụ hoặc CI. Lệnh cấp key in key ban đầu một lần trên terminal của operator; lưu key vào kho secret của client.
* Dùng `python-dotenv` chỉ trong dev; production dùng hệ thống secrets (K8s Secret, Vault…).
* Kiểm tra `hierachain/security/secure_logging.py` và `security/sanitization.py` để tránh rò rỉ dữ liệu nhạy cảm.

## Danh sách kiểm tra production

Dưới đây là checklist nhanh để triển khai HieraChain trong production:

### Bắt buộc

```bash
# Set production environment
export HRC_ENV=production

# Configure PostgreSQL explicitly when using the PostgreSQL storage backend
export HRC_STORAGE_BACKEND=postgres
export DATABASE_URL=postgresql+psycopg://user:password@db:5432/hierachain
# HRC_DATABASE_URL may be used instead of DATABASE_URL

# Enable authentication
export HRC_AUTH_ENABLED=true
export HRC_API_KEYS_FILE=/absolute/path/to/api-keys.json

# Provisioned signing identity and trusted block keys
export HRC_VALIDATOR_IDENTITY=/absolute/path/to/identity.json
export HRC_BLOCK_TRUSTED_KEYS_FILE=/absolute/path/to/trusted-block-keys.json

# Strict P2P trust policy
export HRC_P2P_TRUST_POLICY=strict
```

### Khuyến nghị

```bash
# Use environment variable for master key
export HRC_MASTER_KEY_SOURCE=env

# Enable rate limiting
export HRC_RATE_LIMIT=true
export HRC_RATE_LIMIT_RPM=100

# HSTS header must be configured at the HTTPS reverse proxy.
# This declared setting does not add the header in HieraChain.
export HRC_HSTS_ENABLED=true
```

### Tích hợp doanh nghiệp tùy chọn

```bash
# Use external Vault (actual envs are HRC_VAULT_TOKEN / HRC_VAULT_PATH / HRC_VAULT_URL, not HRC_VAULT_ADDR)
export HRC_VAULT_TOKEN=your_token
export HRC_VAULT_PATH=/path/to/vault

# HSM is not a boolean HRC_HSM_ENABLED flag in code; use KeyProvider interface + HRC_VAULT_* / HSM integration externally
```

### Kiểm tra cấu hình

Sau khi cấu hình, bạn có thể kiểm tra cấu hình bảo mật bằng cách:

```python
from hierachain.config.settings import check_security_config

warnings = check_security_config()
for w in warnings:
    print(f"WARNING: {w}")
```

`check_security_config()` trả cảnh báo cấu hình; nó không kiểm tra header proxy hay kết nối backend. Khi khởi động production, ứng dụng kiểm tra riêng và từ chối cấu hình tắt xác thực hoặc thiếu/sai API key. Cấu hình tích hợp LDAP, HSM và SIEM tại ứng dụng chủ hoặc môi trường triển khai.

## Liên quan

* Mô‑đun Security: [Security](../modules/security.md)
* Kiến trúc Bảo mật: [Bảo mật (chuyên sâu)](../architecture/security.md)
* Tham chiếu Cấu hình: [Config](../reference/config.md)
