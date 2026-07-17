---
title: "Changelog"
description: "Nhật ký thay đổi chính của HieraChain và tài liệu kèm theo."
icon: material/history
---

# Changelog

## Unreleased

??? note "Improvements (84)"

    * 2026-07-17

        * **Hiệu năng**: Thay thế `json` bằng `orjson` trên toàn bộ codebase — security, risk_management, network, monitoring, privacy, config, CLI, API và hierachain modules — cho serialization/deserialization nhanh hơn.
        * **Core**: Thêm tính năng phục hồi dữ liệu payload block tối ưu với phân tích cột `data` trực tiếp khi khả dụng.
        * **Bảo mật**: Tối ưu xác minh chữ ký với thread pool cấu hình được (CPU count) và tách `_get_verify_key` helper để giải mã public key.
        * **Kiểm thử**: Kéo dài thời gian sleep trong `test_repro_determinism` từ 0.5s lên 1.5s cho độ tin cậy shutdown cao hơn.

    * 2026-07-16

        * **Kiểm thử**: Sửa false positive trong term censorship test — bỏ qua docstring examples giải thích regex word-boundary matching.
        * **Tài liệu**: Thêm PR description template cho việc merge v0.0.x vào main.
        * **Changelog**: Cập nhật unreleased section với các phát triển gần đây.

    * 2026-07-12

        * **Network**: Sửa lỗi giải mã public key seed node với xử lý đặc biệt cho ký tự `$$`.

    * 2026-07-11

        * **Docker**: Thêm tùy chọn `DISABLE_WIREGUARD` để bỏ qua khởi tạo giao diện WireGuard.

    * 2026-07-10

        * **Tài liệu**: Cập nhật tài liệu cho rõ ràng và cấu trúc dự án; cải thiện PR template.

    * 2026-07-09

        * **Risk Management**: Cải thiện xử lý kết nối database trong audit logger.
        * **Policy**: Sửa lỗi đánh giá giá trị Null trong Arrow `StructArray`.
        * **Kiểm thử**: Thêm integration test cho kiểm duyệt thuật ngữ cryptocurrency; thêm database audit storage integrity tests.

    * 2026-07-08

        * **CI**: Cải tiến issue templates cho rõ ràng; thêm pull request template.

    * 2026-07-07

        * **Hạ tầng**: Cập nhật script setup K8s/Podman dùng `uv` cho lệnh Python.
        * **Stress**: Tunning ngưỡng chấp nhận trong poison pill test cho độ tin cậy cao hơn.

    * 2026-07-06

        * **Stress Testing**: Triển khai framework kiểm thử mạng toàn diện (mô phỏng bandwidth, latency, packet loss); thêm framework giám sát tài nguyên và cảnh báo.
        * **WebSocket**: Cải thiện độ tin cậy của load test.

    * 2026-07-05

        * **Database**: Nâng cấp SQL adapter với hỗ trợ metadata và merkle root.
        * **API**: Đổi tên API version tags cho rõ ràng (`v1` → `ledger`, `v2` → `business`, `v3` → `admin`); cập nhật security testing scripts và health check endpoints tương ứng.
        * **Tài liệu**: Tổ chức lại tài liệu API version cho rõ ràng.
        * **Demo**: Sửa metadata filename trong IPFS demo; cập nhật version attribute/import paths.

    * 2026-07-04

        * **API**: Tái cấu trúc modules API cho bảo mật và bảo trì tốt hơn; dùng background tasks để ghi security events bất đồng bộ.
        * **Monitoring**: Triển khai module giám sát hiệu suất toàn diện; thêm hệ thống cảnh báo với phát hiện bất thường và thông báo.
        * **Risk Management**: Triển khai `DatabaseAuditStorage` cho audit logging bền vững.
        * **Tái cấu trúc**: Xóa deadlock detector và tests liên quan; xóa tham chiếu `sql_backend`; tổ chức lại quản lý version.

    * 2026-07-02

        * **Storage Migration**: Thay thế `SqlStorageBackend` bằng `SQLiteAdapter`; xóa module storage cũ.
        * **Database**: Thêm bảng chain state cho tra cứu nhanh; thêm hàm lưu trữ và truy xuất dữ liệu blockchain.

    * 2026-07-01

        * **API Routing**: Tái cấu trúc lớn cấu trúc routing API và tên module; tối ưu middleware và WebSocket manager.
        * **Domains**: Tái cấu trúc logic trích xuất event và quản lý transaction; xóa generic-level re-export shim.
        * **Kiểm thử**: Cập nhật import paths và test files cho cấu trúc API mới.

    * 2026-06-30

        * **Dọn dẹp Code Chết**: Xóa các module không dùng trong core (performance, parallel_engine), storage (`ChainModel`), network (message encryption exception classes), error_mitigation, domains (entity reporting, compliance), consensus, API, và adapters.
        * **State**: Xóa hàm `apply_event_list` khỏi world state.
        * **Event Ledger**: Tái cấu trúc cấu trúc dữ liệu event và logic lưu trữ.

    * 2026-06-24

        * **Dependencies**: Thêm `vulture` cho phát hiện code chết; xóa cấu hình `tox` (chuyển sang `uv`).

    * 2026-06-23

        * **Hierarchical**: Modular hóa `MainChain` (proof + registry), `SubChain` (rehydration logic), `Rebalancer` (trích xuất event), `HierarchyManager` (khởi tạo cross-level sync), K8s namespace manager; thêm `compliance_checker`.
        * **Consensus**: Cải thiện logic trích xuất và xác minh chữ ký.
        * **Monitoring/Alert**: Modular hóa thành packages riêng với shared types.
        * **ERP**: Modular hóa components tích hợp cho bảo trì tốt hơn.
        * **Security**: Cải thiện lưu trữ API key và quản lý cache.
        * **Events**: Di chuyển domain event classes với factory functions; di chuyển metrics và transaction manager sang modules riêng.
        * **Core**: Cải thiện event queries và xử lý type.

    * 2026-06-22

        * **BFT Consensus**: Tái cấu trúc thành components modular (engine, dispatcher, view_change).
        * **Ordering**: Tái cấu trúc logic xử lý batch và validation.
        * **Cluster**: Tách helpers xác thực node và authentication.
        * **Redis**: Tái cấu trúc adapter thành manager classes với delegate operations.
        * **Security**: Tách production security checks thành helper function.
        * **API**: Tách helpers tra cứu block và tạo chain.
        * **WebSocket**: Thêm type annotations `None` rõ ràng cho optional parameters.
        * **Schemas**: Tối ưu payload depth validation dùng stack traversal.

    * 2026-06-21

        * **Hiệu năng**: Thay thế `json` bằng `orjson` trên database layer cho serialization nhanh hơn.
        * **Journal**: Thêm ghi bất đồng bộ background cho event logging.
        * **Bảo mật**: Tối ưu xác minh chữ ký batch và serialization proof.

    * 2026-06-20

        * **Consensus**: Tối ưu xác minh chữ ký batch; ủy quyền crypto term validation cho core utility.

    * 2026-06-19

        * **Domains**: Tổ chức lại cấu trúc package; di chuyển các module generic; xóa lớp `generic/`.
        * **Hierarchical**: Triển khai `HierarchyManager` cho điều phối chain; tái cấu trúc xử lý proof sub-chain.
        * **Core**: Cải thiện xử lý block event và merkle tree.
        * **Consensus**: Tổ chức lại BFT consensus; cập nhật PoA và PoF classes.
        * **Security**: Xóa các module certificate và backup không dùng; đơn giản hóa imports.
        * **Storage**: Xóa memory storage và world state modules.
        * **State**: Thêm `WorldState` class cho quản lý trạng thái entity.
        * **Error Mitigation**: Xóa các module rollback và recovery không dùng.
        * **Integration**: Xóa `ArrowClient` và các types liên quan.
        * **Network**: Xóa `NetworkClientSync` synchronous wrapper.
        * **Database**: Thêm `RedisStorageAdapter` cho lưu trữ blockchain Redis.
        * **Config**: Xóa cài đặt cache và parallel processing không dùng.
        * **CLI**: Sửa import path cho `DomainChain`.
        * **Version**: Đơn giản hóa version module; xóa functions không dùng.
        * **Dependencies**: Thêm `orjson 3.11.9`.

    * 2026-06-17

        * **SDK**: Tái cấu trúc thành sync và async clients với shared types và exceptions.
        * **Security**: Modular hóa quản lý certificate và key backup.
        * **Risk Management**: Tái cấu trúc và tối ưu modules.

    * 2026-06-16

        * **Core Cache**: Thay thế `caching.py` nguyên khối bằng `Cache` và `CacheManager` modular.
        * **BFT**: Hợp nhất BFT helpers vào một module duy nhất.
        * **Cluster**: Di chuyển data types sang modules riêng (lockdown_types, cross_level_sync_types).
        * **Monitoring**: Hợp nhất alert và performance types vào shared module.
        * **Integration**: Di chuyển error và sync classes sang types module.
        * **Hierarchical**: Tập trung shared types vào module `types.py` mới.
        * **Error Mitigation**: Thêm các modules xử lý lỗi toàn diện (consensus_validator, resource_validator, network_recovery, auto_scaler, backup_recovery).

    * 2026-06-15

        * **API Restructuring**: Chia nhỏ `v1/endpoints.py` nguyên khối thành components modular; modular hóa `v2/endpoints.py`; sửa import paths cho `v3`.
        * **GraphQL**: Tái cấu trúc schema và resolvers cho tổ chức tốt hơn.
        * **Database**: Thêm base SQL adapter và tích hợp vào `SQLiteAdapter`.
        * **Server**: Modular hóa middleware và GraphQL handler; tối ưu setup server; modular hóa blockchain explorer thành components.

