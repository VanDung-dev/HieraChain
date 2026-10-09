---
title: "Tổng quan về Luồng công việc"
description: "Hướng dẫn và tài liệu tham chiếu cho lập trình viên về các quy trình HieraChain: vận hành cốt lõi, bảo mật, đồng thuận và khôi phục."
icon: material/routes
---

# Tổng quan và hướng dẫn luồng công việc

HieraChain là sổ cái phân cấp thuần Python, hoạt động như plugin layer cho hạ tầng Web2 hiện có. Nó không thay thế ngăn xếp mạng doanh nghiệp vốn đã xử lý TLS/SSL, tường lửa và WAF ở API gateway. HieraChain tập trung vào tính bất biến, niềm tin phân tán, bằng chứng can thiệp và chống chối bỏ.

Tài liệu này liệt kê các quy trình theo sáu nhóm chức năng. Nó mô tả cách các quy trình tương tác khi chạy và cách đọc, bảo trì hoặc bổ sung quy trình.

## 1. Rào chắn phát triển cốt lõi

Khi làm việc với luồng công việc của HieraChain, tuân thủ các rào chắn sau:

* Kiểm duyệt thuật ngữ: HieraChain theo dõi sổ cái quy trình nghiệp vụ, không phải tiền mã hóa. Không dùng thuật ngữ tiền mã hóa trong payload sự kiện, tên biến, khóa cơ sở dữ liệu hoặc comment.

    * Từ bị cấm: `transaction`, `mining`, `coin`, `token`, `wallet`, `address`, `sender`, `receiver`, `amount`, `fee`.
    * Từ bắt buộc: `event` cho mục sổ cái, `node` cho peer, `msp_id` cho danh tính, `entity_id` cho tài sản nghiệp vụ.
    * `CrossChainValidator` kiểm tra dữ liệu ledger/miền được cung cấp; nó không phải hook commit mã nguồn.

* Ràng buộc độ trễ thấp: Kiến trúc hướng đến độ trễ thấp; độ trễ thực tế phụ thuộc vào gom lô, lưu bền vững và triển khai. Giữ mã quy trình ngắn gọn, chạy nhanh. Không thêm mã hóa ở tầng truyền tải hoặc lớp bọc bổ sung làm tăng chi phí CPU.
* Không truy cập trực tiếp bộ lưu trữ: không truy vấn SQL hoặc Redis trực tiếp. Dùng adapter lưu trữ trong `adapters/database/` (ví dụ `adapters/database/sqlite_adapter.py`).

## 2. Tất cả luồng công việc: tra cứu nhanh

Bảng này liệt kê tất cả luồng để tra cứu nhanh:

