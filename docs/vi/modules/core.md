---
title: "Core Module"
description: "Các cấu trúc nền tảng của sổ cái: Block, Blockchain, Merkle Tree và hệ thống Caching đa tầng."
icon: material/cube
---

# Core Module (`hierachain/core/*`)

## 1. Tổng quan

Module `core` chứa các cấu trúc dữ liệu nền tảng của sổ cái. Khối lưu trữ các sự kiện trong bảng Apache Arrow giúp lọc dữ liệu trong bộ nhớ với tốc độ cao và tính toán mã băm xác định. Cây Merkle mật mã cung cấp bằng chứng chứng minh sự kiện có mặt trong khối, kết hợp với bộ nhớ đệm đa tầng tăng tốc độ tra cứu khối, sự kiện và thực thể.

## 2. Các thành phần nền tảng

Toàn bộ thành phần cốt lõi nằm tại `hierachain/core/`.

### 2.1 Khối (`block.py`)

* Lưu trữ bản ghi sự kiện trong một `pyarrow.Table`.
* Truy vấn các trường sự kiện qua biểu thức tính toán của Arrow thay vì vòng lặp Python.
* Tính toán mã băm khối và Merkle root xác định.

### 2.2 Chuỗi khối (`blockchain.py`)

* Quản lý trạng thái chuỗi, khởi tạo khối nguyên thủy (genesis) và hàng đợi sự kiện đang chờ.
* Thực thi cơ chế khóa an toàn đa luồng kèm phát hiện bế tắc (deadlock).
* Duy trì chỉ mục thực thể phục vụ tra cứu lịch sử sự kiện nhanh chóng.

### 2.3 Cây Merkle (`merkle_tree.py`)

* Xây dựng cây Merkle nhị phân từ mã băm các sự kiện.
* Tạo bằng chứng bao hàm (inclusion proof) phục vụ kiểm toán.
* Xác thực Merkle root giữa các tầng chuỗi trong kiến trúc phân cấp.

### 2.4 Bộ nhớ đệm (`cache.py`)

* Cung cấp bộ nhớ đệm trong RAM với các chính sách dọn dẹp LRU, LFU, FIFO và TTL.
* `KeyManager` sử dụng bộ nhớ đệm này cho các tra cứu khóa và quyền.

## 3. Cấu trúc bộ nhớ và lưu trữ của Block

Mỗi đối tượng `Block` đóng gói một bảng Arrow cùng metadata có cấu trúc:

1. Bố cục nhị phân gọn gàng giảm tải bộ nhớ cho các đối tượng Python.
2. Thao tác lọc theo `entity_id` và `event` chạy trực tiếp trên nhân C++ của Arrow.
3. Dữ liệu nhị phân tuần tự hóa bảo đảm tính ổn định của mã băm trên mọi nền tảng.

```python
# Query events by entity on a Block instance
entity_events = block.get_events_by_entity("PROD-123")
```

## 4. An toàn đa luồng và cơ chế khóa

Lớp `Blockchain` điều phối truy cập đồng thời thông qua cơ chế khóa có giới hạn thời gian:

* Theo dõi thời gian giữ khóa với ngưỡng cấu hình linh hoạt.
* Hàm `safe_lock(timeout)` ngăn chặn tình trạng treo luồng khi xảy ra tranh chấp ghi đồng thời.
* Cơ chế callback thông báo cảnh báo tắc nghẽn lên tầng giám sát hệ thống.

## 5. Thực thi đồng thời

Các tác vụ xác thực mật mã và đồng bộ liên chuỗi chạy đồng thời thông qua các worker `ThreadPoolExecutor` do môi trường thực thi quản lý. Quá trình băm và kiểm tra chữ ký được mở rộng trên nhiều lõi CPU trong khi vẫn bảo toàn thứ tự khối tuần tự.

## Liên quan

* [Kiến trúc phân cấp](../architecture/hierarchy.md)
* [Storage Module](./storage.md)
* [Tổng quan bảo mật](./security.md)
