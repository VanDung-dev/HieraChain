---
title: GraphQL API Reference
description: Tài liệu tham chiếu các trường Query và Mutation cho mạng HieraChain GraphQL.
icon: material/graphql
---

# GraphQL API Reference

## Tham chiếu GraphQL API

Hệ thống cho phép tương tác trực tiếp qua cổng **GraphQL Endpoint**. Thư mục chứa cấu hình lõi: `hierachain/api/graphql/schema.py`. Cấu trúc GraphQL tối ưu cho việc truy vấn (query) chọn lọc đa dữ liệu mà không gọi quá nhiều tài nguyên mạng như REST.

### 1. Truy vấn (Queries)

Giao diện GraphQL Schema hỗ trợ trích xuất mạnh mẽ theo phân cấp Main-Chain và Sub-Chains.

**Lấy dữ liệu Block đơn lẻ:**

Truy vấn cục bộ một hàm Block duy nhất qua tên chuỗi và số `index`.

```graphql
query GetSingleBlock {
  block(chainName: "sub_chain_finance", blockIndex: 1) {
    index
    hash
    timestamp
    events {
      eventId
      eventType
    }
  }
}
```

**Lọc các đối tượng Lịch sử Sự kiện (Events) bằng tham số:**

Có thể filter nhanh gọn.

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

Cung cấp cái nhìn toàn vẹn với `chainStatus` (kiểm tra một chain) hoặc `allChains` (phản chiếu dashboard của mạng lưới).

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