---

## v0.0.6 (2026-07-15)

Phiên bản này tập trung vào củng cố bảo mật cho logging subsystem, đơn giản hóa core blockchain và các tầng hierarchical, cùng với hardening consensus với xử lý lỗi chính xác.

??? note "Improvements (6)"

    * **Secure Logging**: Thêm redaction dữ liệu nhạy cảm dựa trên regex trong `hierachain/security/` — các giá trị nhạy cảm được thay bằng `'***'` để ngăn rò rỉ thông tin xác thực. Giới thiệu `_SEVERITY_MAP` để logging nhất quán, thay thế các method log level trực tiếp bằng `logger.log()` — giảm trùng lặp trên toàn bộ call sites.
    * **Core Blockchain Refactoring**: Thêm `_rebuild_event_indexes` để reset và rebuild event indexes sau khi load blocks — đảm bảo index consistency giữa các lần khởi động. Thay đổi hash mismatch từ silent correction thành exception — không còn che giấu corruption tiềm ẩn. Thay thế dictionary access bằng `block.to_event_list()` cho event filtering sạch hơn.
    * **Consensus Hardening**: Cải thiện `_contains_forbidden_terms` với regex word-boundary matching để loại bỏ false positives. Loại bỏ fallback random signature generation — signing fail rõ ràng với error message khi thiếu private key. `ProofOfFederation` tự động sinh key pairs cho validators, expose `public_key` property, thêm `block_hash` vào consensus metadata. `_verify_block_quorum` nhận optional `signer_id` để tránh quét event dư thừa.
    * **Hierarchical Layer Simplification**: Loại bỏ temporary entity index mapping, local chain clear, event statistics reset trong sub-chain rehydration. Xóa redundant event addition vào `Blockchain.pending_events`. Streamline `_recover_pending_events_from_journal` để chỉ đếm uncommitted events, chuyển event reconstruction sang `OrderingRecovery`.
    * **Testing & Benchmark**: Nâng cấp ZK Proof-of-Federation test với keypair thật, chữ ký thật và pre-consensus block validation. Cập nhật storage benchmark dùng `Block` class từ `hierachain.core`, đổi tên `event_type` thành `event`. Thêm helper function cho `ProofOfFederation` instantiation với signing key.

