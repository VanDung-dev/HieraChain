---
title: "Ordering Service"
description: "Sắp thứ tự sự kiện cục bộ, khôi phục journal bền vững, chứng nhận, gom lô và lưu khối có chữ ký."
icon: material/order-bool-ascending
---

# Ordering Service (`hierachain/consensus/ordering/*`)

## Tổng quan

Ordering Service nhận sự kiện cục bộ, ghi nhật ký và xếp hàng, sau đó chứng nhận và gom thành khối có chữ ký. Phát lại journal hỗ trợ khôi phục sau lỗi tiến trình. Dịch vụ không triển khai bầu chọn orderer nhân bản hay tự chuyển sang nút khác khi lỗi.

## Kiến trúc Hệ thống

Ordering Service được thiết kế theo mô hình Facade, điều phối nhiều thành phần chuyên biệt:

| Thành phần | Vai trò | Tệp tin |
| :--- | :--- | :--- |
| OrderingService | Điểm truy cập chính, quản lý vòng đời và cấu hình. | `service.py` |
| Processor | Thu thập bất đồng bộ, xác minh chữ ký theo batch, chứng nhận và xử lý sự kiện. | `processor.py` |
| Block Builder | Gom lô sự kiện; block manager dựng khối. | `block_builder.py` |
| Certifier | Chạy quy tắc tùy chỉnh, kiểm tra cấu trúc và kiểm tra chữ ký/ZK có điều kiện. | `certifier.py` |
| Storage | Lưu khối có chữ ký và đọc lịch sử đã hoàn tất. | `storage.py` |
| Recovery | Khôi phục trạng thái từ Event Journal sau sự cố. | `recovery.py` |
| Journal lookup | Lập index commitment ID/kênh/nội dung bền vững để nhận stable ID. | `journal_lookup.py` |

`OrderingService` sở hữu hàng đợi sự kiện, pending events, certifier, block builder, storage và metrics. `OrderingProcessor` truy cập các dependency này qua service và trực tiếp xử lý cả batch mới lẫn sự kiện replay. Việc tạo và commit block vẫn nằm trong `OrderingBlockManager`; replay journal vẫn nằm trong `OrderingRecovery`.

## Luồng xử lý Sự kiện (Ordering Pipeline)

```mermaid
graph TD
    A[Client Submit Event] --> B[Event Journal]
    B --> C[Event Pool]
    C --> D[Event Certifier]
    D -- Valid --> E[Ordering Processor]
    E --> F[Block Builder]
    F -- Batch Full / Timeout --> G[Create Block and Run Configured Finalizer]
    G --> S[Sign Block Header]
    S --> H[Commit to Storage]
    H --> I[Commit Queue for Consumer]
```

## Các tính năng cốt lõi

### 1. Persistence & Durability (Tính bền vững)
Sự kiện được ghi đồng bộ vào Event Journal và fsync trước khi được đưa vào hàng đợi. Fsync luôn được bật và không thể tắt qua cấu hình. Khi khởi động lại, `Recovery` replay các entry journal và ghi các event đã khôi phục vào block storage trước khi Ordering Service hoạt động. Frame cuối chưa hoàn chỉnh trong journal đang hoạt động sẽ bị cắt bỏ trước khi mở file để ghi tiếp. Frame hoàn chỉnh nhưng chứa Arrow data lỗi khiến recovery thất bại; lỗi replay, chứng thực hoặc xử lý block giữ service ở trạng thái `MAINTENANCE` thay vì kích hoạt khi còn thiếu event.

Endpoint `GET /api/ledger/ready` trả HTTP 200 chỉ khi Ordering Service của mọi Sub-Chain đã đăng ký ở trạng thái `ACTIVE`; endpoint trả HTTP 503 khi bất kỳ service nào còn đang recovery hoặc ở trạng thái maintenance.

