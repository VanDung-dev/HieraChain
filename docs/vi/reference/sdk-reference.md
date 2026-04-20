---
title: Python SDK Reference
description: Tài liệu tham chiếu và hướng dẫn cho lập trình viên tích hợp thư viện SDK của HieraChain (Sync & Async).
icon: material/language-python
---

# Python SDK Reference

Thư viện Python SDK của HieraChain thiết kế mô-đun mạnh mẽ giúp các Developer đẩy giao dịch cũng như thực hiện đọc dữ liệu vô cùng nhanh gọn trong môi trường Python. Mã nguồn đặt tại: `hierachain/sdk/client.py`.

### 1. Khởi tạo Client

SDK cung cấp 2 phương thức theo nhu cầu: **Chạy Đồng bộ (Sync)** và **Chạy Bất đồng bộ (Async)**.
Tất cả đều nhận Object `HieraChainClientConfig` làm profile.

```python
from hierachain.sdk.client import HieraChainClientConfig, HieraChainClient

# Cấu hình Client
config = HieraChainClientConfig(
    base_url="http://localhost:2661",
    timeout=10.0,
    api_key="your-api-key-here"
)
```

### Các phương thức chính

#### `submit_event(chain_name: str, event_data: dict[str, Any]) -> EventResult`

Gửi một sự kiện mới vào một sub-chain cụ thể.

*   **Ví dụ**: `client.submit_event("supply_chain", {"entity_id": "P001", "event": "check"})`

#### `get_block(chain_name: str, index_or_hash: str | int, resolve_cid: bool = False) -> dict`

Lấy thông tin chi tiết của một khối.

*   **resolve_cid**: Nếu `True`, SDK sẽ tự động tải dữ liệu từ IPFS cho các sự kiện có `details_cid`.

#### `get_node_status() -> NodeStatus`

Lấy trạng thái hệ thống từ API v3. Trả về đối tượng chứa `version`, `uptime`, `chains_active`, v.v.

#### `trace_entity(entity_id: str, chain_name: str = None, resolve_cid: bool = False) -> EntityTrace`

Truy vết lịch sử của một thực thể qua các chuỗi.

---

### Ví dụ: Lưu trữ Off-chain (IPFS)

Khi gửi sự kiện với dữ liệu lớn hoặc nhạy cảm, HieraChain khuyến khích sử dụng IPFS. SDK hỗ trợ truy vấn minh bạch:

```python
# 1. Gửi sự kiện với CID từ IPFS (đã upload trước đó)
client.submit_event("supply_chain", {
    "entity_id": "LARGE-DOC-001",
    "event": "document_notarization",
    "details_cid": "QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco",
    "details_nonce": "12345"
})

# 2. Truy vấn và tự động giải mã dữ liệu
block = client.get_block("supply_chain", 100, resolve_cid=True)
# Trường 'details' trong event sẽ chứa dữ liệu đã tải từ IPFS
```

### Xử lý lỗi (Error Handling)

SDK định nghĩa các ngoại lệ chuyên biệt để ứng dụng có thể xử lý logic nghiệp vụ:

```python
from hierachain.sdk.exceptions import (
    CircuitOpenError,     # Khi Circuit Breaker được kích hoạt
    LockdownError,        # Khi hệ thống đang trong chế độ phong tỏa bảo mật
    ServiceUnavailableError # Khi lỗi kết nối hoặc server quá tải
)

try:
    client.submit_event(...)
except LockdownError:
    # Logic xử lý khi hệ thống tạm ngừng hoạt động để bảo trì/bảo mật
    pass
```

# Chạy dạng context manager
with HieraChainClient(config) as client:
    health = client.health_check()
    print("Healthy:", health)
```

**Sử dụng Async (Phù hợp Web Server/FastAPI):**
```python
from hierachain.sdk.client import HieraChainAsyncClient

async with HieraChainAsyncClient(config) as async_client:
    status = await async_client.get_chain_status()
    print("Mạng lưới:", status.block_height)
```

### 2. Các tính năng Mạng lưới cốt lõi (Resilience)

SDK được trang bị tận răng các cơ chế phục hồi và đảm bảo thông lượng để chống spam / quá tải máy chủ Node:

#### a. Tự động phục hồi (Exponential Backoff Retry)
Nếu xảy ra rớt mạng, SDK tự tính toán khoảng dừng nghỉ `initial_delay * (backoff_multiplier ^ attempt)`. Thay vì sập toàn hệ thống, truy vấn sẽ liên tục được lặp lại (theo mặc định cấu hình `max_retries = 5`).

#### b. Chốt kiểm tra mạch (Circuit Breaker)
Hoạt động fail-fast (ưu tiên báo lỗi sớm):
- **CLOSED**: Trạng thái mạng ổn định, toàn bộ request cho pass qua API.
- **OPEN**: Nếu phát hiện 5 lỗi truyền tải liên tục (`circuit_failure_threshold`), rơ-le ngắt, ngay lập tức báo `CircuitOpenError` cho đến lúc hết khoảng timeout 30s (`circuit_recovery_timeout`).
- **HALF_OPEN**: Khi đủ thời gian làm mát, nó tự test một packet. Nếu lỗi sẽ Open lại, nếu tốt sẽ phục hồi đóng mạch về Closed.

#### c. Quản lý trạng thái kẹt (Lockdown & 503)
Nếu Node server báo trả về Header `X-Lockdown-Mode: true` (Hệ thống đang bị tấn công DDoD / bảo trì thủ công) hoặc nhận HTTP `503 Service Unavailable`, SDK sẽ không loay hoay Spam Retries (gây quá tải). Mã lỗi sẽ tự phơi bày qua Class Exception định danh riêng biệt `LockdownError` và `ServiceUnavailableError`. 

### 3. Tương tác Dữ liệu

```python
# Đẩy Submit Event cho Giao dịch
result = client.submit_event("main_chain", {
    "entity_id": "user_sysadmin",
    "event": "update_config"
})
print("Đẩy thành công vào block, Message ID:", result.event_id)

# Lấy Block bằng hash
block = client.get_block(block_id="8f2a9d...")
```
