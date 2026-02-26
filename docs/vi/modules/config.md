---
title: "Config module"
description: "Tổng quan module cấu hình: settings, logging; phân biệt với Reference/config (biến môi trường)."
icon: material/cog
---

# Config Module (`hierachain/config/*`)

## Mục đích

Đóng gói cấu hình hệ thống ở dạng Pythonic, cung cấp API truy cập/kiểm chứng cấu hình cho các thành phần khác của HieraChain.

## Kiến trúc & khái niệm

* Settings: `hierachain/config/settings.py` — lớp `Settings` và biến `settings` (theo môi trường: dev/test/product), cùng hàm `get_settings()`.
* Logging: `hierachain/config/logging.py` — (nếu áp dụng) cấu hình logging chuẩn.

## API công khai (Public API)

```python
from hierachain.config.settings import settings, get_settings

cfg = settings  # thể hiện cấu hình global theo env
api = cfg.get_api_config()        # {"version": ..., "host": ..., "port": ...}
cons = cfg.get_consensus_config() # {"type": ..., "validator_timeout": ...}
errs = cfg.validate_config()      # list lỗi cấu hình (nếu có)
```

Mô tả các trường quan trọng (ví dụ):

* Blockchain: `BLOCK_SIZE_LIMIT`, `PROOF_SUBMISSION_INTERVAL`
* Consensus: `CONSENSUS_TYPE`, `BFT_ENABLED`, `BFT_NODE_COUNT`
* Storage: `DEFAULT_STORAGE_BACKEND`, `DATABASE_URL`, `REDIS_*`
* Security: `AUTH_ENABLED`, `API_KEY_*`, `HSTS_*`, `RATE_LIMIT_*`, `MSP_ENABLED`
* API: `API_VERSION`, `API_HOST`, `API_PORT`
* ZK Proofs: `ENABLE_ZK_PROOFS`, `ZK_*`
* K8s/Proof Aggregation/Rebalance/Cross‑level Sync: các biến `K8S_*`, `PROOF_*`, `REBALANCE_*`, `CROSS_LEVEL_*`

## Cấu hình

* Tham chiếu chi tiết biến môi trường: xem trang [Reference/Config](../reference/config.md).
* Chọn môi trường bằng `HRC_ENV` (`dev`/`test`/`product`).

## Tính năng & hạn chế

* Tính năng: tập trung hóa cấu hình, có kiểm chứng tối thiểu (`validate_config`).
* Hạn chế: một số giá trị cần override qua biến môi trường khi triển khai thực tế (API host/port, DB, CORS…).

## Bảo mật & quyền truy cập

* Không ghi log secret/khóa; dùng biến môi trường/secret manager để cấp phát giá trị nhạy cảm.

## Xử lý lỗi & khắc phục

* `validate_config()` trả về danh sách lỗi để phát hiện cấu hình sai ngay khi khởi động.

## Hiệu năng

* Truy cập cấu hình là O(1); không gây overhead đáng kể.

## Liên quan

* Tham chiếu Config: [Config](../reference/config.md)
* Kiến trúc Bảo mật: [Bảo mật (chuyên sâu)](../architecture/security.md)

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * Các hằng/số và phương thức cấu hình định nghĩa trong `hierachain/config/settings.py` (có `Settings`, `ProductionSettings`, `DevelopmentSettings`, `TestingSettings`, `get_settings()`, `settings`).

    **DECISION**

    * Phân tách "module overview" (trang này) và "reference biến môi trường" (trang Reference/config) để tài liệu dễ tra cứu.

    **ASSUMPTION**

    * Môi trường triển khai có thể cung cấp biến môi trường phù hợp (Docker/K8s/CI/CD).

    **INVARIANT**

    * Các biến bắt buộc phải hợp lệ (port trong 1..65535, backend thuộc {memory, redis, sqlite}, …).

    **EDGE CASES**

    * Thiết lập mâu thuẫn (ví dụ bật BFT nhưng số node < 3f+1) cần phát hiện sớm và cảnh báo.
