---
title: "Cấu hình"
description: "Biến môi trường và thiết lập trong hierachain/config/settings.py; cách override và giá trị mặc định."
icon: material/tune
---

# Cấu hình hệ thống

## Mục đích

Trang này liệt kê các thiết lập chính của HieraChain, giá trị mặc định và cách override. Mọi giá trị đều định nghĩa trong `hierachain/config/settings.py` và đọc từ biến môi trường hoặc hằng số.

## Phạm vi

* Áp dụng cho API, CLI và các thành phần Sub-Chain/Main Chain chạy trong cùng tiến trình Python.
* Không bao gồm phần triển khai hạ tầng như Kubernetes manifest hay reverse proxy. Chỉ bao gồm biến mà HieraChain đọc trực tiếp.

## Cách truy cập cấu hình trong mã

```python
from hierachain.config.settings import settings

print(settings.API_HOST, settings.API_PORT)
print(settings.CONSENSUS_TYPE)
print(settings.AUTH_ENABLED)
```

## Biến môi trường và mặc định

### Môi trường chạy

* `HRC_ENV` chọn lớp cấu hình; dùng `ENV` khi `HRC_ENV` không được đặt hoặc để trống. Nếu đặt cả hai, `HRC_ENV` được ưu tiên. Giá trị không phân biệt chữ hoa/thường và bỏ khoảng trắng hai đầu: `dev` / `development`, `test` / `testing` hoặc `production` / `prod` / `product` (mặc định development khi cả hai để trống). Giá trị khác sẽ gây lỗi thay vì chọn development.
* `.env` được nạp trước khi định nghĩa các thiết lập đọc biến môi trường. Đặt `HRC_ENV_FILE` để dùng tệp dotenv khác. Giá trị đã có trong môi trường tiến trình được ưu tiên hơn giá trị trong tệp.

### API

* `HRC_API_HOST` (mặc định: `localhost` ở dev, `127.0.0.1` ở production)
* `HRC_API_PORT` (mặc định: `2661`)
* `API_VERSION` (hằng số: `ledger`; các route business/admin có tiền tố riêng)

### Đồng thuận và blockchain

* `HRC_CONSENSUS_TYPE` / `HRC_MAINCHAIN_CONSENSUS` (alias, mặc định: `proof_of_authority`; hỗ trợ: `proof_of_authority`, `proof_of_federation`)

* `HRC_BLOCK_INTERVAL` (mặc định `0.0` giây): giãn cách bổ sung PoA; khi dương, validation dùng ít nhất nửa interval. Không điều khiển interval PoF. Batching Sub-Chain mặc định vẫn dùng 50 event và timeout 1 giây.
* `CONSENSUS_FEDERATION_CONFIG`: cấu hình federation (min_validators: 3, block_interval: 5.0). Đây là thuộc tính Settings, không phải biến môi trường.
* `VALIDATOR_TIMEOUT` (mặc định: `30` giây). Thuộc tính Settings.
* `BFT_ENABLED` (mặc định: `True`), `BFT_FAULT_TOLERANCE` (mặc định: `1`), `BFT_NODE_COUNT` (mặc định: `4`). Là thuộc tính Settings (không có biến môi trường `HRC_BFT_ENABLED`).
* Giới hạn block: `BLOCK_SIZE_LIMIT` (mặc định: `1000` events/block ở dev, `10` ở test)
* `PROOF_SUBMISSION_INTERVAL` (mặc định: `300` giây ở dev, `10` ở test)
* `HRC_VALIDATOR_IDENTITY`: đường dẫn tệp danh tính nút đầy đủ (mặc định: `validator_key.json`). Tệp phải có ID nút/MSP, khóa ký riêng/công khai và khóa truyền tải riêng/công khai; đầu ra hai trường của `hrc key generate` chưa đủ. Xem [Khởi động nhanh](../getting-started/quickstart.md).
* `HRC_BLOCK_TRUSTED_KEYS_FILE`: file JSON bắt buộc ánh xạ `creator_id` tới public key Ed25519 dạng hex. Khóa node trong `HRC_VALIDATOR_IDENTITY` phải khớp mục tương ứng. Thiếu file hoặc khóa không khớp sẽ chặn chain/API khởi động. Mọi block, kể cả genesis, đều cần chữ ký tin cậy. Chain cũ có block không ký cần được di chuyển dữ liệu trước khi khởi động.

