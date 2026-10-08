---
title: "Core Module"
description: "Các cấu trúc nền tảng của sổ cái: Block, Blockchain, Merkle Tree và cache trong bộ nhớ."
icon: material/cube
---

# Core Module (`hierachain/core/*`)

## 1. Tổng quan

Module `core` chứa các cấu trúc dữ liệu nền tảng của sổ cái. Khối lưu trữ các sự kiện trong bảng Apache Arrow giúp lọc dữ liệu trong bộ nhớ với tốc độ cao và tính toán mã băm xác định. Cây Merkle mật mã cung cấp bằng chứng chứng minh sự kiện có mặt trong khối. `AdvancedCache` cung cấp cache trong bộ nhớ theo instance, được `KeyManager` sử dụng để tra cứu khóa và quyền.

## 2. Các thành phần nền tảng

Toàn bộ thành phần cốt lõi nằm tại `hierachain/core/`.

### 2.1 Khối (`block.py`)

* Lưu trữ bản ghi sự kiện trong một `pyarrow.Table`.
* Truy vấn các trường sự kiện qua biểu thức tính toán của Arrow thay vì vòng lặp Python.
* Tính toán mã băm khối và Merkle root xác định.
* Dùng dữ liệu Arrow làm nguồn cho cả xác minh và lưu trữ. `to_event_list()` và `to_dict()` trả snapshot sự kiện độc lập; sửa list đầu vào hoặc snapshot xuất ra không làm thay đổi khối.

### 2.2 Chuỗi khối (`blockchain.py`)

* Quản lý trạng thái chuỗi, khởi tạo khối nguyên thủy (genesis) và hàng đợi sự kiện đang chờ.
* Thực thi cơ chế khóa an toàn đa luồng kèm phát hiện bế tắc (deadlock).
* Duy trì chỉ mục thực thể phục vụ tra cứu lịch sử sự kiện nhanh chóng.

### 2.3 Cây Merkle (`merkle_tree.py`)

* Xây dựng cây Merkle nhị phân từ mã băm các sự kiện.
* Tạo bằng chứng bao hàm (inclusion proof) phục vụ kiểm toán.
* Xác thực Merkle root giữa các tầng chuỗi trong kiến trúc phân cấp.

### 2.4 Bộ nhớ đệm (`cache.py`)

* Cung cấp bộ nhớ đệm trong RAM với các chính sách dọn dẹp LRU, LFU, FIFO và TTL.
* `KeyManager` sử dụng bộ nhớ đệm này cho các tra cứu khóa và quyền.

TTL được xử lý khi dùng cache: đọc từ chối entry hết hạn; ghi khi đầy, lấy thống kê, liệt kê key và `len(cache)` xóa chúng. `cleanup_ttl()` vẫn cho phép dọn chủ động. Cache không tạo thread dọn riêng, nên cache đã bỏ có thể được thu hồi. Entry hết hạn trong cache không hoạt động có thể còn chiếm bộ nhớ đến thao tác tiếp theo hoặc khi cache được thu hồi.

## 3. Cấu trúc bộ nhớ và lưu trữ của Block

Mỗi đối tượng `Block` đóng gói một bảng Arrow cùng metadata có cấu trúc:

1. Bố cục nhị phân gọn gàng giảm tải bộ nhớ cho các đối tượng Python.
2. Thao tác lọc theo `entity_id` và `event` chạy trực tiếp trên nhân C++ của Arrow.
3. Dữ liệu nhị phân tuần tự hóa bảo đảm tính ổn định của mã băm trên mọi nền tảng.

```python
# Query events by entity on a Block instance
entity_events = block.get_events_by_entity("PROD-123")
```

## 4. An toàn đa luồng và cơ chế khóa

Lớp `Blockchain` điều phối truy cập đồng thời thông qua cơ chế khóa có giới hạn thời gian:

* Theo dõi thời gian giữ khóa với ngưỡng cấu hình linh hoạt.
* Hàm `safe_lock(timeout)` ngăn chặn tình trạng treo luồng khi xảy ra tranh chấp ghi đồng thời.
* Cơ chế callback thông báo cảnh báo tắc nghẽn lên tầng giám sát hệ thống.

## 5. Thực thi đồng thời

Các tác vụ xác thực mật mã và đồng bộ liên chuỗi chạy đồng thời thông qua các worker `ThreadPoolExecutor` do môi trường thực thi quản lý. Quá trình băm và kiểm tra chữ ký được mở rộng trên nhiều lõi CPU trong khi vẫn bảo toàn thứ tự khối tuần tự.

## Liên quan

* [Kiến trúc phân cấp](../architecture/hierarchy.md)
* [Storage Module](./storage.md)
* [Tổng quan bảo mật](./security.md)

## Mapping của cache và timestamp

`AdvancedCache` triển khai `MutableMapping` trên cùng kho dữ liệu dùng cho eviction. Duyệt cache, `items()`, `values()`, `update()`, `pop()`, `setdefault()` và `dict(cache)` dùng cùng entries với `get()` và `set()`. `None` là giá trị hợp lệ; index khóa thiếu hoặc đã hết hạn gây `KeyError`. `get_keys()` trả snapshot khóa còn hiệu lực. Cache không còn kế thừa `dict`; consumer nên kiểm tra `MutableMapping`. Các khóa được chuẩn hóa thành chuỗi.

Timestamp block được truyền rõ là `0` được giữ nguyên khi serialize và kiểm tra hash. Chỉ `None` yêu cầu lấy thời gian hiện tại.

### Serialization JSON

`hierachain.serialization` dùng `json` chuẩn của Python. Hàm ghi từ chối số không hữu hạn thay vì chuyển thành `null`; hàm đọc từ chối `NaN`, `Infinity` và số vượt khoảng biểu diễn float. Số nguyên giữ độ chính xác của số nguyên Python trong giới hạn chuyển đổi đã cấu hình. Đầu ra UTF-8 dùng dạng gọn; payload digest và chữ ký sắp xếp khóa object. Object không được hỗ trợ yêu cầu serializer được cấu hình rõ ở những thành phần đã hỗ trợ cơ chế này.

Digest request BFT giữ định dạng thư viện chuẩn hiện có. Các hash khác, event ID, Merkle root, payload chữ ký, AAD metadata mã hóa và nội dung IPFS tải lên mới có thể khác serializer trước khi cách biểu diễn số khác, dù giá trị sau giải mã bằng nhau. Nội dung JSON cũ vẫn đọc được, nhưng root và chữ ký lịch sử không tự được viết lại hay chấp nhận bằng encoder fallback. Cần nâng cấp các node đồng bộ và dùng ledger mới cho nhánh tái cấu trúc này, hoặc thực hiện migration và xác minh lịch sử cũ rõ ràng trước khi sử dụng. Giá trị thập phân cần tính toán chính xác và định danh lớn dùng chung với client có giới hạn độ chính xác cần schema chuỗi hoặc số nguyên rõ ràng.
