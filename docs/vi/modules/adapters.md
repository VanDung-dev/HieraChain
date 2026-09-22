---
title: "Adapters Module"
description: "Các adapter cơ sở dữ liệu SQLite, PostgreSQL và Redis trong hierachain/adapters/database/."
icon: material/vector-polyline
---

# Adapters Module (`hierachain/adapters/*`)

## 1. Tổng quan

Module `adapters` cung cấp lớp lưu trữ bền vững cho HieraChain. Hệ thống cốt lõi định nghĩa giao diện chung cho các thao tác cơ sở dữ liệu, cho phép quản trị viên lựa chọn hoặc chuyển đổi cơ sở dữ liệu mà không cần thay đổi logic nghiệp vụ hay mã đồng thuận.

### Vai trò chính

* Chuẩn hóa thao tác đọc và ghi dữ liệu cho chuỗi, khối, sự kiện, bằng chứng và trạng thái thực thể.
* Hỗ trợ nhiều môi trường, với PostgreSQL là mặc định và SQLite là backend fallback cục bộ.
* Đảm bảo phân lập dữ liệu và kiểm tra tính hợp lệ của đầu vào trên các hệ quản trị cơ sở dữ liệu.

## 2. Các adapter cơ sở dữ liệu hiện có

Toàn bộ adapter lưu trữ nằm tại `hierachain/adapters/database/`.

### 2.1 SQLite Database Adapter (`sqlite_adapter.py`)

Adapter fallback khi PostgreSQL không khả dụng, đồng thời là lựa chọn tường minh cho thiết lập một node nhẹ.

* Công nghệ: SQLite3 qua `sqlite3` và `hierachain/adapters/database/base/sql_base.py`.
* Lược đồ dữ liệu: Khởi tạo qua `sqlite_schema.py`, tạo các bảng `chains`, `blocks`, `events`, `proofs` và `chain_state`.
* Điểm mạnh: Không phụ thuộc dịch vụ ngoài, đảm bảo ACID, sao lưu dễ dàng bằng file đơn.
* Chỉ mục: Tạo sẵn trên `entity_id`, `event_type`, `block_number` và `timestamp`.

### 2.2 PostgreSQL Database Adapter (`postgres_adapter.py`)

Adapter cơ sở dữ liệu quan hệ cho các triển khai đa node và doanh nghiệp.

* Công nghệ: PostgreSQL với cơ chế connection pooling.
* Lược đồ dữ liệu: Khởi tạo qua `postgres_schema.py` với cấu trúc tương thích hoàn toàn với SQLite.
* Điểm mạnh: Khả năng ghi đồng thời lớn, quản lý kết nối hiệu quả, hỗ trợ công cụ sao lưu doanh nghiệp.
* Tính năng truy vấn: Tối ưu cho phân vùng dữ liệu và quét chỉ mục cho các bản ghi kiểm toán dung lượng lớn.

### 2.3 Redis Database Adapter (`redis_adapter.py`)

Adapter trên bộ nhớ phục vụ đọc dữ liệu tốc độ cao và tra cứu trạng thái thực thể tức thời.

* Công nghệ: Redis qua thư viện `redis-py`.
* Cấu trúc dữ liệu: Hash lưu block header và dữ liệu sự kiện, sorted set lưu thứ tự sự kiện theo thời gian và dải chỉ mục khối, set lưu danh sách chuỗi duy nhất.
* Điểm mạnh: Độ trễ cực thấp khi tra cứu theo khóa và truy vết nhanh thực thể.
* Tính bền vững: Phụ thuộc vào cấu hình snapshot RDB và nhật ký AOF của Redis.

## 3. So sánh các adapter

| Đặc điểm | SQLiteAdapter | PostgreSQLAdapter | RedisAdapter |
| :--- | :--- | :--- | :--- |
| Loại lưu trữ | File quan hệ | Máy chủ quan hệ | Key-value trong bộ nhớ |
| Môi trường phù hợp | Phát triển, kiểm thử, node biên | Môi trường sản xuất, cụm đa node | Truy vấn trạng thái độ trễ thấp, cache |
| Độ trễ ghi | Thấp | Thấp đến trung bình | Rất thấp |
| Độ linh hoạt truy vấn | Toàn bộ SQL | Toàn bộ SQL | Tra cứu khóa và chỉ mục |
| Tính bền vững | ACID trên file cục bộ | ACID trên máy chủ doanh nghiệp | Snapshot RDB / AOF |
| Dịch vụ bên ngoài | Không | PostgreSQL 13+ | Redis 6+ |

## 4. Cấu hình và sử dụng

### Cấu hình qua settings

Thiết lập backend lưu trữ bằng biến môi trường:

```bash
# Các backend hỗ trợ: sqlite, postgres, redis, memory
export HRC_STORAGE_BACKEND=sqlite
export DATABASE_URL="sqlite:///data/ledger.db"

# Hoặc đối với PostgreSQL
# export HRC_STORAGE_BACKEND=postgres
# export DATABASE_URL="postgresql://user:pass@localhost:5432/hierachain"
```

### Sử dụng trong mã nguồn

#### Sử dụng SQLite

```python
from hierachain.adapters.database.sqlite_adapter import SQLiteAdapter

adapter = SQLiteAdapter("data/ledger.db")
stats = adapter.get_chain_statistics("supply_chain_ledger")
print(f"Total blocks: {stats['total_blocks']}")
```

#### Sử dụng PostgreSQL

```python
from hierachain.adapters.database.postgres_adapter import PostgreSQLAdapter

adapter = PostgreSQLAdapter(connection_string="postgresql://user:pass@localhost:5432/hierachain")
stats = adapter.get_chain_statistics("supply_chain_ledger")
print(f"Total blocks: {stats['total_blocks']}")
```

#### Sử dụng Redis

```python
from hierachain.adapters.database.redis_adapter import RedisAdapter

adapter = RedisAdapter(host="localhost", port=6379, db=0)
stats = adapter.get_chain_statistics("supply_chain_ledger")
print(f"Total blocks: {stats['total_blocks']}")
```

## 5. Bảo mật và xác thực

### Ngăn chặn lỗi Path Traversal

Các adapter kiểm tra nghiêm ngặt đường dẫn và tên chuỗi:

* Tên chỉ cho phép ký tự chữ cái, chữ số, gạch dưới `_` và gạch ngang `-`.
* Các ký tự duyệt thư mục (`..`, `/`, `\`) bị từ chối trước khi thao tác trên hệ thống tệp hoặc truy vấn.

### Ghi log an toàn

Adapter ghi nhận truy vấn và sự kiện kết nối qua `SecureLogger`, tự động ẩn thông tin đăng nhập, token xác thực và dữ liệu nghiệp vụ nhạy cảm.

## 6. Bảo trì và lưu giữ dữ liệu

* Dọn dẹp dữ liệu: Các adapter quan hệ hỗ trợ xóa các bản ghi sự kiện cũ vượt quá ngưỡng cấu hình qua `HRC_SQL_RETENTION_DAYS`.
* Nhật ký và journal: Nhật ký nhị phân và dữ liệu kiểm toán lỗi sử dụng `hierachain/core/parquet_log.py` và `hierachain/error_mitigation/journal.py`, tách rời việc lưu trữ chuỗi khỏi hệ thống log chẩn đoán.

## Liên quan

* [Storage Module](./storage.md)
* [Tham chiếu cấu hình](../reference/config.md)
* [Tổng quan bảo mật](./security.md)
