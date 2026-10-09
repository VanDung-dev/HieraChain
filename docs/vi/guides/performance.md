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

## Cấu hình liên quan

* `AdvancedCache(max_size=..., eviction_policy=...)`: dung lượng và chính sách LRU/LFU/FIFO/TTL theo instance; TTL entry được truyền vào `set()`. Không có công tắc cache toàn cục hoặc tầng cache block/event/entity tự nối vào runtime.
* `block_cache_size` của Ordering điều khiển deque lịch sử block cục bộ (mặc định: `100`).
* Ordering batches: `OrderingService` khởi tạo trực tiếp mặc định 100 event và 2.0 giây; cấu hình SubChain mặc định dùng 50 event và 1.0 giây.

## Khuyến nghị

* Điều chỉnh `batch_size` hoặc `block_size` và `batch_timeout` theo tải đo được và cấu hình service đang dùng.
* Dùng Arrow để giảm overhead chuyển đổi; tránh chuyển đổi qua lại nhiều lần.

## Benchmark tối thiểu

1. **Ghi 10k sự kiện và đo thời gian**: Chạy thử nghiệm tải cơ bản.
2. **Điều chỉnh cấu hình**: Thử thay đổi các thiết lập batch của Ordering; chỉ điều chỉnh instance cache khi tải đo được thực sự sử dụng chúng.
3. **So sánh kết quả**: Đo throughput của event đã commit và độ trễ p95/p99, cùng số event bị từ chối/chưa hoàn tất, thời gian chờ batch, độ bền lưu trữ và chi phí I/O.

Benchmark event có chữ ký dùng chung một triển khai khi chạy cục bộ và trong Docker:

```bash
python -m scripts.benchmark_throughput --events 10000 --batch-size 100
```

Cấu hình danh tính ký của node và khóa tin cậy, đồng thời dùng database và journal riêng qua `HRC_BENCHMARK_DB_URL` và `HRC_BENCHMARK_JOURNAL_DIR`. Wrapper Docker yêu cầu PostgreSQL. Kết quả báo số event đã commit mỗi giây, số event bị từ chối/chưa hoàn tất, p95/p99, timeout batch 0,5 giây và ranh giới độ bền journal/storage. Event bị từ chối hoặc xử lý quá 60 giây khiến lệnh thất bại. Độ trễ đo lúc client quan sát block đã commit, gồm thời gian gửi đồng bộ và lấy block; đây không phải timestamp commit nội bộ của database. Benchmark này chưa đo chi phí I/O hoặc xác lập SLA production.

## Quan sát hệ thống

* Dùng `monitoring/performance_monitor.py` để lấy metrics CPU/RAM.
* Kiểm tra payload/rate limit của API, lỗi Redis, giới hạn event pool/RAM trong ordering và log lỗi storage. Không có `ResourceGuardMiddleware` CPU/RAM ở API.
