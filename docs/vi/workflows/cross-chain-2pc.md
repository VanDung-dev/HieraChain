---
title: "Giao dịch Liên chuỗi (2PC)"
description: "Phối hợp giao thức Cam kết Hai pha (2PC - Two-Phase Commit) cho các hoạt động sự kiện liên chuỗi có tính nguyên tử."
icon: material/swap-horizontal
---

# Giao dịch Liên chuỗi (2PC)

## Tổng quan

Khi một hoạt động nghiệp vụ cần diễn ra đồng thời có tính nguyên tử trên cả hai Chuỗi con (ví dụ: chuyển một tài sản từ chuỗi `logistics` sang chuỗi `finance`), HieraChain sử dụng giao thức **Cam kết Hai pha (2PC - Two-Phase Commit)** để đảm bảo tính toàn vẹn và nguyên tử. Hoặc cả hai chuỗi cùng lưu khối xác nhận sự thay đổi, hoặc cả hai cùng khôi phục lại trạng thái cũ (roll back) — tuyệt đối không có trạng thái lấp lửng hay bất đối xứng.

**Ví dụ thực tế**: Chuyển một mặt hàng trong kho giữa hai phòng ban khác nhau. Chuỗi nguồn ghi nhận sự kiện `deduct` (trừ hàng); chuỗi đích ghi nhận sự kiện `receive` (nhận hàng). Cả hai hoạt động đều phải thành công hoặc không hoạt động nào được áp dụng.

---

## Biểu đồ luồng — Trường hợp Thuận lợi (Happy Path)

```mermaid
sequenceDiagram
    autonumber
    participant HM as 🏛️ HierarchyManager
    participant TM as 🔄 CrossChainTransactionManager
    participant SRC as 📦 Chuỗi con Nguồn (Source SubChain)
    participant DST as 📦 Chuỗi con Đích (Destination SubChain)

    HM->>TM: initiate_cross_chain_transaction(src, dst, payload)
    TM->>TM: Khởi tạo CrossChainTransaction (UUID, state=PENDING)

    rect rgb(0, 0, 0, 0)
        Note over TM,DST: PHA 1 — CHUẨN BỊ (PREPARE)
        TM->>SRC: prepare_transaction(tx_id, payload, is_source=True)
        SRC->>SRC: Khóa tài nguyên, xác thực dữ liệu payload
        SRC-->>TM: True ✅

        TM->>DST: prepare_transaction(tx_id, payload, is_source=False)
        DST->>DST: Kiểm tra khả năng tiếp nhận
        DST-->>TM: True ✅

        TM->>TM: state = PREPARED
    end

    rect rgb(0, 0, 0, 0)
        Note over TM,DST: PHA 2 — CAM KẾT (COMMIT)
        TM->>SRC: commit_transaction(tx_id)
        SRC-->>TM: True ✅
        TM->>DST: commit_transaction(tx_id)
        DST-->>TM: True ✅
        TM->>TM: state = COMMITTED
    end

    TM-->>HM: tx_id (COMMITTED)
```

---

## Biểu đồ luồng — Các Trường hợp Thất bại (Failure Paths)

```mermaid
sequenceDiagram
    autonumber
    participant TM as 🔄 CrossChainTransactionManager
    participant SRC as 📦 Chuỗi con Nguồn
    participant DST as 📦 Chuỗi con Đích

    rect rgb(0, 0, 0, 0)
        Note over TM,DST: KỊCH BẢN A — Pha 1 Chuẩn bị Thất bại
        TM->>SRC: prepare_transaction(tx_id, payload)
        SRC-->>TM: True ✅
        TM->>DST: prepare_transaction(tx_id, payload)
        DST-->>TM: False ❌  (Quá tải / Xác thực lỗi)
        TM->>TM: state = PENDING → Bắt đầu khôi phục (rollback)
        TM->>SRC: rollback_transaction(tx_id)
        TM->>DST: rollback_transaction(tx_id)
        TM->>TM: state = ROLLED_BACK ⚠️
    end

    rect rgb(0, 0, 0, 0)
        Note over TM,DST: KỊCH BẢN B — Pha 2 Cam kết Một phần Thất bại
        TM->>SRC: commit_transaction(tx_id)
        SRC-->>TM: True ✅
        TM->>DST: commit_transaction(tx_id)
        DST-->>TM: Gặp Ngoại lệ (Exception) ❌
        TM->>TM: state = FAILED ❌
        Note over TM: Cần đối soát thủ công<br/>Kiểm tra log để xác định trạng thái một phần
    end
```

