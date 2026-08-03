---
title: "Khóa băng Cụm (Cluster Lockdown)"
description: "Giao thức điều phối khóa băng trạng thái của toàn cụm nút được kích hoạt khi phát hiện các rủi ro nguy hiểm."
icon: material/lock
---

# Khóa băng Cụm (Cluster Lockdown)

## Tổng quan

**Giao thức Khóa băng Cụm (Cluster Lockdown Protocol)** điều phối việc đóng băng trạng thái của toàn bộ hệ thống trên tất cả các nút khi phát hiện sự bất thường nghiêm trọng. Cơ chế này sử dụng **giao thức tin nhắn ngang hàng P2P kiểu tin đồn (gossip) qua ZeroMQ** và yêu cầu **biểu quyết quá bán (tối thiểu 2/3)** của các nút đã đăng ký để kích hoạt cả quá trình khóa băng lẫn phục hồi. Tất cả thông điệp đều được xác thực bằng chữ ký **HMAC-SHA256** nhằm ngăn chặn các cuộc tấn công giả mạo yêu cầu khóa băng.

**Đặc tính quan trọng**: Không một nút đơn lẻ nào có thể đơn phương khóa băng toàn bộ cụm; đạt tỷ lệ biểu quyết tối thiểu (quorum) là điều bắt buộc.

---

## Biểu đồ luồng

```mermaid
sequenceDiagram
    autonumber
    participant N1 as 🖥️ Nút 1 (Phát hiện)
    participant N2 as 🖥️ Nút 2
    participant N3 as 🖥️ Nút 3
    participant OS as ⚙️ Local OrderingService

    Note over N1: Risk Analyzer phát hiện bất thường nghiêm trọng

    rect rgb(0, 0, 0, 0)
        Note over N1,N3: GIAI ĐOẠN 1 — BIỂU QUYẾT KHÓA BĂNG
        N1->>N1: broadcast_lockdown_vote(reason)
        N1->>N2: LOCKDOWN_VOTE { node_id, reason, HMAC-SHA256 }
        N1->>N3: LOCKDOWN_VOTE { node_id, reason, HMAC-SHA256 }

        N2->>N2: Xác thực chữ ký HMAC & dấu thời gian (≤300s)
        N2->>N2: Đăng ký phiếu biểu quyết khóa băng
        N2->>N1: LOCKDOWN_VOTE (N2 đồng ý)
        N2->>N3: LOCKDOWN_VOTE (N2 đồng ý)

        N3->>N3: _check_lockdown_quorum() → votes/total ≥ 0.66
        N3->>N3: _trigger_quorum_lockdown()
    end

    rect rgb(0, 0, 0, 0)
        Note over N1,OS: GIAI ĐOẠN 2 — ĐÓNG BĂNG HỆ THỐNG
        N1->>OS: local_lockdown_callback()
        N2->>OS: local_lockdown_callback()
        N3->>OS: local_lockdown_callback()
        OS->>OS: Ngừng tiếp nhận các sự kiện mới
        N1->>N2: QUARANTINE_REPORT (pending_event_ids, last_block_hash)
        N1->>N3: QUARANTINE_REPORT (pending_event_ids, last_block_hash)
    end

    rect rgb(0, 0, 0, 0)
        Note over N1,OS: GIAI ĐOẠN 3 — BIỂU QUYẾT PHỤC HỒI
        N1->>N2: RECOVERY_VOTE
        N1->>N3: RECOVERY_VOTE
        N2->>N3: RECOVERY_VOTE

        N3->>N3: _check_recovery_quorum() → ≥ 0.66
        N3->>N3: _trigger_quorum_recovery()
        N1->>OS: local_recovery_callback()
        N2->>OS: local_recovery_callback()
        N3->>OS: local_recovery_callback()
        OS->>OS: Khôi phục tiếp nhận sự kiện mới
    end
```

---

## Máy trạng thái (State Machine)

```mermaid
stateDiagram-v2
    [*] --> NORMAL
    NORMAL --> VOTING: Phát hiện bất thường
    VOTING --> LOCKED: Quorum ≥ 2/3 phiếu khóa băng
    VOTING --> NORMAL: Không đủ phiếu / hết hạn chờ
    LOCKED --> RECOVERING: Quorum ≥ 2/3 phiếu phục hồi
    RECOVERING --> NORMAL: Đồng bộ hóa trạng thái hoàn tất
    LOCKED --> LOCKED: Trao đổi các báo cáo kiểm dịch (Quarantine)
```

