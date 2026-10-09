---
title: Python SDK Reference
description: Tài liệu tham chiếu và hướng dẫn cho lập trình viên tích hợp thư viện SDK của HieraChain (Sync & Async).
icon: material/language-python
---

# Python SDK Reference

Python SDK của HieraChain cung cấp client đồng bộ và bất đồng bộ để gửi event và đọc dữ liệu. Mã nguồn: `hierachain/sdk/client.py`.

### 1. Khởi tạo Client

SDK cung cấp 2 phương thức theo nhu cầu: **Chạy Đồng bộ (Sync)** và **Chạy Bất đồng bộ (Async)**.
Tất cả đều nhận Object `HieraChainClientConfig` làm profile.

```python
from hierachain.sdk.client import HieraChainClientConfig, HieraChainClient

# Client Configuration
config = HieraChainClientConfig(
    base_url="http://localhost:2661",
    timeout=10.0,
    api_key="your-api-key-here"
)
```

### Các phương thức chính

#### `submit_event(chain_name: str, event_data: dict[str, Any]) -> EventResult`

Gửi một sự kiện mới vào một sub-chain cụ thể.

*   **Ví dụ**: `client.submit_event("supply_chain", {"entity_id": "P001", "event_type": "check"})`

#### `get_block(chain_name: str, index_or_hash: str | int, resolve_cid: bool = False) -> dict`

Lấy thông tin chi tiết của một khối.

*   **resolve_cid**: Nếu `True`, SDK yêu cầu API giải quyết `details_cid`. API cần bật IPFS; nếu không, CID vẫn ở trạng thái chưa được giải quyết.

#### `get_node_status() -> NodeStatus`

Lấy trạng thái hệ thống từ API Admin. Trả về đối tượng chứa `version`, `uptime`, `chains_active`, v.v.

#### `trace_entity(entity_id: str, chain_name: str | None = None, resolve_cid: bool = False) -> EntityTrace`

Truy vết lịch sử của một thực thể qua các chuỗi.

Entity ID được percent-encode thành một path segment. `health_check()` dùng route API `/api/ledger/health`. Khi cấu hình `api_key`, client đồng bộ và bất đồng bộ không đi theo redirect của request đọc; phản hồi 3xx phát sinh `HieraChainAPIError` và `X-API-Key` không được gửi sang origin khác.

---

### Ví dụ: Lưu trữ Off-chain (IPFS)

Khi gửi sự kiện với dữ liệu lớn hoặc nhạy cảm, HieraChain khuyến khích sử dụng IPFS. SDK hỗ trợ truy vấn minh bạch:

```python
# 1. Submit event with CID from IPFS (uploaded beforehand)
client.submit_event("supply_chain", {
    "entity_id": "LARGE-DOC-001",
    "event_type": "document_notarization",
    "details_cid": "QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco",
    "details_nonce": "00112233445566778899aabb"
})

# 2. Query and auto-decrypt data
block = client.get_block("supply_chain", 100, resolve_cid=True)
# The 'details' field in the event will contain data loaded from IPFS
```

### Xử lý lỗi (Error Handling)

SDK định nghĩa các ngoại lệ chuyên biệt để ứng dụng có thể xử lý logic nghiệp vụ:

```python
from hierachain.sdk.exceptions import (
    CircuitOpenError,     # When Circuit Breaker is activated
    HieraChainAPIError,   # HTTP errors, with status_code
    LockdownError,        # When system is in security lockdown mode
    ServiceUnavailableError # When the server returns HTTP 503
)

try:
    client.submit_event(...)
except LockdownError:
    # Logic to handle when system is temporarily halted for maintenance/security
    pass
```

Với đoạn xử lý đồng bộ, mở client bằng context manager:

```python
with HieraChainClient(config) as client:
    health = client.health_check()
    print("Healthy:", health)
```

Với web server hoặc ứng dụng FastAPI, dùng client bất đồng bộ:
```python
from hierachain.sdk.client import HieraChainAsyncClient

async def read_node_status(config: HieraChainClientConfig) -> None:
    async with HieraChainAsyncClient(config) as async_client:
        status = await async_client.get_node_status()
        print("Network:", status.chains_active)
```

### 2. Các tính năng Mạng lưới cốt lõi (Resilience)

SDK thử lại khi gặp lỗi mạng và dùng circuit breaker để giới hạn request khi API không khả dụng:

#### a. Tự động phục hồi (Exponential Backoff Retry)
Request đọc (`GET`) thử lại khi lỗi truyền tải hoặc HTTP 5xx, với thời gian chờ `initial_delay * (backoff_multiplier ^ attempt)` và tối đa `max_retries = 5` lần theo mặc định. Phản hồi non-2xx được trả về cho client sẽ phát sinh `HieraChainAPIError` kèm `status_code`; phản hồi 3xx và 4xx được trả về sẽ không được thử lại. Client đồng bộ và bất đồng bộ đi theo redirect với request `GET`, `HEAD` và `OPTIONS` không xác thực. Khi cấu hình `X-API-Key`, các method này tắt redirect; request `POST` cũng tắt redirect. Request ghi chỉ gửi một lần, kể cả khi timeout hoặc nhận 503, vì server chưa có hợp đồng idempotency.

#### b. Chốt kiểm tra mạch (Circuit Breaker)
Hoạt động fail-fast (ưu tiên báo lỗi sớm):
- **CLOSED**: Trạng thái mạng ổn định, toàn bộ request cho pass qua API.
- **OPEN**: Nếu phát hiện 5 lỗi truyền tải hoặc HTTP 5xx liên tiếp (`circuit_failure_threshold`), circuit mở và báo `CircuitOpenError` cho đến khi hết thời gian chờ 30 giây (`circuit_recovery_timeout`).
- **HALF_OPEN**: Sau thời gian chờ, chỉ một request được nhận làm probe. Probe không được thử lại; thất bại sẽ mở circuit, thành công sẽ đóng circuit.

#### c. Quản lý trạng thái kẹt (Lockdown & 503)
Nếu Node server trả header `X-Lockdown-Mode: true` hoặc HTTP `503 Service Unavailable`, SDK phát sinh `LockdownError` hoặc `ServiceUnavailableError`. Request đọc có thể thử lại trước; POST thì không.

### 3. Tương tác Dữ liệu

```python
# Submit Event for transaction
result = client.submit_event("supply_chain", {
    "entity_id": "user_sysadmin",
    "event_type": "update_config"
})
print("Event accepted, event_id:", result.event_id)

# Get Block by hash
block = client.get_block("supply_chain", "8f2a9d...")
```

### Truyền JSON

Cả hai SDK client mã hóa body request và đọc JSON response qua helper dùng `json` chuẩn, với UTF-8 và `Content-Type: application/json` mặc định, đồng thời tôn trọng header đã cấu hình. Số không hữu hạn bị từ chối trước khi gửi; response chứa `NaN`, `Infinity` hoặc số vượt khoảng biểu diễn float bị từ chối. Số nguyên Python lớn hơn 64 bit được giữ nguyên mà không chuyển thành float, trong giới hạn chuyển đổi số nguyên của Python. JSON response không hợp lệ đi qua xử lý lỗi và retry hiện có. Request thay đổi dữ liệu vẫn không tự retry.
