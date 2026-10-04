---
title: GraphQL API Reference
description: Tài liệu tham chiếu các trường Query và Mutation cho mạng HieraChain GraphQL.
icon: material/graphql
---

# GraphQL API Reference

GraphQL endpoint cung cấp các trường Query và Mutation được định nghĩa trong `hierachain/api/graphql/schema.py`. Client có thể chọn trường cần đọc trên Main-Chain và Sub-Chains.

### 1. Truy vấn (Queries)

Dùng các truy vấn sau để đọc block, event và trạng thái chain trên Main-Chain và Sub-Chains.

**Lấy dữ liệu Block đơn lẻ:**

Lấy block theo tên chain và `index`.

```graphql
query GetSingleBlock {
  block(chainName: "sub_chain_finance", blockIndex: 1) {
    index
    hash
    timestamp
    events {
      entityId
      eventType
    }
  }
}
```

**Lọc các đối tượng Lịch sử Sự kiện (Events) bằng tham số:**

Lọc event theo tên chain, loại event và giới hạn kết quả.

`blocks` và `events` trả tối đa 100 kết quả cho mỗi trường. Mặc định là 100; `limit: 0` trả danh sách rỗng. Giới hạn này cũng áp dụng khi `limit` được truyền qua biến GraphQL.

`events` đọc event đã finalize theo thứ tự block/row. Với chain native, `entityId` và `eventType` dùng index event; bộ lọc kết hợp chọn danh sách ứng viên nhỏ hơn. Giá trị không có trong index trả danh sách rỗng mà không quét block. Chỉ kết quả khớp mới được sao chép và chuyển thành GraphQL, bao gồm JSON details. `fromTimestamp` và `toTimestamp` bao gồm cả hai đầu và chấp nhận giá trị zero. Truy vấn chỉ theo thời gian lọc metadata Arrow theo batch trước khi giải mã payload; đường này vẫn có thể kiểm tra toàn bộ phần lịch sử còn lại khi không có event khớp. Danh sách ứng viên theo entity/type kết hợp bộ lọc thời gian chọn lọc cũng có thể cần kiểm tra các ứng viên còn lại.

```graphql
query FilterEvents {
  events(
    chainName: "main_chain", 
    limit: 10, 
    eventType: "user_registered"
  ) {
    entityId
    details
    signature
  }
}
```

**Đọc trang event tiếp theo:**

Mỗi event do `events` trả về có `cursor` dạng opaque. Truyền cursor cuối cùng vào `after` và giữ nguyên chain cùng các bộ lọc. Phân trang tiếp tục sau vị trí block/row đó, nên timestamp trùng nhau không làm lặp hay bỏ sót event. Truy vấn native dùng index tìm vị trí trong danh sách ứng viên; truy vấn native không lọc hoặc chỉ lọc thời gian bắt đầu tại block của cursor. Kết quả rỗng chỉ ra điểm kết thúc với các bộ lọc hiện tại. Cursor thuộc riêng từng chain; cursor sai định dạng hoặc khác chain tạo query error. Event đang pending không được trả về. Phân trang đọc trực tiếp chain append-only, không phải snapshot xuyên các request; event finalize về sau có thể xuất hiện trong trang tiếp theo. Trường `cursor` được điền bởi query gốc `events`, không phải `block.events`/`blocks.events` lồng nhau.

```graphql
query EventPage($after: String) {
  events(chainName: "main_chain", eventType: "user_registered", limit: 10, after: $after) {
    entityId
    eventType
    cursor
  }
}
```

Index theo loại dùng chung payload event đã cache với index entity hiện có và được dựng lại khi recovery chain. Nó thêm tham chiếu và vị trí row trong bộ nhớ; không tạo kho payload event riêng và không bỏ xác thực chữ ký. Chain bên ngoài không có index native dùng đường tương thích Arrow/list.

**Trạng thái Blockchain:**

Dùng `chainStatus` để xem một chain hoặc `allChains` để lấy trạng thái của mọi chain.

```graphql
query OverallSystem {
  allChains {
    chainName
    blockCount
    latestBlockHash
    status
  }
}
```

### 2. Tương tác Thay đổi (Mutations)

Schema GraphQL hỗ trợ tính năng Mutation dùng để truyền Event trực tiếp vào sub-chain hoặc main-chain.

**Tham số đầu vào (`AddEventInput`):**
- `chainName` (Required String)
- `entityId` (Required String)
- `eventType` (Required String)
- `details` (Optional String - dạng JSON string hóa)

**Ví dụ:**

```graphql
mutation CreateNewEvent {
  addEvent(event: {
    chainName: "sub_chain_logistics",
    entityId: "driver_443",
    eventType: "delivery_confirmed",
    details: "{\"status\": \"ok\", \"location\": \"zone-b\"}"
  }) {
    success
    blockIndex
    error
  }
}
```
