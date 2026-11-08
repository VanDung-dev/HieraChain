---
title: "Module cấu hình"
description: "Quản lý cấu hình hệ thống, bảo mật bí mật (Secret Management) và định dạng log chuẩn hóa cho HieraChain."
icon: material/cog
---

# Module cấu hình (`hierachain/config/*`)

## Tổng quan

Module Config quản lý các tham số vận hành, khóa bí mật và cấu hình ghi log của HieraChain.

## Các thành phần cốt lõi

<div class="grid cards" markdown>

*   :material-tune:{ .lg .middle } __Quản lý thiết lập__

    ---

    __Tệp__: `settings.py`

    * Hệ thống cấu hình dựa trên môi trường (`HRC_ENV`).
    * Các helper cần gọi trực tiếp để kiểm tra tham số và lấy cảnh báo bảo mật.
    * Phân tách cấu hình theo nhóm: Blockchain, Consensus, Storage, P2P, v.v.

*   :material-format-list-bulleted-type:{ .lg .middle } __Ghi log có cấu trúc__

    ---

    __Tệp__: `logging.py`

    * Định dạng Text cho lập trình viên (màu sắc, dễ đọc).
    * Định dạng JSON cho môi trường Production (phù hợp với ELK, Cloud Logging).
    * Hỗ trợ nhúng Request ID để truy vết lỗi.

</div>

## Quản lý cấu hình theo môi trường

HieraChain dùng `HRC_ENV` để chọn cấu hình và dùng `ENV` khi `HRC_ENV` không được đặt hoặc để trống. Nếu đặt cả hai, `HRC_ENV` được ưu tiên. Giá trị không phân biệt chữ hoa/thường và bỏ khoảng trắng hai đầu:

| Môi trường | Giá trị được chấp nhận | Đặc điểm chính |
| :--- | :--- | :--- |
| Development | `dev`, `development` (mặc định) | Log level DEBUG, mặc định lưu trữ PostgreSQL, cho phép CORS từ mọi nơi. |
| Production | `production`, `prod`, `product` | Bắt buộc xác thực; mặc định lưu trữ PostgreSQL. |
| Testing | `test`, `testing` | Cấu hình cực nhanh, block size nhỏ, mặc định lưu trữ Memory. |

Giá trị môi trường khác, không rỗng, sẽ gây lỗi thay vì chọn development.

Module settings nạp `.env` trước khi định nghĩa các thiết lập đọc biến môi trường. Đặt `HRC_ENV_FILE` để nạp tệp dotenv khác; giá trị đã có trong môi trường tiến trình được ưu tiên.

## Bí mật (Secrets)

Secret được cung cấp qua biến môi trường hoặc hệ thống quản lý secret của nền tảng (Kubernetes Secret, Vault, cloud secret manager). Package đọc `HRC_MASTER_KEY_SOURCE`; chỉ chấp nhận `env`. Giá trị nguồn khác, hoặc `HRC_MASTER_KEY_FILE` khác rỗng, sẽ gây lỗi cấu hình vì runtime không có master-key provider thay thế. Hãy xóa các thiết lập không được hỗ trợ trước khi khởi động.

## Ghi log chuẩn hóa (Observability)

Bạn có thể thay đổi định dạng log thông qua biến môi trường `HRC_LOG_FORMAT`:

*   Dành cho Dev (`text`):
    ```text
    INFO  hierachain.api.server  Starting HieraChain Node on localhost:2661...
    ```

*   Dành cho Ops (`json`):
    ```json
    {"timestamp": "2024-03-20T10:00:00", "level": "INFO", "logger": "hierachain.api", "message": "Node started", "request_id": "abc-123"}
    ```

## Kiểm chứng cấu hình (Validation)

Luồng khởi động API và CLI tự thực hiện kiểm tra. Khởi động từ chối môi trường không hợp lệ, nguồn master key chưa được hỗ trợ và cấu hình xác thực hoặc lưu trữ production không hợp lệ.

## Liên quan

*   [Biến môi trường (Reference)](../reference/config.md)
*   [Kiến trúc Bảo mật](../architecture/security.md)
*   [Network](./network.md)
