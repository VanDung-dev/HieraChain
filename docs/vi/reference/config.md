---
title: "Cấu hình"
description: "Biến môi trường và thiết lập trong hierachain/config/settings.py; cách override và giá trị mặc định."
icon: material/tune
---

# Cấu hình hệ thống

## Mục đích

Tài liệu này liệt kê các biến cấu hình chính của HieraChain (đọc từ biến môi trường và hằng số), nguồn định nghĩa tại `hierachain/config/settings.py`, kèm giá trị mặc định và gợi ý sử dụng.

## Phạm vi

* Áp dụng cho runtime API/CLI và các thành phần Sub-Chain/Main Chain trong cùng tiến trình Python.
* Không bao gồm thông số triển khai hạ tầng (k8s manifests, reverse proxy), chỉ mô tả phần biến môi trường mà Ledgerc trực tiếp.

## Cách truy cập cấu hình trong mã

```python
from hierachain.config.settings import settings

print(settings.API_HOST, settings.API_PORT)
print(settings.CONSENSUS_TYPE)
print(settings.AUTH_ENABLED)
```

## Biến môi trường và mặc định (nhóm chính)

### Môi trường chạy

* `HRC_ENV`: môi trường cấu hình, giá trị: `dev` (mặc định) | `test` | `product`. Ảnh hưởng lớp cấu hình được chọn (Development/Testing/Production).

### API

* `HRC_API_HOST` (mặc định: `localhost` ở dev, `127.0.0.1` ở production)
* `HRC_API_PORT` (mặc định: `2661`)
* `API_VERSION` (constant: `v1`)

### Đồng thuận/Blockchain

* `HRC_CONSENSUS_TYPE` (mặc định: `proof_of_authority`; hỗ trợ: `proof_of_authority`, `proof_of_federation`)
* `CONSENSUS_FEDERATION_CONFIG`: cấu hình cho federation (min_validators: 3, block_interval: 5.0)
* `VALIDATOR_TIMEOUT` (mặc định: `30` giây)
* `BFT_ENABLED` (mặc định: `True`), `BFT_FAULT_TOLERANCE` (mặc định: `1`), `BFT_NODE_COUNT` (mặc định: `4`)
* Giới hạn khối: `BLOCK_SIZE_LIMIT` (mặc định: `1000` events/block ở dev, `10` ở test)
* `PROOF_SUBMISSION_INTERVAL` (mặc định: `300` giây ở dev, `10` ở test)
* `HRC_VALIDATOR_IDENTITY`: đường dẫn file validator identity (mặc định: `validator_key.json`)

### Lưu trữ & Cache

* `HRC_STORAGE_BACKEND` (mặc định: `sqlite` ở dev, `memory` ở test, `redis` ở production; chấp nhận: `memory|redis|sqlite`)
* `WORLD_STATE_CACHE_SIZE` (mặc định: `1000`)
* Caching nâng cao: `ADVANCED_CACHING_ENABLED` (mặc định: `True`)
* `BLOCK_CACHE_SIZE` (mặc định: `5000`), `EVENT_CACHE_SIZE` (`20000`), `ENTITY_CACHE_SIZE` (`10000`)
* Cache policies: `BLOCK_CACHE_POLICY` (`lru`), `EVENT_CACHE_POLICY` (`ttl`), `ENTITY_CACHE_POLICY` (`lfu`)
* `ENTITY_TTL` (mặc định: `3600` giây)
* DB: `DATABASE_URL` (mặc định: `sqlite:///hierachain.db`)
* Redis: `REDIS_HOST` (`localhost`), `REDIS_PORT` (`6379`), `REDIS_DB` (`0`)

### Xử lý song song & tài nguyên

* `PARALLEL_PROCESSING_ENABLED` (`True`), `MAX_WORKERS` (`None` → tự động 50% CPU cores), `PROCESSING_CHUNK_SIZE` (`100`)
* Bảo vệ DoS: `HRC_EVENT_POOL_MAX_SIZE` (mặc định: `10000`), `HRC_RAM_CRITICAL_THRESHOLD` (`95.0` %)

### Bảo mật & Authentication

