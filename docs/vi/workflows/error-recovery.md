---
title: "Giảm thiểu Lỗi & Phục hồi"
description: "Luồng công việc tự động khôi phục và giảm thiểu tác động khi xảy ra lỗi mạng, hết hạn kết nối của leader hoặc bất thường về tính toàn vẹn dữ liệu."
icon: material/alert-decagram
---

# Giảm thiểu Lỗi & Phục hồi (Error Mitigation & Recovery)

## Tổng quan

HieraChain cung cấp các cơ chế khôi phục tự động phân lớp trên ba khía cạnh: **khả năng phục hồi mạng (network resilience)**, **khôi phục nút trưởng nhóm (consensus leader recovery)**, và **hoàn trả trạng thái (state rollback)**. Các cơ chế này hoạt động độc lập và có thể chạy đồng thời.

---

## 6A — Khôi phục Mạng (Network Recovery)

```mermaid
flowchart TB
    NET["🌐 Phát hiện sự cố mạng"]
    LAT["📊 Thu thập lịch sử độ trễ"]
    ADJ["⏱️ adjust_timeout()\nTính toán lại dựa trên độ trễ trung bình + lớn nhất"]
    RED["📡 send_with_redundancy()\nGửi đồng thời qua N đường truyền song song"]
    FIRST["✅ Phản hồi thành công đầu tiên được chấp nhận"]
    PART["⚠️ Phát hiện phân mảnh mạng?\navg_latency > 5000ms"]
    VC["🔄 _initiate_view_change()\nKích hoạt view change BFT"]

    NET --> LAT --> ADJ --> RED --> FIRST
    RED --> PART
    PART -->|Có| VC
    PART -->|Không| FIRST
```

**Chiến lược**: Phương thức `send_with_redundancy()` gửi cùng một thông điệp qua N đường truyền mạng song song cùng một lúc. Phản hồi thành công đầu tiên sẽ được chấp nhận, và các cuộc gọi đang truyền khác sẽ bị hủy bỏ. Cơ chế này giúp xử lý các lỗi đứt quãng đường truyền mà không cần logic thử lại (retry) phức tạp.

---

## 6B — Khôi phục Đồng thuận (Lỗi Trưởng nhóm - Leader Failure)

```mermaid
sequenceDiagram
    autonumber
    participant CRE as 🔧 ConsensusRecoveryEngine
    participant VM as 🔄 BFTViewChangeManager
    participant NEW as 👑 Trưởng nhóm Mới (New Leader)

    Note over CRE: Phát hiện hết hạn kết nối với Leader
    CRE->>CRE: handle_leader_failure(failed_leader_id, current_view)
    CRE->>CRE: Kiểm tra recovery_attempts < max (mặc định 3)
    CRE->>VM: _initiate_view_change(failed_leader, new_view = view + 1)
    VM->>VM: Phát tin VIEW-CHANGE đến tất cả các trình xác thực
    VM->>NEW: Bầu trưởng nhóm mới: Validators[new_view % n]
    NEW->>NEW: Bắt đầu lại pha PRE-PREPARE
    CRE->>CRE: Xóa đếm số lần thử recovery_attempts khi thành công
```

---

## 6C — Hoàn trả Trạng thái (State Rollback)

```mermaid
flowchart LR
    ERR["❌ Lỗi nghiêm trọng\nhoặc Tính toàn vẹn lỗi"]
    SNAP["📸 Nạp Ảnh chụp trạng thái\n(RollbackManager)"]
    JRNL["📓 Phát lại Nhật ký ghi chép\n(TransactionJournal)"]
    VER["🔍 Xác thực Trạng thái đã khôi phục\n(DataValidator)"]
    OK["✅ Trạng thái đã phục hồi"]
    ALERT["🚨 Cảnh báo + Leo thang\n(AlertManager)"]

    ERR --> SNAP --> JRNL --> VER
    VER -->|Hợp lệ| OK
    VER -->|Không hợp lệ| ALERT
```