| Luồng công việc | Nhóm | Kích hoạt | Kết quả | Mô-đun chính |
|:---------|:------|:--------|:-------|:-----------|
| [Gửi Sự kiện](./event-submission.md) | A | `POST /api/ledger/chains/{chain_name}/events` | API trả `event_id`; block được tạo và finalize ở xử lý nền | `hierarchical/sub_chain/base.py` (`SubChain.add_event`) |
| [Neo giữ Bằng chứng](./proof-anchoring.md) | A | Khối được hoàn thiện trên Sub-Chain | Mã băm bằng chứng trên Main Chain | `hierarchical/main_chain/base.py` + `hierarchical/sub_chain/proof.py` |
| [Giao dịch Liên chuỗi 2PC](./cross-chain-2pc.md) | A | `HierarchyManager.transaction_manager` | `COMMITTED`, `ROLLED_BACK` hoặc `IN_DOUBT` có thể phục hồi | `hierarchical/hierarchy_manager/base.py` + `hierarchical/transaction_manager.py` |
| [Đồng thuận BFT](./bft-consensus.md) | B | Thành phần consensus BFT được sử dụng tường minh; không được chọn qua biến cấu hình MainChain/SubChain | Quy trình đồng thuận BFT riêng | `consensus/bft/consensus.py` |
| [Giảm thiểu Lỗi & Phục hồi](./error-recovery.md) | C | Lỗi xác thực / hết hạn leader / sự kiện bị gián đoạn | Lỗi được phân loại, replay journal hoặc BFT view change | `error_mitigation/error_classifier.py` + `journal.py` + `consensus/bft/view_change.py` |
| [Truy vết Thực thể](./entity-tracing.md) | D | `EntityTracer.trace_entity()` | Dấu vết kiểm toán liên chuỗi đầy đủ | `domains/utils/entity_tracer.py` |
| [Nạp lại Trạng thái Chuỗi](./chain-rehydration.md) | D | Khởi động lại node hoặc lệch mã băm | Chuỗi trong bộ nhớ đồng bộ với DB | `hierarchical/sub_chain/base.py` + `hierarchical/sub_chain/ordering.py` |
| [Kiểm tra tính toàn vẹn](./integrity-validation.md) | D | Lời gọi chủ động từ ứng dụng | Tổng hợp sức khỏe hoặc báo cáo nhất quán khối/bằng chứng | `hierarchical/hierarchy_manager/validation.py` |
| [Thực thi chính sách](./policy-enforcement.md) | E | Lời gọi rõ ràng đến `PolicyEngine` | `allow` hoặc `deny` kèm đường dẫn quyết định | `security/policy_engine.py` |
| [Truyền WebSocket](./websocket-streaming.md) | E | Client kết nối đến `/ws`, có thể truyền tham số truy vấn `chain_name` | Đăng ký theo dõi; thông báo cần lời gọi broadcast từ ứng dụng | `api/websocket/manager.py` |
| [Lưu trữ Mã hóa IPFS](./ipfs-storage.md) | E | `IPFSClient.upload_json()` | Trả về CID; bản mã trên IPFS | `api/storage/ipfs_client.py` |
| [Phân tích rủi ro và cảnh báo](./risk-alerts.md) | E | Ứng dụng gọi `AlertManager.check_metric()` | Thông báo được xếp hàng và nâng cấp theo cấu hình quy tắc | `monitoring/alert_system.py` |
| [Đồng bộ Tích hợp ERP](./erp-integration.md) | E | Timer `SyncScheduler` | Sự kiện ERP được gửi tới Sub-Chain | `integration/erp_ledger.py` |
| [Danh tính và xác thực MSP](./msp-identity.md) | F | Lời gọi đăng ký/xác thực MSP rõ ràng | Danh tính được xác nhận + thao tác được cấp quyền | `security/msp.py` |
| [Sao lưu và khôi phục khóa](./key-backup.md) | F | Sao lưu tệp/kho khóa do người vận hành quản lý | Các tệp danh tính/provider được khôi phục | `cli/key.py` + `security/key_provider.py` (không có `key_backup_manager.py`) |

## 3. Nhóm chức năng và phân hệ

Các luồng được nhóm thành sáu khu vực. Dùng bảng điều khiển bên dưới để tìm nhóm khớp với phân hệ bạn đang gỡ lỗi hoặc thay đổi:

<div class="grid cards" markdown>

* :material-sitemap:{ .lg .middle } __Nhóm A: Hoạt động chuỗi cốt lõi__

    ---

    Xử lý tiếp nhận, xác thực mật mã và lưu trữ.

    * [Gửi Sự kiện](./event-submission.md)
    * [Neo giữ Bằng chứng](./proof-anchoring.md)
    * [Thao tác Liên chuỗi (2PC)](./cross-chain-2pc.md)

* :material-shield-key:{ .lg .middle } __Nhóm B: Hoàn thiện đồng thuận__

    ---

    Hoàn thiện khối. Với lựa chọn PoA/PoF, xem [Cơ chế Đồng thuận](./consensus_mechanisms.md).

    * [Đồng thuận BFT (PBFT 3 pha)](./bft-consensus.md)

* :material-server-security:{ .lg .middle } __Nhóm C: Quản lý cụm__

    ---

    Quản trị, kích hoạt khóa băng và phục hồi.

    * [Giảm thiểu Lỗi & Phục hồi](./error-recovery.md)

* :material-shield-check:{ .lg .middle } __Nhóm D: Tính toàn vẹn và truy vết__

    ---

    Kiểm toán, nạp lại khi khởi động lạnh và xác thực toàn vẹn.

    * [Truy vết Thực thể](./entity-tracing.md)
    * [Nạp lại Trạng thái Chuỗi](./chain-rehydration.md)
    * [Xác thực Tính toàn vẹn](./integrity-validation.md)

* :material-connection:{ .lg .middle } __Nhóm E: Vận hành và tích hợp__

    ---

    Cổng chính sách, đẩy WebSocket, lưu trữ IPFS mã hóa và đồng bộ ERP.

    * [Thực thi Chính sách](./policy-enforcement.md)
    * [Luồng dữ liệu WebSocket](./websocket-streaming.md)
    * [Lưu trữ Mã hóa IPFS](./ipfs-storage.md)
    * [Cảnh báo Rủi ro](./risk-alerts.md)
    * [Đồng bộ Tích hợp ERP](./erp-integration.md)

* :material-key-chain:{ .lg .middle } __Nhóm F: Quản lý danh tính và khóa__

    ---

    Đăng ký MSP nhẹ (lớp `Certificate` nội bộ trong `security/msp.py`), ủy quyền thành viên và sao lưu khóa do CLI quản lý (không có X.509/mTLS).

    * [Danh tính & Xác thực MSP](./msp-identity.md)
    * [Sao lưu & Khôi phục Khóa](./key-backup.md)

