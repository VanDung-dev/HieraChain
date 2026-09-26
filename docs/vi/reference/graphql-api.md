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