??? warning "Fix (1)"

    * **Logger Test Alignment**: Cập nhật test assertions để khớp với method signatures mới của logger (`mock_info` → `mock_log`, `call_args` indexing thay đổi).

---

## v0.0.5 (2026-06-20)

Phiên bản này tập trung vào cải thiện core package `hierachain/`, bao gồm thay thế `ipfshttpclient` bằng `httpx` cho Kubo RPC, tạo sub-chain idempotent, củng cố toàn vẹn chain, persist block và xử lý an toàn các trường hợp biên.

??? note "Improvements (6)"

    * **Kubo RPC Migration**: Thay thế `ipfshttpclient` bằng `httpx` trong `hierachain/api/storage/ipfs_client.py`, thực thi IPFS operations trực tiếp qua Kubo HTTP RPC API. Thêm `_parse_multiaddr` để trích xuất host/port từ multiaddress strings. Refactor core operations (upload, download, pin, unpin, list_pins, stats) sang `httpx.Client` POST requests. Loại bỏ `_IPFSClientContext` wrapper class.
    * **Idempotent Sub-Chain Creation**: API v1 (`hierachain/api/v1/endpoints.py`) kiểm tra sub-chain tồn tại trước khi tạo, trả về `201 Created` với audit trail `"already_exists"` cho duplicate. Xử lý `409 Conflict` khi `manager.add_sub_chain` báo duplicate qua `ValueError`.
    * **Chain Integrity Hardening**: Thêm `_verify_chain_links()` trong `hierachain/consensus/ordering/storage.py` để xác thực chuỗi `previous_hash` giữa các block. `_block_from_dict` raise `ValueError` khi computed hash mismatch stored hash, thay vì chỉ log error.
    * **Event Enrichment & Block Persistence**: Ordering service (`hierachain/consensus/ordering/service.py`) tiêm `event_id` vào `event_data` payload trước khi tạo pending event. Recovery (`recovery.py`) ưu tiên `event_id` từ enriched `event_data`. Sub-chain finalize (`hierachain/hierarchical/sub_chain.py`) persist block qua storage handler, đảm bảo rehydration giữ nguyên consensus events.
    * **Block Overwrite**: `hierachain/storage/sql_backend.py` — `save_block` query existing block theo `index`/`chain_name`, xóa và ghi đè thay vì silent `UNIQUE constraint` handling.
    * **Zero Children Safeguard**: Rebalancer (`hierachain/hierarchical/rebalancer.py`) trả về `0` an toàn khi `num_children <= 0`, ngăn lỗi modulo-by-zero.