</div>

## 4. Cách luồng tương tác

Sơ đồ tách các luồng runtime khỏi phần tích hợp do ứng dụng cung cấp. Đường nét đứt chỉ các kết nối do bên gọi quản lý.

```mermaid
flowchart TD
    CLIENT[Client or SDK] -->|Ledger API| WF1[Event submission]
    ERP[Application ERP sink] -->|add_event| WF1
    WF1 -->|Apply committed block, proof due| WF2[Proof anchoring]
    App -.->|Upload via IPFSClient.upload_json()| WF12[IPFS storage]
    WF12 -.->|Return CID to caller| App
    App -.->|Submit event with details_cid| WF1
    App[Application integration] -.-> MSP[MSP checks]
    App -.-> Policy[PolicyEngine checks]
    App -.-> WS[WebSocket broadcast helpers]
    App -.-> Integrity[Integrity reports]
    Integrity -.->|Caller handles report| Alerts[AlertManager]
    App -.-> Backup[Identity backup]
    App --> Rehydrate[Explicit sync_chain]
    Rehydrate -->|Rebuild chain and indexes| WF1
    Trace[Entity tracing] -->|Read finalized history| WF1
    App --> BFT[Separate BFT library]
    App --> TwoPC[Cross-chain 2PC coordinator]
```

### Luồng tích hợp chính cho lập trình viên

| Chuỗi tiếp nhận và bảo mật | Mô tả |
|:---|:---|
| ERP → ERP Sync → Gửi Sự kiện → Neo giữ Bằng chứng | Pipeline tiếp nhận: thay đổi nghiệp vụ → sự kiện nội bộ → khối Sub-Chain → mã băm bằng chứng neo lên chuỗi gốc. |
| Danh tính MSP → Thực thi chính sách → Gửi sự kiện | Tích hợp do bên gọi quản lý: MSP kiểm tra vai trò/chính sách tổ chức; ứng dụng có thể thêm bước kiểm tra `PolicyEngine` riêng trước khi gửi. |
| Kiểm tra tính toàn vẹn → Rủi ro và cảnh báo → Khôi phục sau lỗi | Tích hợp do bên gọi quản lý: kiểm tra kết quả tính toàn vẹn, cung cấp metric hoặc quy tắc cảnh báo, rồi chọn hành động khôi phục vận hành. |
| Khôi phục sau lỗi → Nạp lại trạng thái chuỗi | Phát lại lúc khởi động ordering và đồng bộ Sub-Chain khôi phục trạng thái cục bộ; không có hook tự động từ lỗi snapshot sang dựng lại chuỗi. |

## 5. Hướng dẫn lập trình viên: duy trì luồng công việc

Giữ tài liệu luồng đồng bộ với mã khi bạn thêm tính năng hoặc sửa hành vi:

### Cấu trúc của một tài liệu luồng
Mỗi trang luồng (ví dụ `event-submission.md`) có bố cục sau. Nó phải chứa:

1. Front-matter Zensical: metadata YAML với `title`, `description` và `icon`. Không có tiền tố WF-number.
2. Tiêu đề H1: `# [Title]` khớp với front-matter.
3. Tổng quan: luồng làm gì và khi nào dùng.
4. Sơ đồ luồng: sơ đồ Mermaid sequence hoặc flowchart thể hiện tương tác thời gian chạy.
5. Chi tiết từng bước: bảng ánh xạ số thứ tự tới hành động của lập trình viên.
6. Xử lý lỗi: bảng ánh xạ lỗi (node offline, lỗi xác thực) tới biện pháp xử lý.
7. Lớp và phương thức chính: con trỏ từ bước luồng tới mã (ví dụ `SubChain.add_event()`).
8. Liên quan: liên kết tới luồng anh em hoặc luồng tiếp theo.

### Quy trình thêm hoặc sửa luồng

1. Viết Markdown chuẩn: lưu luồng mới dưới `docs/en/workflows/name.md` dùng hệ thống thiết kế hiện tại.
2. Đăng ký trong zensical.toml: thêm luồng vào cây `Workflows` trong [zensical.toml](https://github.com/VanDung-dev/HieraChain/blob/main/zensical.toml) với tên gọn.
3. Quét thuật ngữ: kiểm tra không thêm từ vựng tiền mã hóa bị cấm.
4. Biên dịch và xác thực: chạy build Zensical trong môi trường HieraChain để kiểm tra định dạng và liên kết:

    ```bash
    zensical build -f zensical.toml
    ```