* `HRC_AUTH_ENABLED` (`false` ở dev/test; `True` cưỡng bức ở production)
* `HRC_API_KEY_LOCATION` (`header`), `HRC_API_KEY_NAME` (`X-API-Key`)
* Master Key: `HRC_MASTER_KEY_SOURCE` (`auto` ở dev/test, `env` ở production), `HRC_MASTER_KEY_FILE` (mặc định: `config/master_backup_key.key`)
* Brute-force protection:
    * `HRC_BF_MAX_FAILURES` (mặc định: `5`)
    * `HRC_BF_LOCKOUT_SECONDS` (mặc định: `900` = 15 phút)
    * `HRC_BF_WINDOW_SECONDS` (mặc định: `300` = 5 phút)
* Identity & Organization: `IDENTITY_MANAGER_ENABLED` (`True`), `REQUIRE_ORGANIZATION_VALIDATION` (`True`), `MSP_ENABLED` (`True`)

### P2P Network Security

* `HRC_P2P_TRUST_POLICY` (mặc định: `open` ở dev, `strict` ở production; giá trị: `open|strict`)
* `HRC_P2P_PEER_ALLOWLIST` (danh sách peer IDs phân tách bằng dấu phẩy cho chế độ strict)
* `HRC_P2P_REQUIRE_SIGNATURES` (`false` ở dev, `true` ở production)

### CORS

* `HRC_CORS_ALLOW_ALL` (`true` ở dev, `false` ở production)
* `HRC_CORS_ORIGINS` (chuỗi CSV domain; production yêu cầu chỉ định rõ)
* `CORS_ALLOW_METHODS` (danh sách phương thức cho phép)
* `CORS_ALLOW_HEADERS` (danh sách headers cho phép)

### HTTPS/HSTS

* `HRC_HSTS_ENABLED` (`false` ở dev/test; `true` ở production)
* `HRC_HSTS_MAX_AGE` (mặc định: `31536000` = 1 năm)

### Rate Limiting

* `HRC_RATE_LIMIT` (`false` ở dev/test; `true` ở production)
* `HRC_RATE_LIMIT_RPM` (mặc định: `100` requests/phút)

### Multi-Organization

* `MULTI_ORG_ENABLED` (`True`), `MSP_ENABLED` (`True`)
* `ORGANIZATION_ADMIN_THRESHOLD` (mặc định: `1`)
* `CHANNEL_CREATION_POLICY` (mặc định: `majority`; giá trị: `majority|unanimous|admin_only`)
* `AFFILIATION_HIERARCHY_ENABLED` (`True`)

### Zero-Knowledge (ZK)

* `HRC_ENABLE_ZK_PROOFS` (mặc định: `false`)
* `HRC_ZK_MODE` (`mock` hoặc `production`, mặc định `mock`)
* `HRC_ZK_VERIFICATION_KEY`, `HRC_ZK_PROVING_KEY`, `HRC_ZK_CIRCUIT` (đường dẫn)
* `HRC_ZK_REQUIRED_MAINCHAIN` (mặc định: `false`)

### Kubernetes (cách ly namespace Sub-Chain)

* `HRC_K8S_ENABLED` (mặc định: `false`)
* `HRC_K8S_NAMESPACE_PREFIX` (mặc định: `hrc-subchain-`)
* `HRC_K8S_CONFIG` (đường dẫn kubeconfig, rỗng nếu in-cluster)
* Giới hạn/tài nguyên:
    * `HRC_K8S_CPU_LIMIT` (mặc định: `1000m`)
    * `HRC_K8S_MEMORY_LIMIT` (mặc định: `1Gi`)
    * `HRC_K8S_CPU_REQUEST` (mặc định: `250m`)
    * `HRC_K8S_MEMORY_REQUEST` (mặc định: `256Mi`)

### Proof Aggregation

* `HRC_PROOF_AGGREGATION` (mặc định: `true`)
* `HRC_PROOF_BATCH_SIZE` (mặc định: `10`)
* `HRC_PROOF_BATCH_TIMEOUT` (mặc định: `30.0` giây)
* `HRC_PROOF_COMPRESSION` (mặc định: `true`)

### Sub-chain Rebalancing

* `HRC_REBALANCE_ENABLED` (mặc định: `true`)
* `HRC_REBALANCE_THRESHOLD_EPS` (mặc định: `1000` events/sec)
* `HRC_REBALANCE_CHECK_INTERVAL` (mặc định: `60.0` giây)
* `HRC_REBALANCE_MIN_EVENTS` (mặc định: `5000` events trước khi split)
* `HRC_REBALANCE_COOLDOWN` (mặc định: `300.0` giây = 5 phút)