??? warning "Fix (1)"

    * **Integrity Check Locking**: Di chuyển post-rehydration chain integrity validation ra ngoài lock trong `hierachain/hierarchical/sub_chain.py`. Downgrade mismatch log từ error xuống warning để tính đến pending consumer thread blocks.

---

## v0.0.4 (2026-05-25)

Phiên bản này tập trung vào Node Identity với keypairs Ed25519/Curve25519, mã hóa ZeroMQ CURVE cho P2P, endpoint API v3 cho event an toàn, chữ ký Ed25519 cho Proof of Federation, xác thực timestamp BFT chống replay, và củng cố bảo mật toàn diện trong `hierachain/`.

??? note "Improvements (4)"

    * **Node Identity & P2P Networking**: Giới thiệu `NodeIdentity` trong `hierachain/security/identity_loader.py`, mã hóa ZeroMQ CURVE trong `NetworkClient`, `send_direct`/`broadcast`, ping-pong heartbeat. Tích hợp node identity qua `HierarchyManager`, `DomainChain`, `OrderingService` và BFT consensus.
    * **API v3 & Chữ ký số**: Endpoint `POST /api/v3/chains/{chain_name}/secure-events` với xác thực chữ ký Ed25519, giới hạn payload 1MB và độ sâu tối đa 10. Thêm trường `sender`/`signature` vào schema v1 với validation hex nghiêm ngặt.
    * **Củng cố Consensus**: Chữ ký Ed25519 cho Proof of Federation (`_create_federation_signature`, `_verify_block_quorum`), xác thực timestamp BFT 30 giây chống replay, xác minh block hash khi reconstruction, `block_interval` cấu hình qua `HRC_BLOCK_INTERVAL`.
    * **Bảo mật**: Từ chối ZK proof giả trong production (cho phép test), so sánh hằng số thời gian HMAC (`hmac.compare_digest`), `threading.RLock` trong LockdownProtocol, tăng PBKDF2 lên 310,000 iterations, `AdvancedCache` với TTL/LRU cho `KeyManager`.

