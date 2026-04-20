---
title: "Adapters Module"
description: "Các adapter lưu trữ/cơ sở dữ liệu: SQLite, File (Parquet/Arrow), Redis — Tích hợp IO linh hoạt theo mô hình Adapter Pattern."
icon: material/vector-polyline
---

# Adapters Module (`hierachain/adapters/*`)

## 1. Tổng quan

Module **Adapters** đóng vai trò là lớp trừu tượng hóa (Abstraction Layer) cho việc lưu trữ dữ liệu trong HieraChain. Thay vì ràng buộc logic nghiệp vụ vào một loại cơ sở dữ liệu cụ thể, HieraChain sử dụng **Adapter Pattern** để cho phép thay đổi backend lưu trữ một cách linh hoạt mà không cần sửa đổi mã nguồn cốt lõi.

### Vai trò chính

* **Chuẩn hóa IO**: Cung cấp giao diện thống nhất để lưu trữ block, event, metadata và proof.
* **Linh hoạt triển khai**: Hỗ trợ từ môi trường phát triển (SQLite/File) đến môi trường sản xuất hiệu năng cao (Redis/Parquet).
* **Tối ưu hóa truy vấn**: Mỗi adapter được thiết kế để tối ưu cho một kiểu truy vấn nhất định (ví dụ: File adapter tối ưu cho việc truy vết entity trên quy mô lớn).

---

## 2. Các Adapter hiện có

HieraChain cung cấp ba loại adapter chính, chia thành hai nhóm: `database` và `storage`.

### 2.1 SQLite Database Adapter (`adapters/database/sqlite_adapter.py`)

Sử dụng SQLite làm backend cho các hệ thống yêu cầu tính toàn vẹn dữ liệu quan hệ và truy vấn SQL linh hoạt.

* **Công nghệ**: SQLite3.
* **Cấu trúc Schema**:

    * `chains`: Lưu thông tin định danh và loại chuỗi (Main/Sub).
    * `blocks`: Lưu trữ header của block, mã băm và metadata.
    * `events`: Lưu chi tiết các sự kiện nghiệp vụ dưới dạng JSON.
    * `proofs`: Lưu vết các bằng chứng cross-chain giữa Sub-Chain và Main Chain.

* **Ưu điểm**: Hỗ trợ ACID, quản lý quan hệ giữa các thực thể tốt, dễ dàng sao lưu (single file).
* **Tối ưu**: Có sẵn các chỉ mục (indexes) trên `entity_id`, `event_type`, và `timestamp`.

### 2.2 File Storage Adapter (`adapters/storage/file_storage.py`)

Adapter hiệu năng cao dành cho dữ liệu lớn, sử dụng định dạng file chuyên dụng cho phân tích.

* **Công nghệ**: **Apache Parquet** và **PyArrow**.
* **Cấu trúc lưu trữ**:

    * `blocks/`: Lưu trữ block dưới dạng file `.parquet` nén (Zstd). Mỗi block là một bảng Arrow.
    * `events/`: Duy trì bộ chỉ mục sự kiện (Event Index) cho phép truy tìm (tracing) cực nhanh.
    * `chains/`: Lưu metadata chuỗi dưới dạng JSON.

* **Ưu điểm**: Tốc độ đọc/ghi cực nhanh, nén dữ liệu tốt, hỗ trợ **Column Pruning** (chỉ đọc các cột cần thiết).
* **Tính năng đặc biệt**:

    * `BatchBlockWriter`: Buffer dữ liệu để ghi hàng loạt, giảm thiểu I/O overhead.
    * `get_entity_events_optimized`: Sử dụng Arrow Dataset để quét dữ liệu trên nhiều file block đồng thời.

### 2.3 Redis Storage Adapter (`adapters/storage/redis_storage.py`)

Phù hợp cho các node yêu cầu phản hồi thời gian thực (Real-time) và truy cập dữ liệu nóng (Hot data).