### Lưu trữ và cache

* `HRC_STORAGE_BACKEND` / `DATABASE_URL` / `HRC_DATABASE_URL` (mặc định: `postgres` ở development và production, `memory` ở test; giá trị được nhận diện: `sqlite`, `postgres` / `postgresql`, `redis`, `memory`). Backend không hợp lệ sẽ chặn API khởi động và khởi tạo chain storage. `HierarchyManager` cũng từ chối `redis` khi khởi động vì chưa lưu bền vững block đã ký; dùng `sqlite` hoặc `postgres` cho ledger bền vững. Redis vẫn dùng được trong các adapter riêng cho indexing, trạng thái xác thực và rate limit.
* Trong production, khi backend được chọn là PostgreSQL, cần đặt rõ `DATABASE_URL` hoặc `HRC_DATABASE_URL`. API từ chối URL fallback local có sẵn khi khởi động; bước này không kiểm tra kết nối tới database.
* `DATABASE_URL` được ưu tiên khi có giá trị. Nếu rỗng hoặc chỉ có khoảng trắng, hệ thống dùng `HRC_DATABASE_URL`.
* Nếu PostgreSQL không khả dụng, khởi tạo storage của chain sẽ thất bại. Đặt `HRC_STORAGE_BACKEND=sqlite` để chọn SQLite tường minh.
* Cache theo instance: `AdvancedCache(max_size=10000, eviction_policy="lru")` nhận cấu hình riêng; `set(key, value, ttl=...)` đặt TTL cho entry. `KeyManager` dùng cache khóa/quyền riêng và `cache_ttl` (mặc định: `300` giây). `block_cache_size` của Ordering vẫn là key cấu hình service (mặc định: `100`), không phải thuộc tính `Settings`.
* Cấu hình không dùng đã bỏ: `ADVANCED_CACHING_ENABLED`, `BLOCK_CACHE_SIZE`, `EVENT_CACHE_SIZE`, `ENTITY_CACHE_SIZE`, `BLOCK_CACHE_POLICY`, `EVENT_CACHE_POLICY`, `ENTITY_CACHE_POLICY`, `ENTITY_TTL` và `hierachain.core.cache.DEFAULT_CACHE_CONFIG`. Các tên này chưa từng điều khiển cache runtime; bỏ import/truy cập trực tiếp và cấu hình instance cache hoặc service thực sự sử dụng chúng.
* DB: `DATABASE_URL` (fallback khi development: `postgresql://hiera:hiera@localhost:5432/hierachain`; không dựa vào fallback này trong production)
* Redis: `HRC_REDIS_HOST` hoặc `REDIS_HOST` (`localhost`), `HRC_REDIS_PORT` hoặc `REDIS_PORT` (`6379`), `REDIS_DB` (`0`). Tên có tiền tố HRC được ưu tiên.

### IPFS (lưu trữ off-chain)

* `HRC_IPFS_ENABLED` (mặc định: `false`). Bật hoặc tắt IPFS cho dữ liệu lớn.
* `HRC_IPFS_HOST` (mặc định: `/ip4/127.0.0.1/tcp/5001`). Địa chỉ daemon IPFS.
* `HRC_IPFS_AUTO_PIN` (mặc định: `true`). Pin dữ liệu sau khi upload để không bị garbage collect.
* `HRC_IPFS_TIMEOUT` (mặc định: `120` giây). Thời gian chờ tối đa cho thao tác IPFS.
* `HRC_IPFS_ENCRYPTION_KEY`: bắt buộc với factory IPFS từ môi trường, gồm đúng 64 ký tự hex (32 byte). Giá trị thiếu hoặc không hợp lệ gây `IPFSError`. Các nút đọc cùng đối tượng đã mã hóa cần cùng khóa, nonce và metadata AAD; phải giữ khóa qua các lần khởi động lại.

