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
    * Trả giá trị mặc định khi bí mật thiếu hoặc không truy xuất được.

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

Module settings nạp `.env` trước khi định nghĩa các thiết lập đọc biến môi trường. Đặt `HRC_ENV_FILE` để nạp tệp dotenv khác; giá trị đã có trong môi trường tiến trình được ưu tiên.

---

## Secret Manager (Quản lý Bí mật)

Đây là thành phần quan trọng để bảo vệ các khóa nhạy cảm như `HRC_CLUSTER_SECRET` hoặc `IPFS_ENCRYPTION_KEY`.

### Ví dụ sử dụng trong mã nguồn:
```python
from hierachain.config.secret_manager import SecretManager

sm = SecretManager()
# Retrieve the configured field
cluster_key = sm.get_secret("HRC_CLUSTER_SECRET")
```

### Backends hỗ trợ:
1.  **Environment (`env`)**: Mặc định, đọc trực tiếp từ biến môi trường.
2.  **Vault (`vault`)**: Kết nối tới HashiCorp Vault KV v2.
3.  **AWS (`aws`)**: Đọc trường chuỗi từ JSON object trong AWS Secrets Manager.

`get_secret(key, default=None)` nhận tên biến môi trường cho `env`, hoặc tên trường cho Vault/AWS. Với AWS, `key` không phải SecretId: đặt `HRC_AWS_SECRET_NAME` thành tên secret hoặc ARN và tùy chọn `HRC_AWS_REGION` (mặc định `us-east-1`). `SecretString` phải là JSON object với trường được yêu cầu có kiểu chuỗi; mỗi lần gọi chỉ trả trường đó, kể cả chuỗi rỗng đã lưu.

Thiếu cấu hình, thiếu trường, trường không phải chuỗi, JSON lỗi, `SecretBinary` và lỗi backend đều trả `default` (hoặc `None`). AWS không fallback sang biến môi trường và không trả toàn bộ JSON object. Log không chứa nội dung bí mật hoặc thông điệp exception. AWS secret cũ lưu dạng chuỗi thuần cần chuyển sang JSON object có trường chuỗi được đặt tên.

Vault trả `default` (hoặc `None`) khi thiếu URL hoặc thông tin xác thực; trong trường hợp đó, nó không đọc biến môi trường cùng tên. Backend không được hỗ trợ sẽ gây `ValueError`. Caller phải gọi `SecretManager` trực tiếp: cấu hình backend không tự thay mọi lời gọi `os.getenv()` trong ứng dụng.

`SecretManager` độc lập với xử lý master key. `HRC_MASTER_KEY_SOURCE=env` vẫn được chấp nhận để tương thích với hành vi secret qua biến môi trường hiện có. Giá trị nguồn khác và mọi `HRC_MASTER_KEY_FILE` không rỗng đều gây lỗi cấu hình vì runtime chưa có master-key provider thay thế. Hãy xóa các thiết lập không được hỗ trợ trước khi khởi động.

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