* **Công nghệ**: Redis (In-memory data structure).
* **Cấu trúc dữ liệu**:

    * **Hashes**: Lưu trữ block và metadata.
    * **Sorted Sets (ZSET)**: Lưu chỉ mục block theo index và sự kiện của entity theo timestamp.
    * **Sets**: Quản lý danh sách các chuỗi và thực thể duy nhất.

* **Ưu điểm**: Độ trễ (latency) cực thấp, hỗ trợ đếm số liệu thống kê (statistics) theo thời gian thực.
* **Sử dụng**: Thường được dùng làm cache hoặc database chính cho các node giao dịch tần suất cao.

---

## 3. So sánh các Adapter

| Đặc điểm | SQLiteAdapter | FileStorageAdapter | RedisStorageAdapter |
| :--- | :--- | :--- | :--- |
| **Loại lưu trữ** | Cơ sở dữ liệu quan hệ | File hệ thống (Parquet) | Bộ nhớ (In-memory) |
| **Phù hợp nhất** | ERP Integration, Audit | Big Data, Phân tích truy vết | Real-time Dashboard, High-speed Node |
| **Tốc độ ghi** | Trung bình | Rất nhanh (với Batch) | Cực nhanh |
| **Tốc độ truy vấn** | Nhanh (SQL) | Cực nhanh (Analytical) | Nhanh nhất (Point lookup) |
| **Tính bền vững** | Cao (ACID) | Cao (File-based) | Phụ thuộc cấu hình Redis RDB/AOF |
| **Dependencies** | Không (Built-in Python) | `pyarrow` | `redis-py` |

---

## 4. Hướng dẫn sử dụng

### Cấu hình qua Settings

Bạn có thể chọn adapter mặc định thông qua biến môi trường hoặc file cấu hình:

```bash
# Chọn backend lưu trữ
export HRC_STORAGE_BACKEND=sqlite  # Hoặc "redis", "file"
export DATABASE_URL="sqlite:///my_ledger.db"
```

### Sử dụng trong mã nguồn

#### Sử dụng SQLite

```python
from hierachain.adapters.database.sqlite_adapter import SQLiteAdapter

adapter = SQLiteAdapter("data/ledger.db")
# Lấy thống kê chuỗi
stats = adapter.get_chain_statistics("supply_chain_v1")
print(f"Tổng số block: {stats['total_blocks']}")
```

#### Sử dụng File (Parquet)

```python
from hierachain.adapters.storage.file_storage import FileStorageAdapter, BatchBlockWriter

storage = FileStorageAdapter(storage_path="./blockchain_data")

# Ghi hàng loạt blocks để tối ưu hiệu năng
with BatchBlockWriter(storage, "main_chain", batch_size=100) as writer:
    for block in new_blocks:
        writer.add(block)
```

---

## 5. Bảo mật & An toàn dữ liệu

### Chống tấn công Path Traversal (CWE-22)

Tất cả các adapter đều thực hiện kiểm tra nghiêm ngặt tên chuỗi (chain name) và đường dẫn:

* Chỉ cho phép ký tự alphanumeric, dấu gạch dưới `_` và gạch ngang `-`.
* Ngăn chặn các ký tự điều hướng như `..` để đảm bảo dữ liệu không bị ghi đè ngoài thư mục chỉ định.

### Secure Logging

Việc ghi log trong các adapter được thực hiện qua `SecureLogger`, đảm bảo không lộ các thông tin nhạy cảm của doanh nghiệp trong file log hệ thống.

---

## 6. Xử lý lỗi & Bảo trì

* **Cleanup**: Cả ba adapter đều hỗ trợ phương thức `cleanup_old_data(days_to_keep)` để tự động dọn dẹp các khối dữ liệu cũ hoặc log không cần thiết theo chính sách lưu trữ của doanh nghiệp.
* **Data Integrity**: Khi sử dụng `FileStorageAdapter`, mã băm (hash) của block được lưu trực tiếp trong metadata của file Parquet, cho phép kiểm tra tính toàn vẹn ngay khi load file mà không cần đọc toàn bộ nội dung.

---

## Liên quan

* [Core Concepts - Blockchain](../architecture.md)
* [Storage Module](./storage.md)
* [Security Overview](./security.md)
