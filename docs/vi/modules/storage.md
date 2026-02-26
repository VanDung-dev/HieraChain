---
title: "Storage module"
description: "Module lưu trữ: world state, backend bộ nhớ/SQL, cấu hình và lưu ý hiệu năng — bám sát hierachain/storage/*."
icon: material/database
---

# Storage Module

## Mục đích

Quản lý lưu trữ trạng thái (world state) và lịch sử Block/Event với các backend linh hoạt (in-memory, SQL, Redis tùy cấu hình), cân bằng giữa hiệu năng và độ bền dữ liệu.

## Kiến trúc & khái niệm

* World State: ảnh chụp trạng thái hiện tại của dữ liệu (truy vấn nhanh, cập nhật theo block). File tham chiếu: `hierachain/storage/world_state.py`.
* Backend lưu trữ:

  * In-memory: `hierachain/storage/memory_storage.py` — tốc độ cao, không bền.
  * SQL: `hierachain/storage/sql_backend.py` — bền vững, hỗ trợ SQLite/PostgreSQL.
  * (Tùy chọn) Mô hình dữ liệu ORM: `hierachain/storage/models.py`.

* Cấu hình qua `hierachain/config/settings.py` (DEFAULT_STORAGE_BACKEND, DATABASE_URL, REDIS_* nếu có).

## API công khai (mô tả khái quát)

```yaml
WorldState:
  apply_block(block)
  get_entity(entity_id)
  query(filter)

MemoryStorage/SqlBackend:
  save_block(block)
  load_block(index|hash)
  iterate_blocks(offset, limit)
  save_world_state(snapshot)
  load_world_state()
```

Ví dụ (mô tả):

```python
from hierachain.storage.world_state import WorldState
ws = WorldState(storage=MemoryStorage() | SqlBackend(...))
ws.apply_block(block)
entity = ws.get_entity("PROD-001")
```

## Cấu hình

* `DEFAULT_STORAGE_BACKEND`: memory | redis | sqlite (xem `settings.py`).
* `DATABASE_URL`: ví dụ `sqlite:///hierachain.db` hoặc URL PostgreSQL.
* `WORLD_STATE_CACHE_SIZE`: điều chỉnh cache world state.

## Tính năng & hạn chế

* Tính năng:

  * Lưu trữ block bền (SQL) và truy vấn nhanh (in-memory).
  * Tách world state và lịch sử khối để tối ưu đọc/ghi.

* Hạn chế/ghi chú:

  * In-memory không bền, mất dữ liệu khi khởi động lại.
  * SQL cần migration và quản lý kết nối phù hợp.

## Bảo mật & quyền truy cập

* Kết nối DB nên dùng tài khoản ít quyền và TLS khi khả dụng.
* Dữ liệu nhạy cảm nên mã hoá ở tầng ứng dụng nếu lưu ngoài chuỗi.

## Xử lý lỗi & khắc phục

* Khi DB lỗi kết nối, khuyến nghị cơ chế retry backoff.
* Có thể kết hợp `error_mitigation/journal.py` để phục hồi.

## Hiệu năng

* Batch ghi block để giảm overhead transaction.
* Sử dụng chỉ mục phù hợp cho bảng block/events ở SQL.
* Điều chỉnh kích thước cache theo tải hệ thống.

### Storage Adapters

#### SQLite Adapter

file: `hierrachain/adapters/database/sqlite_adapter.py`

```python
class SQLiteAdapter:
  __init__(db_path="hierachain.db")
  save_block(block); load_block(index); get_all_blocks()
  save_chain_state(chain_name, state); load_chain_state(chain_name)
  execute_query(query, params); close()
```

#### File Storage

file: `hierrachain/adapters/storage/file_storage.py`

```python
class FileStorage:
  __init__(base_path="./data")
  save(key, data); load(key); delete(key); exists(key)
  list_keys(prefix=""); get_size(key)
```

#### Redis Storage

file: `hierrachain/adapters/storage/redis_storage.py`

```python
class RedisStorage:
  __init__(host="localhost", port=6379, db=0)
  set(key, value, ttl=None); get(key); delete(key)
  exists(key); keys(pattern="*")
  push(list_key, value); pop(list_key)
```

## Liên quan

* Config: [Config](../reference/config.md)
* Core: [Core](core.md)
* Error Mitigation: [Error Mitigation](error-mitigation.md)

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * Các tệp mô-đun lưu trữ hiện diện: `hierachain/storage/{sql_backend.py, memory_storage.py, world_state.py, models.py}`.
    * Các tuỳ chọn cấu hình liên quan nằm tại `hierachain/config/settings.py` (DEFAULT_STORAGE_BACKEND, DATABASE_URL, REDIS_*...).

    **DECISION**

    * Tách World State (đọc nhanh) khỏi lịch sử khối (bền), cho phép chọn backend theo môi trường.
    * Khuyến nghị SQL cho production, in-memory cho dev/test.

    **ASSUMPTION**

    * Ứng dụng triển khai migration khi dùng SQL.
    * Hệ thống có cơ chế giám sát/khôi phục khi backend gặp sự cố.

    **INVARIANT**

    * Ghi block phải theo thứ tự và atomically ảnh hưởng tới world state tương ứng.
    * Dữ liệu block đã commit không chỉnh sửa; chỉ append.

    **EDGE CASES**

    * Mất kết nối DB giữa chừng: cần rollback transaction và retry an toàn.
    * Kích thước block lớn gây chậm: cần batch/stream hoặc tăng tài nguyên DB.
