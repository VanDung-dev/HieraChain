---
title: "Config Module"
description: "Quản lý cấu hình hệ thống, bảo mật bí mật (Secret Management) và định dạng log chuẩn hóa cho HieraChain."
icon: material/cog
---

# Config Module (`hierachain/config/*`)

## Tổng quan

Module **Config** quản lý các tham số vận hành, khóa bí mật và cấu hình ghi log của HieraChain.

---

## Các thành phần cốt lõi

<div class="grid cards" markdown>

*   :material-tune:{ .lg .middle } __Settings Management__

    ---

    __File__: `settings.py`

    * Hệ thống cấu hình dựa trên môi trường (`HRC_ENV`).
    * Tự động kiểm chứng (validation) tính hợp lệ của tham số.
    * Phân tách cấu hình theo nhóm: Blockchain, Consensus, Storage, P2P, v.v.

*   :material-key-chain:{ .lg .middle } __Secret Manager__

    ---

    __File__: `secret_manager.py`

    * Truy xuất bí mật (secrets) độc lập với hạ tầng.
    * Hỗ trợ backends: Environment, HashiCorp Vault, AWS Secrets Manager.
    * Tự động fallback linh hoạt.

*   :material-format-list-bulleted-type:{ .lg .middle } __Structured Logging__

    ---

    __File__: `logging.py`

    * Định dạng **Text** cho lập trình viên (màu sắc, dễ đọc).
    * Định dạng **JSON** cho môi trường Production (phù hợp với ELK, Cloud Logging).
    * Hỗ trợ nhúng Request ID để truy vết lỗi.

</div>

---

## Quản lý cấu hình theo môi trường

HieraChain dùng `HRC_ENV` để chọn cấu hình và dùng `ENV` khi `HRC_ENV` không được đặt hoặc để trống. Nếu đặt cả hai, `HRC_ENV` được ưu tiên. Giá trị không phân biệt chữ hoa/thường và bỏ khoảng trắng hai đầu:

| Môi trường | Giá trị được chấp nhận | Đặc điểm chính |
| :--- | :--- | :--- |
| **Development** | `dev`, `development` (mặc định) | Log level DEBUG, mặc định lưu trữ PostgreSQL, cho phép CORS từ mọi nơi. |
| **Production** | `production`, `prod`, `product` | Bật xác thực theo mặc định, HSTS, P2P Strict Trust. |
| **Testing** | `test`, `testing` | Cấu hình cực nhanh, block size nhỏ, mặc định lưu trữ Memory. |

Giá trị môi trường khác, không rỗng, sẽ gây lỗi thay vì chọn development.

---

## Secret Manager (Quản lý Bí mật)

Đây là thành phần quan trọng để bảo vệ các khóa nhạy cảm như `HRC_CLUSTER_SECRET` hoặc `IPFS_ENCRYPTION_KEY`.

### Ví dụ sử dụng trong mã nguồn:
```python
from hierachain.config.secret_manager import SecretManager

sm = SecretManager()
# Tự động lấy từ Vault, AWS hoặc Env tùy theo cấu hình
cluster_key = sm.get_secret("HRC_CLUSTER_SECRET")
```

### Backends hỗ trợ:
1.  **Environment (`env`)**: Mặc định, đọc trực tiếp từ biến môi trường.
2.  **Vault (`vault`)**: Kết nối tới HashiCorp Vault KV v2.
3.  **AWS (`aws`)**: Kết nối tới AWS Secrets Manager.

---

## Ghi log chuẩn hóa (Observability)

Bạn có thể thay đổi định dạng log thông qua biến môi trường `HRC_LOG_FORMAT`:

*   **Dành cho Dev (`text`)**:
    ```text
    INFO  hierachain.api.server  Starting HieraChain Node on localhost:2661...
    ```

*   **Dành cho Ops (`json`)**:
    ```json
    {"timestamp": "2024-03-20T10:00:00", "level": "INFO", "logger": "hierachain.api", "message": "Node started", "request_id": "abc-123"}
    ```

---

## Kiểm chứng cấu hình (Validation)

HieraChain thực hiện kiểm tra cấu hình ngay khi khởi động để tránh các lỗi vận hành tiềm ẩn:

*   **`validate_config()`**: Kiểm tra các giá trị logic (ví dụ: Port phải từ 1-65535, Block size > 0).
*   **`check_security_config()`**: Cảnh báo nếu các thiết lập bảo mật trong môi trường Production không đủ an toàn (ví dụ: Tắt Auth hoặc bật CORS-all).

---

## Liên quan

*   [Biến môi trường (Reference)](../reference/config.md)
*   [Kiến trúc Bảo mật](../architecture/security.md)
*   [Hệ thống Monitoring](./monitoring.md)
