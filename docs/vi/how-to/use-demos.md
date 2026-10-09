---
title: "Hướng dẫn chạy Demo"
description: "Cách chạy các kịch bản demo để kiểm tra tính năng cốt lõi của HieraChain."
icon: material/play-circle
---

# Hướng dẫn chạy Demo (`demo/*`)

Thư mục `demo/` chứa ví dụ thư viện và giao diện. Kích hoạt môi trường repository và cấp signing identity/bản đồ khóa đáng tin cậy theo [Quickstart](../getting-started/quickstart.md) trước khi chạy script tạo chain. Kết quả demo và mock không bảo đảm lưu bền hay bảo mật cho production.

## 1. Demo tính năng cốt lõi (Core Features)

Script này trình diễn luồng tạo Sub-chain, gửi Event, và cơ chế Channel/Private Data.

```bash
# Run the basic demo
python demo/demo.py
```

Các bước diễn ra trong demo:

* Khởi tạo Main Chain và Sub-Chain (`supply_chain`).
* Đăng ký tổ chức (Organization) và người dùng (User).
* Gửi các sự kiện (Events) nghiệp vụ.
* Tạo Private Data Collection chỉ chia sẻ giữa hai bên.

## 2. Demo Đồng thuận BFT qua ZeroMQ

Trình diễn khả năng đồng thuận của 4 node sử dụng giao thức BFT qua mạng ZeroMQ.

```bash
# Run the BFT demo
python demo/demo_zmq_consensus.py
```

## 3. Sao lưu và khôi phục khóa

Xem [Sao lưu khóa](../workflows/key-backup.md) để biết file khóa CLI, node identity đầy đủ và vault mã hóa cho phát triển. Repository không có `demo_key_backup.py` hay `KeyBackupManager`.

## 4. Demo Tích hợp IPFS

Minh họa cách lưu trữ dữ liệu lớn/tài liệu lên IPFS với mã hóa AES-256.

```bash
# Run the IPFS demo
python demo/demo_ipfs.py
```

Script thử kết nối IPFS daemon cục bộ trên cổng 5001 và có thể chuyển sang mock trong bộ nhớ. CID của mock không chứng minh dữ liệu được lưu mã hóa hay truy xuất được từ daemon thật.

## 5. Trình khám phá Blockchain (Explorer)

Giao diện web đơn giản để xem danh sách block và sự kiện.

```bash
# Run the explorer demo
python demo/demo_explorer.py
```

Demo phục vụ JSON đã tạo và dashboard riêng tại [http://127.0.0.1:8000/explorer](http://127.0.0.1:8000/explorer). Chạy `demo/demo.py` trước để tạo dữ liệu. Server này tách biệt với ledger API trên cổng 2661.