??? warning "Fix (2)"

    * **Consensus & Storage**: Sửa xác thực block signature và sinh key tự động trong PoA, sửa return value mặc định trong BFT handler từ `True` sang `False`, thêm validation proof_hash 64-ký tự SHA-256, xác thực toàn vẹn chain sau deserialization, thêm cột `creator_id`/`signature` vào block DB model.
    * **API & SDK**: Cập nhật default base URL SDK từ 8000 sang 2661, validation tên sub-chain bằng regex, thread-safe `RateLimiter`, validation CID/nonce trong IPFS client.

---

## v0.0.3 (2026-05-02)

Phiên bản này tập trung vào cải thiện type safety toàn diện trong `hierachain/`, đạt full Mypy compliance, xác thực Ed25519 64-byte nghiêm ngặt, canonicalization JSON cho xác minh deterministic, HMAC lockdown protocol, middleware giới hạn payload, và validation timestamp 24 giờ.

??? note "Improvements (4)"

    * **Tuân thủ Mypy đầy đủ**: Giải quyết các cảnh báo static typing trên tất cả module — consensus, API, security, network, monitoring, error mitigation, storage, adapters, hierarchical, domains, core và cluster.
    * **Xác thực Signature Ed25519**: Thực thi chiều dài 64-byte nghiêm ngặt cho signature Ed25519 trong `verify_signature_standalone` để ngăn chặn bypass validation.
    * **Canonicalization JSON**: Triển khai `get_canonical_bytes` với sắp xếp dict đệ quy, chuẩn hóa Unicode NFC, định dạng float nhất quán cho xác minh chữ ký deterministic.
    * **Bảo mật**: Thêm `PayloadLimitMiddleware` từ chối POST/PUT/PATCH trên 1MB, validation proof timestamp 24h, ngăn chặn API key mặc định trong production (`RuntimeError`), refactor HMAC lockdown protocol (`hmac.new` SHA256).

??? warning "Fix (1)"

    * **BFT & Validation**: Giới hạn BFT message log ở 10,000 entries ngăn memory growth vô hạn, cải thiện IPFS connection handling (`_ensure_connected` với None checks), sửa bare except clauses, thêm `\b` word-boundary matching cho validation thuật ngữ cryptocurrency.

---

## v0.0.2 (2026-04-04)

Phiên bản này tập trung vào tăng cường bảo mật, khả năng quan sát hệ thống và các cải thiện quan trọng về ổn định cho core package `hierachain/`, giải quyết các vấn đề thực tế phát hiện trong quá trình kiểm thử và đánh giá.