### Xử lý song song và tài nguyên

* `HRC_EVENT_POOL_MAX_SIZE` (mặc định: `10000`) giới hạn hàng đợi event của ordering.
* `HRC_RAM_CRITICAL_THRESHOLD` (mặc định: `95.0` %) được khai báo trong settings nhưng chưa có consumer runtime trong ordering hoặc storage.

### Bảo mật và authentication

* Authentication: `HRC_AUTH_ENABLED` (mặc định `false` ở dev/test và bắt buộc `true` ở production; đặt tường minh thành `false` sẽ chặn production khởi động)
* `HRC_API_KEYS_FILE`: bắt buộc trong production. Đường dẫn tới file JSON chứa key không rỗng, đọc được; mỗi key dài ít nhất 32 ký tự và có `user_id` cùng danh sách `permissions` không rỗng. File được đọc khi tạo API app; thay đổi map key vẫn cần tạo lại từng node hoặc khởi động lại từng tiến trình chạy trực tiếp.
* `HRC_API_KEY_REVOCATIONS_DB` (mặc định: `data/api_key_revocations.sqlite3`): lưu bền vững API key đã thu hồi và brute-force lockout cục bộ cho API production. Mọi worker trên một host phải dùng chung file ghi được và bền vững này.
* `HRC_AUTH_STATE_REDIS_URL` (tùy chọn): khi đặt, API key revocation và brute-force lockout dùng cùng Redis giữa các host. Cần cấu hình Redis persistence nếu revocation phải tồn tại sau khi Redis khởi động lại. Lỗi backend sẽ từ chối xác thực thay vì dùng trạng thái cục bộ.
* `HRC_API_KEY_LOCATION` (`header`), `HRC_API_KEY_NAME` (`X-API-Key`)
* Secret backend: `HRC_SECRET_BACKEND` (giá trị: `env`, `vault`, `aws`). Mặc định là `env`; giá trị khác gây `ValueError`.
* AWS Secret Manager: `HRC_AWS_SECRET_NAME` (bắt buộc, tên secret hoặc ARN chứa JSON object), `HRC_AWS_REGION` (mặc định: `us-east-1`). `SecretManager.get_secret(key)` chọn trường chuỗi, không trả toàn bộ `SecretString`; xem [Secret Manager](../modules/config.md) về giá trị mặc định và chuyển đổi dữ liệu.
* `HRC_MASTER_KEY_SOURCE=env` vẫn được chấp nhận như alias tương thích cho hành vi secret qua biến môi trường hiện có. Giá trị khác của `HRC_MASTER_KEY_SOURCE` và mọi `HRC_MASTER_KEY_FILE` không rỗng sẽ khiến cấu hình dừng với lỗi vì chưa có master-key provider thay thế. Điều này không thay đổi API `FileVaultProvider` riêng biệt.
* Bảo vệ brute-force:
    * `HRC_BF_MAX_FAILURES` (mặc định: `5`)
    * `HRC_BF_LOCKOUT_SECONDS` (mặc định: `900` = 15 phút)
    * `HRC_BF_WINDOW_SECONDS` (mặc định: `300` = 5 phút)
    * TTL khóa của Redis tuân theo `HRC_BF_LOCKOUT_SECONDS`; mỗi yêu cầu kiểm tra khóa đều đọc khóa dùng chung. SQLite và Redis đếm số lần thất bại một cách nguyên tử giữa các worker. Redis dùng thời gian máy chủ và cập nhật Lua nguyên tử cho cửa sổ thất bại và ngưỡng khóa. Bộ đếm lần thử của memory/file vẫn thuộc riêng từng tiến trình.
* Identity và organization: `IDENTITY_MANAGER_ENABLED` (`True`), `REQUIRE_ORGANIZATION_VALIDATION` (`True`), `MSP_ENABLED` (`True`)

### Bảo mật mạng P2P

