---
title: "Khóa băng Cụm"
description: "Giao thức điều phối khóa băng trạng thái của toàn cụm nút được kích hoạt khi phát hiện các rủi ro nguy hiểm."
icon: material/lock
---

# Khóa băng cụm

## Tổng quan

Giao thức khóa băng cụm đóng băng trạng thái toàn hệ thống trên mọi node khi phát hiện bất thường nghiêm trọng. Nó dùng gossip P2P qua ZeroMQ và yêu cầu quorum tối thiểu 2/3 node đã đăng ký để kích hoạt cả khóa băng lẫn khôi phục. Mọi thông điệp được xác thực bằng HMAC-SHA256 để ngăn giả mạo yêu cầu khóa băng.

Điểm chính: không một node đơn lẻ nào có thể tự khóa toàn cụm; phải đạt quorum.

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

## Máy trạng thái

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

## Các bước chi tiết

| Bước | Mô tả |
|:-----|:------|
| **1. Phát hiện** | `RiskAnalyzer` hoặc người vận hành gọi `broadcast_lockdown_vote(reason)`. |
| **2. Phát phiếu** | Lan truyền LOCKDOWN_VOTE dạng gossip tới mọi peer, kèm HMAC-SHA256 và timestamp. |
| **3. Xác thực** | Mỗi node kiểm tra chữ ký HMAC và loại phiếu có độ trễ trên 300 giây. |
| **4. Kiểm tra quorum** | `_check_lockdown_quorum()`: nếu `votes / total_nodes >= 0.66` thì kích hoạt khóa băng. |
| **5. Đóng băng** | Mỗi node gọi `local_lockdown_callback()` và `OrderingService` dừng nhận sự kiện. |
| **6. Báo cáo kiểm dịch** | Node trao đổi danh sách ID sự kiện chờ xử lý và hash khối cuối để đối chiếu lệch trạng thái. |
| **7. Biểu quyết khôi phục** | Sau khi phân tích lỗi, người vận hành hoặc trigger tự động phát `RECOVERY_VOTE` dạng gossip. |
| **8. Quorum khôi phục** | Ngưỡng tương tự (2/3). Khi đạt quorum: gọi `local_recovery_callback()` và trở lại hoạt động bình thường. |

---

## Xử lý lỗi

| Tình huống | Hành vi |
|:-----------|:--------|
| Xác thực HMAC lỗi | Loại phiếu, ghi log cảnh báo |
| Timestamp phiếu > 300 giây | Từ chối phiếu (chống replay) |
| Không đủ quorum khóa băng | Hệ thống tiếp tục bình thường, phiếu tự hết hạn |
| Không đủ quorum khôi phục | Cụm vẫn bị khóa; gửi cảnh báo leo thang qua Risk Alerts |
| Node mới tham gia khi đang khóa | Node mới vẫn bị khóa cho đến khi quorum khôi phục hoàn tất |

---

## Lớp và phương thức chính

| Bước | Lớp / Phương thức | Tệp |
|:-----|:--------------|:-----|
| Khởi tạo khóa băng | `ClusterLockdownManager.broadcast_lockdown_vote()` | `cluster/lockdown_protocol.py` |
| Xác thực tin nhắn | `_verify_lockdown_message()` | `cluster/lockdown_protocol.py` |
| Kiểm tra quorum | `_check_lockdown_quorum()` | `cluster/lockdown_protocol.py` |
| Đóng băng | `local_lockdown_callback()` | `cluster/lockdown_protocol.py` |
| Quorum khôi phục | `_check_recovery_quorum()` | `cluster/lockdown_protocol.py` |
| Giao thức mạng | `ZmqTransport.broadcast()` | `network/zmq_transport.py` |

---

## Liên quan

- [Cảnh báo Rủi ro](./risk-alerts.md): vượt ngưỡng rủi ro kích hoạt quy trình này
- [Giảm thiểu Lỗi & Phục hồi](./error-recovery.md): xử lý rollback sau khi khôi phục
- [Sao lưu & Khôi phục Khóa](./key-backup.md): khóa băng không tự kích hoạt xoay vòng khóa
