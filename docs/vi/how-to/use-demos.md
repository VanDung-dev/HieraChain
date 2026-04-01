---
title: "Hướng dẫn chạy Demo"
description: "Cách chạy các kịch bản demo để kiểm tra tính năng cốt lõi của HieraChain."
icon: material/play-circle
---

# Hướng dẫn chạy Demo (`demo/*`)

Thư mục `demo/` chứa các script mẫu giúp bạn nhanh chóng làm quen với các tính năng quan trọng của hệ thống.

## 1. Demo tính năng cốt lõi (Core Features)

Script này trình diễn luồng tạo Sub-chain, gửi Event, và cơ chế Channel/Private Data.

```bash
# Chạy demo cơ bản
python demo/demo.py
```

**Các bước diễn ra trong demo:**

* Khởi tạo Main Chain và Sub-Chain (`supply_chain`).
* Đăng ký tổ chức (Organization) và người dùng (User).
* Gửi các sự kiện (Events) nghiệp vụ.
* Tạo Private Data Collection chỉ chia sẻ giữa hai bên.

---

## 2. Demo Đồng thuận BFT qua ZeroMQ

Trình diễn khả năng đồng thuận của 4 node sử dụng giao thức BFT qua mạng ZeroMQ.

```bash
# Chạy demo BFT
python demo/demo_zmq_consensus.py
```

---

## 3. Demo Sao lưu và Khôi phục Khóa

Hướng dẫn cách sử dụng `KeyBackupManager` để bảo vệ khóa cá nhân của người dùng.

```bash
# Chạy demo backup
python demo/demo_key_backup.py
```

---

## 4. Demo Tích hợp IPFS

Minh họa cách lưu trữ dữ liệu lớn/tài liệu lên IPFS với mã hóa AES-256.

```bash
# Chạy demo IPFS
python demo/demo_ipfs.py
```

> **Lưu ý**: Yêu cầu daemon IPFS phải đang chạy (mặc định tại port 5001).

---

## 5. Trình khám phá Blockchain (Explorer)

Giao diện web đơn giản để xem danh sách block và sự kiện.

```bash
# Chạy explorer demo
python demo/demo_explorer.py
```

Sau đó truy cập [http://localhost:2661/explorer](http://localhost:2661/explorer) (yêu cầu server API đang chạy).

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * Các script demo nằm trong thư mục gốc `demo/`.
    * Yêu cầu môi trường Python >= 3.10.
    * Hầu hết demo cần khởi tạo `HierarchyManager` (Main Chain) trước.

    **DECISION**

    * Chạy script trực tiếp từ thư mục gốc để đảm bảo các import nội bộ từ `hierachain` hoạt động đúng.
    * Tách riêng các demo theo tính năng (Consensus, Security, IPFS) để dễ kiểm tra độc lập.

    **ASSUMPTION**

    * Người chạy demo đã cài đặt đầy đủ dependencies qua `pip install -e .`.
    * Biến môi trường `.env` đã được cấu hình nếu demo yêu cầu database hoặc IPFS thật.

    **INVARIANT**

    * Demo không làm thay đổi dữ liệu thật nếu đang chạy ở mode `MemoryStorage`.
    * Mọi demo đều phải dọn dẹp (cleanup) tài nguyên hoặc log sau khi kết thúc nếu chạy thành công.

    **EDGE CASES**

    * Chạy demo IPFS khi server IPFS local chưa bật → script sẽ tự động chuyển sang mock mode hoặc báo lỗi kết nối.
    * Chạy nhiều demo cùng lúc trên cùng một database file → có thể gây lock database (nếu dùng SQLite).
