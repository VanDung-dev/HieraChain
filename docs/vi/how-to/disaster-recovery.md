---
title: Khôi phục sau thảm họa
description: Chi tiết cơ chế TransactionJournal, RollbackManager và KeyBackupManager để xử lý gián đoạn và khôi phục hệ thống HieraChain.
icon: material/backup-restore
---

# Khôi phục sau thảm họa

HieraChain được thiết kế với tiêu chí ưu tiên cao nhất cho tính bền vững (Durability) và tính không thể đảo ngược hệ thống. Tài liệu này hướng dẫn cách hệ thống tự động xử lý và cách vận hành quy trình khôi phục khi xảy ra gián đoạn hoặc thảm họa máy chủ.

---

## 1. Cơ chế Transaction Journaling (Replay Data)

Nhằm chống lại việc mất dữ liệu do crash ứng dụng, mất điện, hoặc hệ điều hành bị tắt đột ngột, HieraChain triển khai một module gọi là **`TransactionJournal`** trước khi sự kiện (event) được đưa vào Ordering Service để xử lý.

### Cách thức hoạt động

- **Storage Format:** Các log journal được tuần tự hóa theo định dạng **Apache Arrow RecordBatch**, cho phép tốc độ đọc/ghi cực nhanh và bảo toàn cấu trúc schema.
- **Length-Prefixed Framing:** Tập tin append-only ghi theo cấu trúc `[Độ dài 4 Bytes][Dữ liệu Batch]`.
- **Sync & Fsync:** Mọi thao tác log sự kiện đều được gọi `os.fsync()` đảm bảo disk I/O thực sự ghi xuống phần cứng trước khi phản hồi thành công.

### Hướng dẫn Khôi phục (Replay)

Khi Node khởi động lại sau một sự cố không mong muốn (Crash), hệ thống tự động kiểm tra thư mục Log (mặc định `data/journal/current.log`). Node sẽ tự gọi vòng lặp qua phương thức `replay()` để phát lại chuỗi RecordBatch và khôi phục mảng sự kiện vào bộ nhớ (MemPool hoặc World State) một cách đầy đủ.

---

## 2. Quản lý Rollback State (`RollbackManager`)

Trong trường hợp rủi cấu ro lớn hơn — như dữ liệu phân vùng hoặc nâng cấp (upgrade) nhầm lẫn — hệ thống cho phép "lùi" toàn bộ trạng thái về một mốc an toàn.

`RollbackManager` sẽ lưu lại các điểm trạng thái hệ thống:

- **Configuration State**: Cấu hình file YAML, JSON, PY.
- **Chain State**: Khối lượng block và Hash gần nhất.
- **Consensus State**: View Number, Node ID của Leader hiện tại.
- **Storage State**: Snapshot của World State.

### Quy trình Rollback

1. Lấy danh sách snapshot bằng `manager.get_snapshots()`.
2. Hệ thống kiểm tra **Integrity Hash (Hàm băm nguyên vẹn)** của snapshot. Snapshot không nguyên vẹn hoặc quá cũ (hơn 72 giờ) có khả năng bị từ chối nếu không bật cờ `force=True`.
3. Thực thi hàm `rollback_to_snapshot(snapshot_id)`. Nó sẽ khôi phục từng phần của `Configuration` và `Chain State`.

---

## 3. Sao lưu và Khôi phục Khóa (`KeyBackupManager`)

Bảo vệ cặp quá ký ECDSA/Ed25519 là nhiệm vụ quan trọng. `KeyBackupManager` tự động sao lưu an toàn khi hệ thống tạo Key mới:

- **Bảo mật AES-256-GCM**: Key Public / Private của Node được thu thập, mã hóa GCM (Authenticate Encryption) với Key Master được cấp bởi Admin.
- **Xác minh toàn vẹn (Integrity)**: Sử dụng cấu hình băm `SHA-512` kết hợp `HMAC` để đối chiếu mỗi khi khôi phục.
- **Phân phối đa vị trí (Multi-location)**: Mã băm và file `.enc` được hệ thống "copy" phân tán ra nhiều đường dẫn `locations` nhằm chống Single Point of Failure (SPOF).

### Khôi phục khi cần thiết

Sử dụng `restore_keys(backup_id)`. Manger sẽ đọc luồng IO, xác minh checksum `SHA-512`, giải mã GCM, và ngay lập tức tiêm vào tiến trình Node mà không cần stop hệ thống. Định dạng cặp khóa luôn được `_validate_keys` xác minh để tránh lỗi load key hỏng.

---

## 4. Xử lý Lỗi Mạng và Suy Trái (BFT Consensus Recovery)

Cụm BFT của HieraChain (với thuật toán dựa trên View Change) tự chứa các đặc tính "Tự phục hồi" (Self-recovery) đối với các sự cố liên lạc:

- **Sự cố Leader bị Node-down**: Nếu Leader gặp crash, timeout (không broadcast block mới đúng hạn), các Validators sẽ gửi tin nhắn kháng nghị. Khi đạt trên `2f + 1` tin nhắn kháng nghị, hệ thống khởi tạo **View Change**, chuyển qua Leader tiếp theo (ví dụ: `Leader_ID = View_Number % Total_Nodes`).
- **Sự cố Network Partition (Chia cắt mạng)**: Nếu mạng bị chia làm 2 mảnh, mảnh không chiếm đa số (***< 2f + 1***) sẽ tự động ngừng (Halt). Mảng lớn hơn (trên 66% số node) tiếp tục giao dịch. Khi kết nối khôi phục, mảnh nhỏ hơn tự động gọi API P2P để đồng bộ (Sync Blocks) với nhánh dài nhất.

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * Mã nguồn tài liệu tham chiếu: `hierachain/*` (Python >= 3.10 theo `pyproject.toml`).
    * Script CLI: `hrc` (định nghĩa tại `[project.scripts]` trong `pyproject.toml`).
    * API server: `hierachain/api/server.py` (có thể chạy bằng `python -m hierachain.api.server`).

    **DECISION**

    * Dùng Markdown, tách rõ các khối FACT / DECISION / ASSUMPTION / INVARIANT / EDGE CASES.
    * Tổ chức nội dung theo khung chuẩn thống nhất.

    **ASSUMPTION**

    * Người đọc đã cài Python 3.10+ và có quyền truy cập internet để cài dependencies.
    * Môi trường phát triển sử dụng `venv` hoặc công cụ tương đương.

    **INVARIANT**

    * FACT phải bám sát mã nguồn hiện tại (tên file, chữ ký API, đường dẫn).
    * Không pha trộn nội dung tiếp thị trong tài liệu kỹ thuật.

    **EDGE CASES**

    * Khác biệt shell giữa Windows (PowerShell) và Linux/macOS (bash) khi kích hoạt venv.
    * Mạng nội bộ hạn chế có thể ảnh hưởng quá trình cài gói.
