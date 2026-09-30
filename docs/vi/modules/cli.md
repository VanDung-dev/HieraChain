---
title: "CLI Module"
description: "Hướng dẫn sử dụng công cụ dòng lệnh hrc để quản lý chuỗi, sự kiện, node và bảo mật trong HieraChain."
icon: material/console
---

# CLI Module (`hierachain/cli/*`)

## Tổng quan

CLI `hrc` cho phép nhà vận hành và lập trình viên quản lý HieraChain từ terminal.

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
*   **`hrc chain submit-proof`**: Hiện trả exit code khác 0 vì registry chain của CLI chỉ nằm trong bộ nhớ. Dùng endpoint REST gửi proof có xác thực và SQL storage bền vững.

### Nhóm lệnh `event` (Quản lý Sự kiện)

Dùng để ghi và truy vấn các hoạt động kinh doanh.

*   **`hrc event add`**: Thêm một sự kiện vào chuỗi.

    *   *Tham số*: `<chain_name>`, `[start_operation|complete_operation|quality_check|status_change]`
    *   *Option*: `--entity-id` (Bắt buộc), `--details` (Chuỗi JSON mô tả chi tiết sự kiện).

*   **`hrc event show`**: Hiển thị lịch sử sự kiện trong một chuỗi.

    *   *Option*: `--entity-id` (Lọc theo thực thể cụ thể).

### Nhóm lệnh `key` (Quản lý Khóa)

Dùng để tạo và kiểm tra các cặp khóa Ed25519 cho Validator.

*   **`hrc key generate`**: Tạo cặp khóa trong file mới với mode `0600` trên hệ POSIX. Không ghi đè file đã có và không in khóa bí mật.

    *   *Option*: `--output` (Mặc định: `validator_key.json`), `--format` (`json` hoặc `hex`). File hex ghi khóa bí mật ở dòng đầu và khóa công khai ở dòng thứ hai.

*   **`hrc key show`**: Hiển thị thông tin khóa từ file (che dấu khóa bí mật).
*   **`hrc key verify`**: Kiểm tra tính hợp lệ của cặp khóa (khớp giữa khóa công khai và bí mật).

### Nhóm lệnh `node` (Quản lý Node)

Dùng để vận hành node API.

*   **`hrc node start`**: Khởi chạy server FastAPI.

    *   *Option*: `--host`, `--port`, `--reload` (Dành cho phát triển).

*   **`hrc node init`**: Khởi tạo thư mục dữ liệu và cấu hình mặc định cho node mới.

### Nhóm lệnh `verify` (Kiểm định)

Công cụ dành cho kiểm toán viên để kiểm tra tính toàn vẹn của sổ cái.

*   **`hrc verify chain`**: Kiểm tra hash block, Merkle root, liên kết chuỗi và chữ ký block bắt buộc bằng khóa tin cậy đã cấu hình. Thiếu block, cơ sở dữ liệu rỗng, thiếu khóa tin cậy hoặc dữ liệu sai đều trả exit code khác 0.
*   **`hrc verify signatures`**: Kiểm tra chữ ký block bắt buộc và các sự kiện đã ký. Sự kiện không ký được đếm là chưa xác minh; sự kiện thiếu dữ liệu ký hoặc có chữ ký sai trả exit code khác 0. Cơ sở dữ liệu rỗng cũng trả exit code khác 0.

Cả hai lệnh nhận `--db` (đường dẫn/URL SQLite hoặc URL PostgreSQL; nếu bỏ qua thì dùng cơ sở dữ liệu đã cấu hình). `verify signatures` còn nhận `--limit` để chỉ kiểm tra N block gần nhất trong từng chain. Sự kiện đã ký cần khóa công khai trong `details.public_key` hoặc `details.sender_public_key` để xác minh.

Các lệnh này kiểm tra block đã lưu. Chain do CLI tạo hiện chỉ nằm trong bộ nhớ và CLI chưa lưu chúng xuống storage.

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

# Gửi proof qua REST API có xác thực và SQL storage bền vững
curl -X POST -H "X-API-Key: $HRC_API_KEY" http://localhost:2661/api/ledger/chains/logistics_01/submit-proof
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
*   [Security & Verify](./security.md)
