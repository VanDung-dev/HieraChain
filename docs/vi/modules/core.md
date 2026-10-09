---
title: "Core Module"
description: "Các cấu trúc nền tảng của sổ cái: Block, Blockchain, Merkle Tree và cache trong bộ nhớ."
icon: material/cube
---

# Module Core (`hierachain/core/*`)

## Tổng quan

Module `core` chứa khối, chuỗi cơ sở, phép tính Merkle root và cache trong bộ nhớ. Khối dùng bảng Apache Arrow để lưu và lọc sự kiện. Byte JSON chuẩn hóa của sự kiện quyết định Merkle root; header chuẩn hóa quyết định hash khối. `KeyManager` dùng `AdvancedCache` để tra cứu khóa và quyền.

## Các thành phần

Toàn bộ thành phần cốt lõi nằm tại `hierachain/core/`.

### Khối (`block.py`)

* Lưu trữ bản ghi sự kiện trong một `pyarrow.Table`.
* Lọc `entity_id` và `event` bằng biểu thức tính toán của Arrow, rồi giải mã payload của các sự kiện khớp thành dictionary Python.
* Tính toán mã băm khối và Merkle root xác định.
* Dùng dữ liệu Arrow làm nguồn cho cả xác minh và lưu trữ. `to_event_list()` và `to_dict()` trả snapshot sự kiện độc lập; sửa list đầu vào hoặc snapshot xuất ra không làm thay đổi khối.

### Chuỗi khối (`blockchain.py`)

* Quản lý trạng thái chuỗi, khởi tạo khối nguyên thủy (genesis) và hàng đợi sự kiện đang chờ.
* Dùng `threading.RLock` khi thay đổi chuỗi và truy vấn qua chỉ mục.
* Duy trì chỉ mục thực thể và loại sự kiện để tra cứu lịch sử.

Khởi tạo chuỗi cần danh tính ký cố định và khóa công khai tương ứng đã được người vận hành phê duyệt. Khối genesis được ký bằng danh tính đó. `add_event()` sao chép và xác thực sự kiện, thêm timestamp nếu thiếu, rồi trả ID cho sự kiện trong hàng đợi chờ. `finalize_block()` ký và xác thực khối trước khi thêm vào chuỗi trong bộ nhớ và xóa các sự kiện đã ghi khỏi hàng đợi chờ.

Lớp cơ sở không có worker tự gom lô, nhật ký sự kiện hay storage adapter. Các thành phần cấp cao cung cấp ordering và lưu trữ bền vững; xem [Dịch vụ ordering](../consensus/ordering.md). `Blockchain.add_block()` kiểm tra tính toàn vẹn và chữ ký tin cậy qua `BlockVerifier`; kiểm tra đồng thuận thuộc các triển khai MainChain/SubChain.

### Cây Merkle (`merkle_tree.py`)

* Xây dựng cây Merkle nhị phân từ mã băm các sự kiện.
* Trả root đã tính qua `get_root()`.
* Giữ nguyên nút không có cặp khi đưa lên tầng tiếp theo. Cặp nút được băm theo `SHA256(b"\x01" + left.encode() + right.encode())`, trong đó mỗi nút con là chuỗi hash dạng hex.

Cây rỗng có root là hash SHA-256 của byte rỗng; cây có một lá dùng chính lá đó làm root. `MerkleTree` không có phương thức tạo hay xác minh inclusion proof. `BlockVerifier.verify_merkle_root()` tính lại root từ sự kiện của khối và so sánh với root đã lưu. Tầng phân cấp thực hiện kiểm tra anchor giữa các chuỗi.

### Bộ nhớ đệm (`cache.py`)

* Cung cấp bộ nhớ đệm trong RAM với các chính sách dọn dẹp LRU, LFU, FIFO và TTL.
* `KeyManager` sử dụng bộ nhớ đệm này cho các tra cứu khóa và quyền.

`AdvancedCache(max_size=10000, eviction_policy="lru")` đặt dung lượng và chính sách loại bỏ theo từng instance. Thời hạn được đặt cho từng entry qua `set(key, value, ttl=...)`. Chính sách loại bỏ `ttl` ưu tiên xóa entry hết hạn và dùng LRU khi không có entry nào hết hạn.