**Các bước hoàn trả**:
1. `RollbackManager.load_snapshot()` — nạp ảnh chụp trạng thái (snapshot) nhất quán gần đây nhất.
2. `TransactionJournal.replay()` — phát lại (replay) các nhật ký đã cam kết kể từ thời điểm chụp snapshot.
3. `DataValidator.validate()` — xác thực trạng thái đã khôi phục so với mã kiểm tra băm (cryptographic checksums).
4. Nếu xác thực thất bại: gửi cảnh báo leo thang qua hệ thống Cảnh báo Rủi ro; yêu cầu sự can thiệp thủ công từ người quản trị.

---

## Các bước thực hiện chi tiết

| Luồng phụ | Kích hoạt | Hành động |
|:----------|:----------|:----------|
| **6A Mạng** | `avg_latency > ngưỡng` | Khoảng thời gian chờ thích ứng + gửi song song dự phòng |
| **6A Phân mảnh** | `avg_latency > 5000ms` | Kích hoạt Thay đổi Phiên (View Change) BFT (Đồng thuận BFT) |
| **6B Trưởng nhóm** | `leader_timeout` | Gọi `ConsensusRecoveryEngine.handle_leader_failure()` $\rightarrow$ View Change |
| **6B Thử lại tối đa**| `recovery_attempts ≥ max` | Ghi lỗi nghiêm trọng, cảnh báo rủi ro, tạm dừng đồng thuận |
| **6C Hoàn trả** | Lỗi toàn vẹn dữ liệu hoặc lỗi nghiêm trọng | Nạp ảnh chụp trạng thái $\rightarrow$ Phát lại Nhật ký $\rightarrow$ Xác thực |

---

## Xử lý lỗi

| Tình huống | Hành vi |
|:-----------|:--------|
| Hết lượt khôi phục (6B) | Gửi cảnh báo rủi ro mức tối cao, nút dừng tham gia quá trình đồng thuận |
| Không tìm thấy Ảnh chụp (6C) | Chuyển sang nạp lại đầy đủ chuỗi từ cơ sở dữ liệu (Chain Rehydration) |
| Phát lại nhật ký ra trạng thái không hợp lệ | Cảnh báo leo thang qua hệ thống Cảnh báo Rủi ro, đánh dấu yêu cầu can thiệp thủ công |
| Sự cố phân mảnh mạng được khắc phục | Khoảng chờ thích ứng tự động giảm xuống, luồng hoạt động bình thường trở lại |

---

## Các Class & Method quan trọng

| Bước | Class / Method | File |
|:-----|:--------------|:-----|
| Cấu hình khoảng chờ mạng | `NetworkRecoveryManager.adjust_timeout()` | `error_mitigation/recovery_engine.py` |
| Gửi tin dự phòng | `send_with_redundancy()` | `error_mitigation/recovery_engine.py` |
| Xử lý lỗi Leader | `ConsensusRecoveryEngine.handle_leader_failure()` | `error_mitigation/recovery_engine.py` |
| Kích hoạt View Change | `BFTViewChangeManager._initiate_view_change()` | `consensus/bft/consensus.py` |
| Nạp ảnh chụp | `RollbackManager.load_snapshot()` | `error_mitigation/rollback_manager.py` |
| Phát lại nhật ký | `TransactionJournal.replay()` | `error_mitigation/journal.py` |
| Xác thực trạng thái | `DataValidator.validate()` | `error_mitigation/validator.py` |

---

## Liên quan

- [Đồng thuận BFT](./bft-consensus.md) — Chi tiết về Thay đổi Phiên (View Change)
- [Khóa băng Cụm](./cluster-lockdown.md) — Khôi phục ở cấp độ toàn cụm nút
- [Nạp lại Trạng thái Chuỗi](./chain-rehydration.md) — Tải lại toàn bộ chuỗi từ cơ sở dữ liệu (DB)
- [Cảnh báo Rủi ro](./risk-alerts.md) — Các thông báo cảnh báo leo thang
