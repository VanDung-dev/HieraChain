---
title: "Hướng dẫn hiệu năng"
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
* Ordering batches: `OrderingService` khởi tạo trực tiếp mặc định 100 event và 2.0 giây; cấu hình SubChain mặc định dùng 50 event và 1.0 giây.

## Khuyến nghị

* Điều chỉnh `batch_size` hoặc `block_size` và `batch_timeout` theo tải đo được và cấu hình service đang dùng.
* Dùng Arrow để giảm overhead chuyển đổi; tránh chuyển đổi qua lại nhiều lần.

## Benchmark tối thiểu

1. **Ghi 10k sự kiện và đo thời gian**: Chạy thử nghiệm tải cơ bản.
2. **Điều chỉnh cấu hình**: Thử thay đổi các thiết lập batch của Ordering và `EVENT_CACHE_POLICY`.
3. **So sánh kết quả**: Đo lường throughput (events/sec) và độ trễ (latencies p50/p95).

## Quan sát hệ thống

* Dùng `monitoring/performance_monitor.py` để lấy metrics CPU/RAM.
* Bật `ResourceGuardMiddleware` để shed load trong đỉnh tải.
