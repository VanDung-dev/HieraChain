---
title: "Core Module"
description: "Kiến trúc nền tảng của HieraChain: Block, Blockchain, Apache Arrow, Caching và Parallel Processing."
icon: material/cube
---

# Core Module (`hierachain/core/*`)

## Tổng quan

Module **Core** là trái tim của HieraChain Ledger, cung cấp các cấu trúc dữ liệu và công cụ xử lý hiệu năng cao nhất. Tại đây, công nghệ **Apache Arrow** được tích hợp sâu để quản lý hàng triệu sự kiện với tốc độ cực nhanh, kết hợp với hệ thống Caching đa tầng và Parallel Engine để đảm bảo khả năng mở rộng (scalability) ở cấp độ doanh nghiệp.

---

## Các thành phần nền tảng

<div class="grid cards" markdown>

*   :material-database-import:{ .lg .middle } __Block & Apache Arrow__

    ---

    __File__: `block.py`

    * Lưu trữ sự kiện theo mô hình cột (columnar storage).
    * Lọc dữ liệu bằng Arrow Compute (nhanh hơn 10-50x so với Python list).
    * Hashing và Merkle Root xác định (deterministic).

*   :material-link-variant:{ .lg .middle } __Blockchain & Safety__

    ---

    __File__: `blockchain.py`

    * Quản lý chuỗi khối, genesis và bộ nhớ đệm (pending pool).
    * **Deadlock Detection**: Tự động phát hiện và xử lý tắc nghẽn khóa (lock contention).
    * Chỉ mục hóa Entity (Entity Indexing) cho truy vấn O(1).

*   :material-flash:{ .lg .middle } __Parallel Engine__

    ---

    __File__: `parallel_engine.py`

    * Xử lý song song dựa trên chính sách (Policy-driven).
    * Worker pools chuyên biệt cho Validation, Indexing và Batch processing.
    * Tự động chia nhỏ dữ liệu (Chunking) để tối ưu bộ nhớ.

*   :material-speedometer:{ .lg .middle } __Advanced Caching__

    ---

    __File__: `caching.py`

    * Caching 3 tầng: Block, Event và Entity.
    * Chính sách loại bỏ: **LRU**, **LFU**, **FIFO**, **TTL**.
    * Tăng tốc truy xuất block lên tới **42 lần**.

</div>

---

## Kiến trúc Block (High-Performance Event Storage)

HieraChain không lưu trữ block theo dạng JSON phẳng thông thường. Mỗi block bên trong là một `pyarrow.Table`.

### Ưu điểm vượt trội:

1.  **Hiệu quả bộ nhớ**: Arrow sử dụng bố cục bộ nhớ tối ưu, giảm overhead của Python objects.
2.  **Truy vấn thần tốc**: Việc tìm kiếm sự kiện theo `entity_id` hoặc `event_type` được thực hiện trực tiếp trong tầng C++ của Arrow.
3.  **Tính nhất quán**: Trường `data` lưu trữ payload gốc dưới dạng Binary, đảm bảo tính toàn vẹn tuyệt đối khi băm.

```python
# Ví dụ truy vấn nhanh trên Block
entity_events = block.get_events_by_entity("PROD-123")
```

---

## Blockchain & Cơ chế Chống Tắc nghẽn (Deadlock Prevention)

HieraChain được thiết kế để chạy trong môi trường đa luồng (multi-threaded). `Blockchain` tích hợp một **Deadlock Detector** để giám sát các thao tác khóa luồng:

*   **Monitor**: Theo dõi thời gian chờ khóa luồng (threshold mặc định 3s).
*   **Safe Lock**: Cơ chế `safe_lock(timeout)` giúp hệ thống không bị treo vô hạn khi xảy ra tranh chấp tài nguyên.
*   **Recovery**: Tự động kích hoạt callback khi phát hiện rủi ro deadlock.

---

## Hệ thống Caching đa tầng

Lớp `BlockchainCacheManager` cung cấp khả năng tăng tốc đáng kinh ngạc cho các thao tác đọc:

| Loại Cache | Chính sách mặc định | Hiệu năng cải thiện |
| :--- | :--- | :--- |
| **Block Cache** | LRU (Least Recently Used) | **~42x** (Truy xuất block theo index) |
| **Event Cache** | TTL (Time To Live) | Tối ưu cho các API truy vấn sự kiện mới nhất. |
| **Entity Cache** | LFU (Least Frequently Used) | **~18.9x** (Truy vết lịch sử một đối tượng) |

---

## Parallel Processing Engine

Để xử lý hàng ngàn sự kiện mỗi giây, Core cung cấp một động cơ xử lý song song thông minh:

*   **Validation Pool**: Chuyên dụng để kiểm tra chữ ký và Merkle root của block.
*   **CPU Intensive Pool**: Sử dụng `ProcessPoolExecutor` để thực hiện các phép tính băm nặng.
*   **Policy-driven**: Hệ thống tự động chọn pool phù hợp dựa trên loại tác vụ (ví dụ: tác vụ `indexing` sẽ có ưu tiên thấp hơn tác vụ `priority`).

---

## Hợp đồng Miền (Domain Contract)

Lớp `DomainContract` cho phép định nghĩa các quy tắc kinh doanh:

*   **Lifecycle**: Quản lý trạng thái từ `DEVELOPMENT` -> `ACTIVE` -> `DEPRECATED`.
*   **Versioning**: Hỗ trợ nâng cấp phiên bản hợp đồng và di trú dữ liệu (migration).
*   **Storage**: Mỗi hợp đồng có không gian lưu trữ key-value riêng biệt.

---

## Liên quan

*   [Hierarchical Architecture](../architecture/hierarchy.md)
*   [Performance Benchmarking](../guides/performance.md)
*   [Security Verifiers](./security.md)