---

## Các bước thực hiện chi tiết

| Bước | Mô tả |
|:-----|:------|
| **1. Phát hiện bất thường** | Lệnh `RiskAnalyzer` hoặc người vận hành hệ thống kích hoạt `broadcast_lockdown_vote(reason)` thủ công. |
| **2. Phát tin phiếu bầu** | Lan truyền thông điệp LOCKDOWN_VOTE dạng gossip tới tất cả các nút ngang hàng, được ký kèm HMAC-SHA256 + dấu thời gian. |
| **3. Xác thực phiếu bầu** | Mỗi nút nhận tin xác thực chữ ký HMAC và từ chối các phiếu bầu có thời gian trễ lớn hơn 300 giây. |
| **4. Kiểm tra Quorum** | Lệnh `_check_lockdown_quorum()`: nếu tỷ lệ `votes / total_nodes ≥ 0.66` $\rightarrow$ quy trình khóa băng được kích hoạt. |
| **5. Đóng băng hệ thống** | Mỗi nút gọi hàm gọi lại `local_lockdown_callback()` $\rightarrow$ `OrderingService` dừng hoàn toàn việc tiếp nhận sự kiện. |
| **6. Báo cáo kiểm dịch** | Các nút trao đổi danh sách ID các sự kiện đang chờ xử lý và các mã băm của khối cuối cùng để đối soát độ sai lệch trạng thái. |
| **7. Biểu quyết phục hồi** | Sau khi phân tích lỗi xong, người vận hành hoặc trigger tự động khởi tạo lan truyền `RECOVERY_VOTE` dạng gossip. |
| **8. Quorum phục hồi** | Yêu cầu ngưỡng tối thiểu tương tự (2/3). Khi đạt quorum: gọi hàm `local_recovery_callback()` $\rightarrow$ khôi phục hoạt động bình thường. |

---

## Xử lý lỗi

| Tình huống | Hành vi |
|:-----------|:--------|
| Xác thực HMAC thất bại | Phiếu biểu quyết bị loại bỏ, ghi nhật ký cảnh báo |
| Dấu thời gian phiếu bầu > 300 giây | Phiếu biểu quyết bị từ chối (ngăn chặn tấn công phát lại - replay attack) |
| Không đạt đủ tỷ lệ phiếu khóa băng | Hệ thống tiếp tục hoạt động bình thường, các phiếu bầu tự động hết hạn |
| Không đạt đủ tỷ lệ phiếu phục hồi | Toàn cụm tiếp tục bị khóa băng; phát đi cảnh báo leo thang thông qua hệ thống Cảnh báo Rủi ro |
| Nút mới tham gia cụm trong lúc khóa băng | Nút mới tự động nhận trạng thái LOCKED thông qua `StateSyncManager` |

---

## Các Class & Method quan trọng

| Bước | Class / Method | File |
|:-----|:--------------|:-----|
| Khởi tạo khóa băng | `ClusterLockdownManager.broadcast_lockdown_vote()` | `cluster/lockdown_protocol.py` |
| Xác thực tin nhắn | `_verify_lockdown_message()` | `cluster/lockdown_protocol.py` |
| Kiểm tra Quorum | `_check_lockdown_quorum()` | `cluster/lockdown_protocol.py` |
| Đóng băng hệ thống | `local_lockdown_callback()` | `cluster/lockdown_protocol.py` |
| Quorum phục hồi | `_check_recovery_quorum()` | `cluster/lockdown_protocol.py` |
| Đồng bộ trạng thái | `StateSyncManager.sync_state()` | `cluster/state_sync_manager.py` |
| Giao thức mạng | `ZmqTransport.broadcast()` | `network/zmq_transport.py` |

---

## Liên quan

- [Risk Analysis & Alerts](./risk-alerts.md): Việc vượt quá ngưỡng rủi ro cho phép sẽ kích hoạt quy trình này
- [Giảm thiểu Lỗi & Phục hồi](./error-recovery.md): Xử lý hoàn trả trạng thái (rollback) sau khi phục hồi thành công
- [Sao lưu & Khôi phục Khóa](./key-backup.md): Quá trình khóa băng cụm có thể kích hoạt cơ chế luân chuyển khóa $\rightarrow$ Sao lưu & Khôi phục Khóa