`TransactionJournal.log_event()` vẫn flush và fsync mỗi lần append thành công trước khi trả về. `read_since()` đọc record từ đĩa nhưng tái sử dụng lần sync thành công nếu device, inode, kích thước, thời gian sửa và thời gian thay đổi của file active khớp trạng thái đã sync. Mở/đóng writer, rotation và ghi thất bại làm mất hiệu lực trạng thái đó. Trạng thái chưa biết hoặc đã đổi yêu cầu fsync lại; lỗi đọc và sync được truyền lên. Đường dẫn active bị thay bằng inode khác bị từ chối. `flush()` tường minh vẫn sync mỗi lần gọi. Các quy tắc này giữ hợp đồng journal ghi nối tiếp với một owner; ACK đọc lại vẫn cần dữ liệu từ đĩa.

Stable ID trước hết kiểm tra trạng thái pending/batch/processed đang hoạt động và block storage. Với ID còn lại, `JournalEventLookup` quét lịch sử journal một lần khi dùng đầu tiên, sau đó chỉ đọc suffix sau cursor và lưu commitment kênh/nội dung nhỏ gọn. Index từ chối ID xung đột, kể cả các record trùng ID nhưng khác nội dung. Event cũ chỉ có trong journal cần payload để đưa lại vào hàng đợi vẫn đọc toàn bộ từ đĩa; index không giữ bản sao payload lịch sử. Journal tùy chỉnh hoặc thay thế không có lookup này giữ đường quét tương thích. Lịch sử tại cursor bị mất/cắt ngắn khiến thao tác bị từ chối. Quét ban đầu, liệt kê archive và metadata index vẫn tăng theo lịch sử được giữ; chưa bổ sung retention/compaction.

`lockdown()` chờ commit đang chạy hoàn tất, sau đó chặn commit tiếp theo và sự kiện mới cho đến khi gọi `resume()`. Sự kiện trong hàng đợi và batch đã cắt được giữ để xử lý khi resume; journal vẫn được giữ để phục hồi sau crash. Hoàn tất recovery không ghi đè `LOCKDOWN`, và `resume()` không thể kích hoạt lại service đã dừng.

### 2. Batching Strategy
Nhận vào hàng đợi chờ tối đa `enqueue_timeout` giây (mặc định `1.0`, cho phép giá trị lớn hơn zero đến `60`). Hàng đợi đầy hoặc shutdown gây `OrderingBackpressureError`, mang `event_id` và `journaled`. Event mới giữ chỗ trước khi ghi, nên bị từ chối tại bước này có `journaled=False`. Đưa lại event đã bền vững vào hàng đợi báo `journaled=True` và có thể thử lại cùng ID mà không ghi thêm entry. `POST /api/ledger/chains/{chain_name}/events` chuyển lỗi này thành HTTP 503 với các trường trên trong `detail`. Shutdown đánh thức producer đang chờ. Nhận event giữ condition của hàng đợi xuyên suốt fsync; độ trễ đĩa vì vậy cũng làm consumer chờ.

Để tối ưu hiệu năng, Ordering Service không đóng khối cho từng sự kiện đơn lẻ mà sử dụng chiến lược gom nhóm:
*   `OrderingService` khởi tạo trực tiếp mặc định dùng `batch_size=100` và `batch_timeout=2.0` giây.
*   Sub-Chain mặc định dùng `block_size=50` và `batch_timeout=1.0` giây; cấu hình tường minh có thể đổi cả hai.

### 3. Event Certification
`EventCertifier` chạy quy tắc xác thực do bên gọi thêm và kiểm tra các trường bắt buộc `entity_id`, `event` cùng timestamp hữu hạn. Sự kiện mới phải nằm trong khoảng 300 giây so với thời gian máy chủ; replay có thể cho phép timestamp cũ hơn. Helper chữ ký chỉ xác minh khi có sender/signature dạng chuỗi và payload details dạng chuỗi, trừ khi xác minh theo batch đã thành công. Nó cũng chạy kiểm tra ZK tùy chọn. Nó không gọi MSP hay `PolicyEngine`; ứng dụng phải thực thi quyền channel tại điểm tích hợp.

