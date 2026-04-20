---
title: "CLI Module"
description: "Hướng dẫn sử dụng công cụ dòng lệnh hrc để quản lý chuỗi, sự kiện, node và bảo mật trong HieraChain."
icon: material/console
---

# CLI Module (`hierachain/cli/*`)

## Tổng quan

Module **CLI** cung cấp công cụ dòng lệnh mạnh mẽ mang tên `hrc`, giúp các nhà vận hành và phát triển tương tác nhanh chóng với hệ thống HieraChain mà không cần qua giao diện web hoặc gọi API thủ công. 

Công cụ được xây dựng trên thư viện **Click**, hỗ trợ phân nhóm lệnh logic, gợi ý lệnh (tab-completion) và xử lý tham số chặt chẽ.

### Cách cài đặt & Khởi chạy

Khi cài đặt HieraChain ở chế độ phát triển (`pip install -e .`), lệnh `hrc` sẽ được đăng ký vào hệ thống. Bạn có thể kiểm tra bằng cách:

```bash
hrc --help
```

---

## Nhóm lệnh chính

Hệ thống CLI của HieraChain được chia thành các nhóm chức năng riêng biệt:

### Nhóm lệnh `chain` (Quản lý Chuỗi)

Dùng để khởi tạo và theo dõi cấu trúc phân cấp của các chuỗi.

*   **`hrc chain create`**: Tạo một Sub-Chain mới.

    *   *Tham số*: `[supply_chain|healthcare|finance|manufacturing]`
    *   *Option*: `--name` (Bắt buộc), `--parent` (Mặc định: `main`).

*   **`hrc chain list`**: Liệt kê toàn bộ các chuỗi hiện có và số lượng block của chúng.
*   **`hrc chain submit-proof`**: Gửi bằng chứng mã hóa từ Sub-Chain lên Main Chain để xác thực liên chuỗi.

### Nhóm lệnh `event` (Quản lý Sự kiện)

Dùng để ghi và truy vấn các hoạt động kinh doanh.

*   **`hrc event add`**: Thêm một sự kiện vào chuỗi.

    *   *Tham số*: `<chain_name>`, `[start_operation|complete_operation|quality_check|status_change]`
    *   *Option*: `--entity-id` (Bắt buộc), `--details` (Chuỗi JSON mô tả chi tiết sự kiện).

*   **`hrc event show`**: Hiển thị lịch sử sự kiện trong một chuỗi.

    *   *Option*: `--entity-id` (Lọc theo thực thể cụ thể).

### Nhóm lệnh `key` (Quản lý Khóa)

Dùng để tạo và kiểm tra các cặp khóa Ed25519 cho Validator.

*   **`hrc key generate`**: Tạo cặp khóa mới.

    *   *Option*: `--output` (Mặc định: `validator_key.json`), `--format` (json/hex).

*   **`hrc key show`**: Hiển thị thông tin khóa từ file (che dấu khóa bí mật).
*   **`hrc key verify`**: Kiểm tra tính hợp lệ của cặp khóa (khớp giữa khóa công khai và bí mật).

### Nhóm lệnh `node` (Quản lý Node)

Dùng để vận hành node API.

*   **`hrc node start`**: Khởi chạy server FastAPI.

    *   *Option*: `--host`, `--port`, `--reload` (Dành cho phát triển).

*   **`hrc node init`**: Khởi tạo thư mục dữ liệu và cấu hình mặc định cho node mới.

### Nhóm lệnh `verify` (Kiểm định)

Công cụ dành cho kiểm toán viên để kiểm tra tính toàn vẹn của sổ cái.

*   **`hrc verify chain`**: Kiểm tra cấu trúc liên kết giữa các block (hash chaining).
*   **`hrc verify signatures`**: Kiểm tra toàn bộ chữ ký số của các block và sự kiện trong cơ sở dữ liệu.

    *   *Option*: `--limit` (Chỉ kiểm tra N block gần nhất), `--db` (Đường dẫn cơ sở dữ liệu).

---

## Ví dụ sử dụng thực tế

### 1. Khởi tạo hệ thống và tạo chuỗi cung ứng

```bash
# Khởi tạo dữ liệu node
hrc node init --data-dir ./my_data

# Tạo chuỗi cung ứng linh kiện
hrc chain create supply_chain --name logistics_01 --parent main
```

### 2. Ghi nhận quy trình sản xuất

```bash
# Bắt đầu sản xuất thực thể ITEM-99
hrc event add logistics_01 start_operation --entity-id ITEM-99 --details '{"line": "A1"}'

# Hoàn tất và gửi proof lên Main Chain
hrc chain submit-proof logistics_01
```

### 3. Kiểm định an toàn dữ liệu

```bash
# Kiểm tra 100 block gần nhất xem có bị sửa đổi không
hrc verify signatures --limit 100
```

---

## Cấu hình & Biến môi trường

CLI ưu tiên đọc cấu hình từ file `chains.json` hoặc file được chỉ định qua option toàn cục:

```bash
hrc --config custom_config.json chain list
```

---

## Nguyên tắc thiết kế (Developer Notes)

1.  **Tính nguyên tử**: Mỗi lệnh CLI phải thực hiện một nhiệm vụ duy nhất và trả về Exit Code phù hợp (0: Thành công, >0: Thất bại).
2.  **Bảo mật**: Không bao giờ in khóa bí mật đầy đủ ra màn hình. Sử dụng mặt nạ (masking) khi hiển thị thông tin nhạy cảm.
3.  **Tương thích Scripting**: Kết quả đầu ra của các lệnh `list` hoặc `show` được định dạng để dễ dàng xử lý bằng `grep`, `awk` hoặc `jq`.

---

## Liên quan

*   [API Documentation](./api.md)
*   [Storage Adapters](./adapters.md)
*   [Security & Verify](../security/identity.md)
