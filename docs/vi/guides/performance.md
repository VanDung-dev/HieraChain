---
title: "Hiệu năng"
description: "Hướng dẫn tối ưu hiệu năng: cache L1/L2, Apache Arrow, batch size, song song hoá, mẹo benchmark."
icon: material/speedometer
---

# Hướng dẫn hiệu năng

## Mục đích

Đưa ra khuyến nghị để đạt hiệu năng tốt khi lưu trữ/xử lý sự kiện và gửi proof.

## Nguyên tắc

* Tối ưu cấu trúc dữ liệu: sử dụng Arrow cho lưu trữ cột.
* Giảm chi phí IO/serialize: nhóm sự kiện theo lô, tránh payload nhị phân lớn trong `data`.
* Dùng cache hợp lý: L1 trong bộ nhớ, L2 bền vững nếu cần.

## Thiết lập liên quan (trích `config/settings.py`)

* `ADVANCED_CACHING_ENABLED`: bật cache nâng cao.
* `BLOCK_CACHE_SIZE`, `EVENT_CACHE_SIZE`, `ENTITY_CACHE_SIZE`: kích thước cache.
* Chính sách: `BLOCK_CACHE_POLICY` (lru/lfu/fifo/ttl), `EVENT_CACHE_POLICY`, `ENTITY_CACHE_POLICY`.
* Xử lý song song: `PARALLEL_PROCESSING_ENABLED`, `MAX_WORKERS`, `PROCESSING_CHUNK_SIZE`.

## Khuyến nghị

* Điều chỉnh batch size theo tải thật (ví dụ 100–1000 sự kiện/batch).
* Bật `PARALLEL_PROCESSING_ENABLED` khi có nhiều CPU; để `MAX_WORKERS=None` để tự chọn theo 50% số lõi.
* Dùng Arrow để giảm overhead chuyển đổi; tránh chuyển đổi qua lại nhiều lần.

## Benchmark tối thiểu

1. **Ghi 10k sự kiện và đo thời gian**: Chạy thử nghiệm tải cơ bản.
2. **Điều chỉnh cấu hình**: Thử thay đổi các tham số `PROCESSING_CHUNK_SIZE`, `EVENT_CACHE_POLICY`.
3. **So sánh kết quả**: Đo lường throughput (events/sec) và độ trễ (latencies p50/p95).

## Quan sát hệ thống

* Dùng `monitoring/performance_monitor.py` để lấy metrics CPU/RAM.
* Bật `ResourceGuardMiddleware` để shed load trong đỉnh tải.

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * Tham số cache/song song hoá nằm trong `hierachain/config/settings.py`.
    * Lưu trữ Arrow trong `hierachain/core/block.py` và schema ở `core/schemas.py`.

    **DECISION**

    * Ưu tiên batch và Arrow; tránh payload `data` lớn nếu không cần.

    **ASSUMPTION**

    * Tải thực tế có tính bùng nổ; cần khả năng shed load.

    **INVARIANT**

    * Tối ưu không được phá vỡ tính xác định của hash/Merkle.

    **EDGE CASES**

    * TTL cache quá ngắn gây miss liên tục; batch quá lớn gây spike bộ nhớ.