* Định danh node và P2P transport: `HRC_NODE_ID` (mặc định: `default-node`; `NODE_ID` là alias dự phòng), `HRC_P2P_PORT` (mặc định: `5555`; `NODE_PORT` là alias dự phòng), và `HRC_PEERS` (mặc định: danh sách rỗng; danh sách seed node phân tách bằng dấu phẩy; `PEERS` là alias dự phòng). Dùng `peer-id@host:port` khi định danh transport từ xa khác hostname; dạng `host:port` lấy hostname làm peer ID. Tên có tiền tố HRC được ưu tiên.
* `HRC_P2P_TRUST_POLICY` (mặc định: `open` ở dev, `strict` ở production; giá trị: `open|strict`)
* `HRC_P2P_PEER_ALLOWLIST` (danh sách peer ID phân tách bằng dấu phẩy cho chế độ strict)
* `HRC_P2P_REQUIRE_SIGNATURES` (`false` ở dev, `true` ở production)

Production cố định chính sách tin cậy ở `strict` và yêu cầu chữ ký ở `True`; giá trị môi trường không ghi đè các thuộc tính production này. `SecureConnectionManager` dùng các thiết lập đó. Luồng khởi động API tạo `NetworkClient` với seed peer và transport key, chưa nối manager này, chính sách tin cậy hoặc kiểm tra chữ ký vào client. Xem [Network](../modules/network.md).

### CORS

* `HRC_CORS_ALLOW_ALL` (`true` ở dev, `false` ở production)
* `HRC_CORS_ORIGINS` (danh sách CSV domain; production cần giá trị cụ thể)
* `CORS_ALLOW_METHODS` (danh sách method cho phép)
* `CORS_ALLOW_HEADERS` (danh sách header cho phép)

### HTTPS và HSTS

* `HRC_HSTS_ENABLED` (`false` ở dev/test; `true` ở production)
* `HRC_HSTS_MAX_AGE` (mặc định: `31536000` = 1 năm)

Các thiết lập này được khai báo và kiểm tra để cảnh báo cấu hình, nhưng middleware API không thêm `Strict-Transport-Security`. Hãy cấu hình header tại reverse proxy HTTPS.

### Rate limiting

* `HRC_RATE_LIMIT` (`false` ở dev/test; `true` ở production)
* `HRC_RATE_LIMIT_RPM` (mặc định: `100` requests/phút)
* `HRC_RATE_LIMIT_BACKEND`: `memory` (đơn node) hoặc `redis` (đa node hoặc cluster).
* Với backend `redis`, lỗi và timeout Redis từ chối request không thuộc diện miễn trừ bằng HTTP 503 (fail-closed). Kiểm tra Redis chạy ngoài event loop của API.

### Monitoring và metrics

* `HRC_METRICS_ENABLED` (mặc định: `false`). Bật `/metrics` để xuất registry Prometheus mặc định. API không đăng ký bộ đếm yêu cầu/độ trễ HTTP hay collector cho ledger.
* `HRC_TRUSTED_PROXIES` (mặc định: `127.0.0.1`). IP của reverse proxy tin cậy (cho HTTP/2, HTTP/3).

### Đa tổ chức

* `MULTI_ORG_ENABLED` (`True`), `MSP_ENABLED` (`True`)
* `ORGANIZATION_ADMIN_THRESHOLD` (mặc định: `1`)
* `CHANNEL_CREATION_POLICY` (mặc định: `majority`; giá trị: `majority|unanimous|admin_only`)
* `AFFILIATION_HIERARCHY_ENABLED` (`True`)

### Zero-knowledge (ZK)

* `HRC_ENABLE_ZK_PROOFS` (mặc định: `false`)
* `HRC_ZK_MODE` (`mock` hoặc `production`, mặc định `mock`)
* `HRC_ZK_VERIFICATION_KEY`, `HRC_ZK_PROVING_KEY`, `HRC_ZK_CIRCUIT` (đường dẫn file)
* `HRC_ZK_REQUIRED_MAINCHAIN` (mặc định: `false`)

Mock chỉ phục vụ phát triển; tạo/xác minh `production` chưa triển khai. Bật flag hoặc cấu hình key/circuit không cung cấp backend production.