TTL được xử lý khi dùng cache: đọc từ chối entry hết hạn; ghi khi đầy, lấy thống kê, liệt kê key và `len(cache)` xóa chúng. `cleanup_ttl()` vẫn cho phép dọn chủ động. Cache không tạo thread dọn riêng, nên cache đã bỏ có thể được thu hồi. Entry hết hạn trong cache không hoạt động có thể còn chiếm bộ nhớ đến thao tác tiếp theo hoặc khi cache được thu hồi.

## Cấu trúc bộ nhớ và lưu trữ của Block

Bảng Arrow có các cột metadata để lọc và cột nhị phân `data` chứa byte JSON chuẩn hóa của sự kiện. `to_event_list()` giải mã các byte đó để giữ kiểu JSON và details lồng nhau. Xem [Mô hình dữ liệu](../reference/data-models.md) để biết lược đồ bảy cột.

`calculate_hash()` băm `index`, `timestamp`, `previous_hash`, `nonce`, `merkle_root` và `creator_id`. Chữ ký và bảng sự kiện không phải các trường header được băm trực tiếp; Merkle root gắn byte sự kiện với header.

```python
# Query events by entity on a Block instance
entity_events = block.get_events_by_entity("PROD-123")
```

## Cơ chế khóa của Blockchain

`Blockchain.lock` là khóa tái nhập, cho phép phương thức như `finalize_block()` gọi phương thức khác cũng dùng khóa trong cùng một luồng. Các khối `with self.lock` nội bộ chờ lấy khóa mà không đặt timeout. Lớp này không có `safe_lock(timeout)`, bộ phát hiện deadlock hay callback báo tranh chấp khóa. `get_events_by_filter()` duyệt chuỗi mà không lấy khóa; bên gọi cần phối hợp truy cập nếu muốn có góc nhìn nhất quán trong lúc ghi đồng thời.

## Thực thi

Phép tính hash khối và Merkle root chạy đồng bộ. Core không tạo worker pool. `verify_batch_signatures()` trong `hierachain/security/security_utils.py` dùng thread pool dùng chung cho lô từ bốn chữ ký; cơ chế này không làm phép băm khối hay kiểm tra toàn vẹn toàn chuỗi chạy song song.

## Liên quan

* [Kiến trúc phân cấp](../architecture/hierarchy.md)
* [Storage Module](./storage.md)
* [Tổng quan bảo mật](./security.md)

## Mapping của cache và timestamp

`AdvancedCache` triển khai `MutableMapping` trên cùng kho dữ liệu dùng cho eviction. Duyệt cache, `items()`, `values()`, `update()`, `pop()`, `setdefault()` và `dict(cache)` dùng cùng entries với `get()` và `set()`. `None` là giá trị hợp lệ; index khóa thiếu hoặc đã hết hạn gây `KeyError`. `get_keys()` trả snapshot khóa còn hiệu lực. Bên gọi nên dùng giao diện `MutableMapping`. Các khóa được chuẩn hóa thành chuỗi.

Timestamp block được truyền rõ là `0` được giữ nguyên khi serialize và kiểm tra hash. Chỉ `None` yêu cầu lấy thời gian hiện tại.

### Serialization JSON

`hierachain.serialization` dùng `json` chuẩn của Python. Hàm ghi từ chối số không hữu hạn thay vì chuyển thành `null`; hàm đọc từ chối `NaN`, `Infinity` và số vượt khoảng biểu diễn float. Số nguyên giữ độ chính xác của số nguyên Python trong giới hạn chuyển đổi đã cấu hình. Đầu ra UTF-8 dùng dạng gọn; payload digest và chữ ký sắp xếp khóa object. Object không được hỗ trợ yêu cầu serializer được cấu hình rõ ở những thành phần đã hỗ trợ cơ chế này.

Mã hóa chuẩn hóa là một phần của quy tắc toàn vẹn cho hash, event ID, Merkle root, chữ ký, AAD metadata mã hóa và nội dung IPFS tải lên. Thay đổi cách encoder biểu diễn số có thể làm các byte này khác nhau dù giá trị sau giải mã bằng nhau. Root và chữ ký lịch sử không tự được viết lại hay chấp nhận qua encoder fallback. Cần phối hợp thay đổi encoder giữa các node và xác minh lịch sử hiện có trước khi migration. Digest request BFT cũng dùng helper `dumps_canonical_json()` chung. Giá trị thập phân cần tính toán chính xác và định danh lớn dùng chung với client có giới hạn độ chính xác cần schema chuỗi hoặc số nguyên rõ ràng.