Certifier mặc định giữ 10.000 kết quả gần nhất (`EventCertifier(max_history=...)`). Event bị từ chối được xóa khỏi pending map. Sau khi kết quả bị loại khỏi cache, `get_event_status()` tra storage bền vững cho event đã commit và trả `ordered` không kèm kết quả certification; event bị từ chối từ lâu có thể trả `None`. Lịch sử này không phải bằng chứng certification bền vững.

### 4. Chi phí commit và liên chuỗi

`events_committed` và `average_batch_size` chỉ đếm sự kiện trong block đã lưu thành công. Latency dùng thời điểm nhận của các sự kiện đó; trạng thái đo thời gian của sự kiện còn chờ trong batch khác được giữ lại. `batch_size` của processor có thể khác `block_size` của block mà không đếm sự kiện chưa commit.

Gán block index, liên kết previous hash, ký và commit storage vẫn được tuần tự hóa theo từng Ordering Service. Xác minh chữ ký giữ batch thread pool và các kiểm tra certification hiện có. Coordinator 2PC giữ record pha bền vững và đọc lại trước khi commit participant; quyết định COMMIT không rõ kết quả vẫn ở trạng thái nghi vấn và không cho phép rollback. Giảm đọc lại journal không loại bỏ các ranh giới toàn vẹn này hay biến ACK nhận event thành block finality. Các chain độc lập có thể chia tải bằng journal owner riêng; gom block không gom ACK lưu bền vững của event.

## Ví dụ sử dụng

Cấp danh tính ký đầy đủ và khóa tin cậy đã được phê duyệt theo [Khởi động nhanh](../getting-started/quickstart.md), đồng thời chọn backend lưu trữ bền vững được hỗ trợ trước khi chạy ví dụ. `batch_size` giới hạn lượt thu thập của processor; `block_size` giới hạn sự kiện mỗi khối. ID trả về xác nhận đã tiếp nhận, còn `force_block_creation()` yêu cầu flush; đọc các khối đã lưu để xác nhận commit.

```python
import time
from hierachain.consensus.ordering.service import OrderingService

config = {
    "batch_size": 200,
    "block_size": 100,
    "batch_timeout": 1.5,
    "storage_dir": "data/ordering-example",
}
service = OrderingService(config=config)
try:
    event_id = service.receive_event(
        event_data={
            "entity_id": "CONTAINER-45",
            "event": "shipped",
            "timestamp": time.time(),
            "details": {"status": "shipped"},
        },
        channel_id="logistics_chain",
        submitter_org="ORG_SUPPLY",
    )
    service.force_block_creation()
finally:
    service.shutdown()
```

## Quyền sở hữu journal cục bộ {#local-journal-ownership}

Mỗi đường dẫn journal cục bộ chỉ có một instance/process sở hữu tại một thời điểm, được bảo vệ bằng POSIX advisory writer lock không chờ. Owner thứ hai không mở được journal cho đến khi owner đầu đóng hoặc thoát; guard này không biến journal thành log nhiều writer dùng chung. Các thread phải dùng chung một instance `TransactionJournal`. Writer độc lập cần node identity và thư mục lưu trữ riêng, hoặc volume riêng trên filesystem hỗ trợ POSIX lock và directory fsync. Mẫu PVC theo từng pod của Kubernetes StatefulSet giúp tách journal giữa các node. Cần nâng cấp mọi process dùng đường dẫn đó trước khi ghi format journal mới; phiên bản cũ chưa lấy writer lock.

## Liên quan

*   [Hệ thống ghi nhật ký (Journal)](../modules/error-mitigation.md)
*   [Cấu trúc Khối (Block)](../modules/core.md)
*   [Đồng thuận BFT](./bft_consensus.md)