---

## Máy trạng thái Giao dịch (Transaction State Machine)

```mermaid
flowchart LR
    P["PENDING"] --> PR["PREPARED"]
    PR --> C["COMMITTED ✅"]
    PR --> RB["ROLLED_BACK ⚠️"]
    P --> F["FAILED ❌"]
    PR --> F
```

---

## Các bước thực hiện chi tiết

| Bước | Mô tả |
|:-----|:------|
| **1. Khởi tạo** | `HierarchyManager` tạo một thực thể `CrossChainTransaction` với UUID duy nhất và trạng thái `state=PENDING`. |
| **2. Pha 1 — Chuẩn bị nguồn** | Chuỗi nguồn khóa tài nguyên liên quan, xác thực lược đồ (schema) của payload. |
| **3. Pha 1 — Chuẩn bị đích** | Chuỗi đích kiểm tra dung lượng lưu trữ khả dụng và các ràng buộc nghiệp vụ. |
| **4. Kết quả Pha 1** | Nếu cả hai chuỗi trả về `True`: trạng thái chuyển thành `PREPARED`. Nếu một trong hai lỗi: khôi phục trạng thái cũ (rollback) ngay lập tức trên cả hai chuỗi. |
| **5. Pha 2 — Cam kết nguồn** | Chuỗi nguồn hoàn tất hoạt động (phát ra sự kiện thông qua Gửi Sự kiện). |
| **6. Pha 2 — Cam kết đích** | Chuỗi đích hoàn tất hoạt động (phát ra sự kiện thông qua Gửi Sự kiện). |
| **7. Kết quả** | Trạng thái chuyển thành `COMMITTED`. Mã `tx_id` được trả về cho bên gọi. |

---

## Xử lý lỗi

| Tình huống | Trạng thái chuyển dịch | Cách thức phục hồi |
|:-----------|:-----------------------|:-------------------|
| Lỗi Pha 1 trên Chuỗi Nguồn | `ROLLED_BACK` | Tự động hoàn trả trạng thái (rollback) trên Chuỗi Đích |
| Lỗi Pha 1 trên Chuỗi Đích | `ROLLED_BACK` | Tự động hoàn trả trạng thái (rollback) trên Chuỗi Nguồn |
| Lỗi Pha 2 khi cam kết trên một trong hai chuỗi | `FAILED` | Phải đối soát thủ công thông qua nhật ký kiểm toán (audit log) |
| Hết hạn kết nối mạng (Timeout) trong Pha 2 | `FAILED` | Người vận hành hệ thống phải kiểm tra trạng thái cam kết cuối cùng |

---

## Các Class & Method quan trọng

| Bước | Class / Method | File |
|:-----|:--------------|:-----|
| Khởi tạo | `HierarchyManager.initiate_cross_chain_transaction()` | `hierarchical/hierarchy_manager.py` |
| Tạo giao dịch | `CrossChainTransactionManager.__init__()` | `domains/generic/chains/domain_chain.py` |
| Chuẩn bị | `DomainChain.prepare_transaction()` | `domains/generic/chains/domain_chain.py` |
| Cam kết | `DomainChain.commit_transaction()` | `domains/generic/chains/domain_chain.py` |
| Khôi phục | `DomainChain.rollback_transaction()` | `domains/generic/chains/domain_chain.py` |

---

## Liên quan

- [Gửi Sự kiện](./event-submission.md) — mỗi phương thức `commit_transaction()` bên trong sẽ gọi đến `add_event()`
- [Giảm thiểu Lỗi & Phục hồi](./error-recovery.md) — quản lý khôi phục trạng thái ở cấp độ hệ thống