### Đồng bộ trạng thái Cross-level

* `HRC_CROSS_LEVEL_SYNC` (mặc định: `true`)
* `HRC_CROSS_LEVEL_BATCH` (mặc định: `100`)
* `HRC_CROSS_LEVEL_TIMEOUT` (mặc định: `30.0` giây)

### Integration

* `ERP_INTEGRATION_ENABLED` (`True`)
* `SUPPORTED_ERP_SYSTEMS` (danh sách: `sap`, `oracle`, `microsoft_dynamics`)

### Logging

* `LOG_LEVEL` (mặc định: `INFO` ở dev, `DEBUG` ở test, `WARNING` ở production)
* `LOG_FORMAT` (chuỗi định dạng mặc định: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`)
* `HRC_LOG_SQL_DETAIL` (mặc định: `true` ở dev, `false` ở production)

### CLI

* `CLI_CONFIG_FILE` (mặc định: `chains.json`)
* `CLI_LOG_LEVEL` (mặc định: `INFO`)

## Ví dụ .env (phát triển)

```dotenv
HRC_ENV=dev
HRC_API_HOST=0.0.0.0
HRC_API_PORT=2661
HRC_CONSENSUS_TYPE=proof_of_authority
HRC_AUTH_ENABLED=false
HRC_CORS_ALLOW_ALL=true
DATABASE_URL=sqlite:///hierachain.db
LOG_LEVEL=DEBUG
```

## Gợi ý cấu hình production (tối thiểu)

```dotenv
HRC_ENV=product
HRC_API_HOST=0.0.0.0
HRC_AUTH_ENABLED=true
HRC_CORS_ALLOW_ALL=false
HRC_CORS_ORIGINS=https://portal.example.com
HRC_RATE_LIMIT=true
DATABASE_URL=postgresql+psycopg://user:pass@db:5432/hierachain
DEFAULT_STORAGE_BACKEND=redis
REDIS_HOST=redis
REDIS_PORT=6379
```

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * Nguồn sự thật: `hierachain/config/settings.py` định nghĩa tất cả hằng số và đọc biến môi trường bằng `os.getenv`.
    * `get_settings()` chọn lớp cấu hình theo `HRC_ENV` với các lớp: `DevelopmentSettings`, `TestingSettings`, `ProductionSettings`.
    * Invariants kiểm tra trong `validate_config()`: `BLOCK_SIZE_LIMIT > 0`, `PROOF_SUBMISSION_INTERVAL > 0`, `VALIDATOR_TIMEOUT > 0`, `DEFAULT_STORAGE_BACKEND ∈ {memory, redis, sqlite}`, `API_PORT ∈ [1, 65535]`.

    **DECISION**

    * Dùng prefix `HRC_` cho mọi biến môi trường riêng của HieraChain.
    * Production bắt buộc bật `AUTH_ENABLED`, vô hiệu `CORS_ALLOW_ALL`, khuyến nghị bật HSTS và Rate Limiting.
    * Tài liệu trình bày mặc định như trong mã; mọi ví dụ phải dùng giá trị hợp lệ theo `validate_config()`.

    **ASSUMPTION**

    * Biến môi trường được truyền vào process trước khi ứng dụng khởi động (systemd, Docker env, hoặc `.env` + `python-dotenv`).
    * Khi dùng Redis/DB, network nội bộ ổn định và thông số kết nối hợp lệ.

    **INVARIANT**

    * API_PORT luôn thuộc [1, 65535]; vi phạm sẽ bị `validate_config()` báo lỗi.
    * DEFAULT_STORAGE_BACKEND chỉ là một trong `memory|redis|sqlite`.
    * Production luôn cưỡng bức `AUTH_ENABLED=True` (theo lớp `ProductionSettings`).

    **EDGE CASES**

    * Thiết lập mâu thuẫn: `CORS_ALLOW_ALL=true` cùng lúc đặt `CORS_ORIGINS` ở production → ưu tiên policy production (khuyến nghị tắt `ALLOW_ALL`).
    * Sai phạm dải port (`API_PORT=0` hoặc >65535) → ứng dụng phải từ chối cấu hình.
    * Bật ZK ở `production` nhưng thiếu đường dẫn key/circuit → cần quy trình kiểm tra trước khi enable.
