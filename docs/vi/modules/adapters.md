---
title: "Adapters module"
description: "Các adapter lưu trữ/cơ sở dữ liệu: SQLite, File, Redis — tích hợp IO theo mô hình Adapter Pattern."
icon: material/vector-polyline
---

# Adapters

## Mục đích

Chuẩn hóa điểm nối (IO boundary) giữa HieraChain và hệ thống lưu trữ/cơ sở dữ liệu bên dưới thông qua các adapter có thể hoán đổi. Giúp triển khai linh hoạt tùy môi trường: file hệ thống, Redis, hoặc SQLite.

## Kiến trúc & khái niệm

* Adapter Pattern: Mỗi backend hiện thực giao diện đọc/ghi thống nhất cho dữ liệu/khối/trạng thái.
* Phân loại:

  * Database: `adapters/database/sqlite_adapter.py` — truy cập kho SQLite (và có thể mở rộng RDBMS khác).
  * Storage:

    * `adapters/storage/file_storage.py` — lưu/đọc tệp khối, snapshot, đính kèm.
    * `adapters/storage/redis_storage.py` — lưu đệm/tra cứu nhanh qua Redis.

* Ràng buộc: Các adapter không tự áp đặt logic đồng thuận hay bảo mật; chúng triển khai thao tác IO theo hợp đồng đã định.

## API công khai (Public API)

Mức mô tả (rút gọn, tham khảo tên lớp/hàm trong mã nguồn):

* Khởi tạo adapter với cấu hình (đường dẫn DB/file, host/port Redis, timeouts...).
* Giao diện đọc/ghi bản ghi/block/snapshot theo khóa/ID.
* Quản lý vòng đời tài nguyên: mở/kết nối → dùng → đóng/flush.

Ví dụ mô tả (giả định):

```python
# Pseudocode
from hierachain.adapters.storage import file_storage
store = file_storage.FileStorage(root_dir="./data")
store.write("blocks/0001.json", b"{...}")
data = store.read("blocks/0001.json")
```

## Cấu hình

* Tham khảo `hierachain/config/settings.py`:
  * `DEFAULT_STORAGE_BACKEND`: memory | redis | sqlite
  * Thông số Redis: `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`
  * `DATABASE_URL`: ví dụ `sqlite:///hierachain.db`
* Biến môi trường tương ứng có thể ghi đè giá trị mặc định (xem trang Reference/Config).

## Tính năng & hạn chế

* Tính năng:

  * Thay thế backend nhanh chóng mà không đổi luồng nghiệp vụ.
  * Kết hợp nhiều adapter: Redis (cache) + SQLite/File (bền vững).

* Hạn chế:

  * File/SQLite phù hợp môi trường đơn nút; môi trường phân tán cần backend đồng bộ/HA.

## Bảo mật & quyền truy cập

* Adapter bản thân không triển khai xác thực/ủy quyền; ràng buộc bảo mật thực thi ở tầng `security/*` và `api/*`.
* Đường dẫn file và thông tin kết nối cần bảo vệ qua biến môi trường/secret manager.

## Xử lý lỗi & khắc phục

* Nên kết hợp với `error_mitigation/*` (journal, rollback, recovery) để đảm bảo phục hồi khi IO lỗi.
* Cơ chế retry/backoff khi kết nối Redis/DB thất bại (tùy adapter).

## Hiệu năng

* Redis cho tra cứu nóng (hot path) và cache L1/L2.
* File/SQLite phù hợp throughput trung bình; quy mô lớn cân nhắc RDBMS/NoSQL chuyên dụng.

## Liên quan

* Storage module: [Storage](storage.md)
* Config (tham chiếu): [Config](../reference/config.md)
* Error Mitigation: [Error Mitigation](error-mitigation.md)

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * Có các tệp adapter trong `hierachain/adapters/`: 
        * `database/sqlite_adapter.py`
        * `storage/file_storage.py`
        * `storage/redis_storage.py`

    * Cấu hình liên quan nằm ở `hierachain/config/settings.py` (DATABASE_URL, REDIS_*).

    **DECISION**

    * Sử dụng Adapter Pattern để cô lập lớp IO khỏi logic chuỗi và đồng thuận.
    * Ưu tiên cấu hình qua biến môi trường để triển khai linh hoạt.

    **ASSUMPTION**

    * Môi trường phát triển sử dụng SQLite/File; môi trường staging/production có thể dùng Redis/RDBMS.
    * Quyền truy cập file hệ thống/Redis/DB đã được cấp.

    **INVARIANT**

    * Hợp đồng đọc/ghi của adapter phải ổn định (không thay đổi hành vi ở cùng phiên bản).
    * Dữ liệu ghi ra phải toàn vẹn; lỗi ghi phải được báo hiệu để tầng trên quyết định rollback.

    **EDGE CASES**

    * Mất quyền ghi thư mục dữ liệu → thao tác lưu file thất bại.
    * Redis không khả dụng → cần fallback/bật chế độ memory.
    * Lỗi khóa/tập tin bị khóa (file lock) trên Windows.