??? note "Improvements (5)"

    * **Quản lý Secret & Thông tin xác thực**:

        * Giới thiệu `SecretManager` thống nhất trong `config` để quản lý thông tin xác thực an toàn với hỗ trợ nhiều backend.
        * Ngăn chặn vô tình làm lộ bí mật trong logs bằng cách che tên secret và định danh backend.
        * Ngăn chặn tự động sinh master key trong môi trường production để yêu cầu cấp phát key rõ ràng.

    * **Bảo mật & Chính sách**:

        * Thêm lưu trữ persistent cho brute force lockouts và chủ động từ chối các mẫu input nguy hiểm trong policy engine.
        * Tăng cường kiểm tra tạo thư mục để ngăn chặn tấn công path traversal trong đường dẫn cơ sở dữ liệu SQLite của SubChain.
        * Thêm module bảo mật chuyên dụng cho endpoint GraphQL với xác thực input và kiểm soát truy cập.

    * **Khả năng Quan sát & Giám sát**:

        * Tích hợp thu thập metrics Prometheus để giám sát thời gian thực độ trễ API, thông lượng khối và sức khỏe consensus.
        * Thêm hỗ trợ logging JSON để tích hợp tốt hơn với các hệ thống tổng hợp logs như ELK và Loki.
        * Thêm phương thức alert đơn giản và instance manager toàn cục để thông báo sự kiện chủ động.
        * Tăng cường rate limiting API với backend Redis cho các deployment phân tán.

    * **Cải thiện Core & Hierarchical Chain**:

        * Triển khai phát hiện deadlock với timeout và cơ chế phục hồi trong quản lý lock.
        * Leo thang mức độ nghiêm trọng của ZK proof bị thiếu lên mức critical và tích hợp trigger alert tự động.
        * Cải thiện độ mạnh mẽ của việc submit proof và xử lý shutdown trong hierarchical chains.
        * Thêm xác thực input cho `ChannelLedger.add_event` để ngăn chặn events bị malformed.

    * **Công cụ Nhà phát triển & CLI**:

        * Thêm lệnh CLI chuyên dụng cho sinh, backup và phục hồi key (`python -m hierachain key ...`).
        * Thêm endpoint để fetch khối cụ thể theo index hoặc hash cho audit mục tiêu.
        * Cập nhật SDK client để hỗ trợ đầy đủ multi-chain API v3.
        * Đồng bộ block schema với event schema để có cấu trúc dữ liệu nhất quán.

??? warning "Fix (2)"

    * **Ổn định Consensus & Ordering**:

        * Giải quyết race condition quan trọng trong commit khối và xử lý sự kiện chờ trong `OrderingService`.
        * Đảm bảo các hoạt động lockdown và resume là atomic để ngăn chặn trạng thái không nhất quán trong quá trình bảo trì.
        * Ngăn chặn mất dữ liệu im lặng trong quá trình phục hồi transaction journal với xác thực đúng đắn.
        * Cải thiện logic phục hồi state với xác thực config và modularized recovery từ transaction journal.

    * **Core & Hierarchical Chain**:

        * Sửa race condition trong quản lý hierarchical chain và thêm thủ tục shutdown graceful.

---

## v0.0.1 (2026-03-22)

Phiên bản này đánh dấu việc hoàn thiện định hướng kiến trúc ban đầu của HieraChain, tập trung vào việc hợp nhất các thành phần cốt lõi thành một khung nguyên mẫu thống nhất.

??? note "Improvements (4)"

    * **Tích hợp Lưu trữ IPFS**: Hỗ trợ lưu trữ dữ liệu off-chain với mã hóa AES-256-GCM và định danh CID trên toàn bộ các giao diện API (REST, GraphQL, WebSocket).
    * **Tối ưu Hiệu suất & Khả năng mở rộng**:

        * Xử lý khối song song trong `OrderingService`.
        * Caching cho xác thực chứng chỉ và quyền hạn.
        * Tối ưu hóa worker pool (75% CPU) và hỗ trợ đa luồng cho SQLite.

    * **Công cụ cho Nhà phát triển**: Ra mắt `BlockchainExplorer` dashboard và hệ thống tài liệu kỹ thuật chi tiết.
    * **Bảo mật & Toàn vẹn**: 

        * Hỗ trợ Merkle Root trong block header và lưu trữ.
        * Đảm bảo tính nhất quán của hash và thread-safe cho các thành phần core.
        * Chuẩn hóa logging bảo mật với `SecureLogger`.

??? warning "Fix (1)"

    * **Ổn định & QA**: 

        * Sửa lỗi Chain Rehydration giúp khôi phục trạng thái chính xác sau khi restart.