### Đồng bộ trạng thái cross-level

* `HRC_CROSS_LEVEL_SYNC` (mặc định: `true`)
* `HRC_CROSS_LEVEL_BATCH` (mặc định: `100`)
* `HRC_CROSS_LEVEL_TIMEOUT` (mặc định: `30.0` giây)

### Integration

* `ERP_INTEGRATION_ENABLED` (`True`)
* `SUPPORTED_ERP_SYSTEMS` (danh sách: `sap`, `oracle`, `microsoft_dynamics`)

Các thuộc tính này không khởi động ERP sync ở API. Connector vendor có sẵn là fixture `simulation_mode=True`; ứng dụng phải cấp adapter thật.

### Thuộc tính khai báo chưa điều khiển runtime

`HRC_BLOCK_CREATION_MODE`, `HRC_BLOCK_MAX_WAIT_SEC`, `HRC_PARQUET_ROLL_INTERVAL`, `HRC_POSTGRES_SYNC_MODE` và `HRC_SQL_RETENTION_DAYS` được đọc vào settings nhưng chưa có consumer runtime trong `hierachain/`. Đặt các biến này không tự đổi batching, xoay Parquet, bật batch worker SQL hoặc xóa event cũ. Cấu hình batching trực tiếp trên ordering service/Sub-Chain.

### Logging

* `LOG_LEVEL`: lớp môi trường được chọn cố định thuộc tính này ở `DEBUG` trong dev/test và `WARNING` trong production. Đặt biến môi trường `LOG_LEVEL` không ghi đè các giá trị của lớp.
* `LOG_FORMAT` (chuỗi định dạng logging Python chuẩn).
* `HRC_LOG_FORMAT`: `text` (mặc định) hoặc `json` (cho log tập trung như ELK/Loki).
* `HRC_LOG_SQL_DETAIL` (mặc định: `false`; bật tường minh qua biến môi trường nếu cần)

Các lệnh khởi động cấu hình Uvicorn riêng: `python -m hierachain` chọn `debug` khi settings có mức DEBUG và `info` trong các trường hợp còn lại; `hrc node start` dùng `info`. `HRC_LOG_FORMAT` điều khiển formatter của ứng dụng.

### CLI

* `CLI_CONFIG_FILE` (mặc định: `data/config.yaml`; cấu hình node mặc định cho `hrc --config`)
* `CLI_LOG_LEVEL` (mặc định: `INFO`)

## Ví dụ .env (development)

Thêm identity ký và bản đồ trusted key theo [Bắt đầu nhanh](../getting-started/quickstart.md) trước khi khởi tạo chain.

```dotenv
HRC_ENV=dev
HRC_API_HOST=0.0.0.0
HRC_API_PORT=2661
HRC_CONSENSUS_TYPE=proof_of_authority
HRC_AUTH_ENABLED=false
HRC_CORS_ALLOW_ALL=true
DATABASE_URL=postgresql://hiera:hiera@localhost:5432/hierachain
```

## Cấu hình production khuyến nghị (tối thiểu)

```dotenv
HRC_ENV=production
HRC_API_KEYS_FILE=/run/secrets/api_keys.json
HRC_VALIDATOR_IDENTITY=/run/secrets/identity.json
HRC_BLOCK_TRUSTED_KEYS_FILE=/run/secrets/trusted_block_keys.json
HRC_API_KEY_REVOCATIONS_DB=/var/lib/hierachain/api_key_revocations.sqlite3
HRC_NODE_ID=node1
HRC_API_HOST=0.0.0.0
HRC_AUTH_ENABLED=true
HRC_CORS_ALLOW_ALL=false
HRC_CORS_ORIGINS=https://portal.example.com
HRC_RATE_LIMIT=true
DATABASE_URL=postgresql://user:pass@db:5432/hierachain
HRC_STORAGE_BACKEND=postgres
HRC_IPFS_ENABLED=true
HRC_IPFS_HOST=/ip4/ipfs/tcp/5001
HRC_IPFS_ENCRYPTION_KEY=your_32_byte_hex_key_here
```
