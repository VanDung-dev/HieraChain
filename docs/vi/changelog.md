---
title: "Changelog"
description: "Nhật ký thay đổi chính của HieraChain và tài liệu kèm theo."
icon: material/history
---

# Changelog

## Unreleased

??? note "Improvements (0)"
??? warning "Fix (2)"

    * 2026-08-14

        * **Bảo mật (ZK Mock Proof)**: `_generate_mock_proof` trong `hierachain/security/zk_prover.py` nhận thêm tham số `sub_chain_name` và đưa vào `public_inputs`, khắc phục tình trạng commitment SHA-256 được tính với `sub_chain_name=""` trong khi verifier hash với tên sub-chain thật (làm mọi proof bị reject khi `ENABLE_ZK_PROOFS=true`). `_verify_mock_proof` thay thế kiểm tra prefix `mock_proof` thiếu chặt chẽ bằng logic `_verify_mock` chuẩn từ `zk_verifier` (so hash commitment với `public_inputs`), từ chối fake proof.
        * **Hierarchical**: Chuyển guard chain chỉ có genesis block lên trước `get_latest_block()` trong `_submit_proof_for_sub_chain` (`hierachain/hierarchical/sub_chain/proof.py`), tránh `IndexError` khi SubChain rỗng thay vì trả `False` đúng quy ước.

---

## v0.1.0 (2026-08-10)

Phiên bản cột mốc quan trọng này đánh dấu sự củng cố kiến trúc thư viện cốt lõi của HieraChain (`hierachain/`). Các điểm nổi bật bao gồm chuẩn hóa hoàn toàn thuật ngữ, hoàn thiện cơ chế đồng thuận hai tầng (PoA cho SubChain nội bộ và PoF cho liên minh MainChain inter-org), tích hợp các thư viện hiệu năng cao (`orjson`, `uvloop`), dọn dẹp mã nguồn thừa và tái cấu trúc router API.

??? note "Improvements (52)"

    * 2026-07-27

        * **Đồng thuận**: Giới thiệu biến môi trường `HRC_MAINCHAIN_CONSENSUS` với bí danh tương thích ngược `HRC_CONSENSUS_TYPE`. `MainChain.__init__` chấp nhận tham số `consensus_type` tùy chọn. `SubChain` mặc định sử dụng PoA cho sự kiện nội bộ, có thể cấu hình qua `config["consensus_type"]`.

    * 2026-07-23

        * **Tái cấu trúc**: Chuyển toàn bộ import nội tuyến/muộn (`os`, `sys`, `time`, `uuid`, `asyncio`, `warnings`, `httpx`, `pyarrow`, `cast`) lên đầu file (module-level) trên 14 file nguồn, tuân thủ hoàn toàn PEP 8 về thứ tự import.

    * 2026-07-22

        * **API**: Bổ sung thư viện `uvloop` và kích hoạt event loop bất đồng bộ hiệu năng cao trong API Server.
        * **Blockchain**: Bổ sung chỉ mục `event_type_index` trên `Blockchain` và hàm `to_event_list` trên `Block` cho phép tra cứu sự kiện theo loại với độ phức tạp O(1).
        * **Cache**: Thay thế danh sách mặc định bằng `OrderedDict` cho quản lý thứ tự LRU/TTL và đơn giản hóa vòng đời thread dọn dẹp.
        * **Bảo mật**: Tái cấu trúc logic kiểm duyệt thuật ngữ crypto bằng phương pháp duyệt đệ quy, loại bỏ serialization JSON tốn kém.
        * **Hierarchical**: Tối ưu hóa `HierarchyManager` sử dụng chung ngữ cảnh thread pool executor, giảm overhead khởi tạo thread khi đồng bộ proof.
        * **State**: Khắc phục lỗi tranh chấp (race condition) khi tính toán Root Hash trong `WorldState` bằng cách đưa sắp xếp và dựng Merkle Tree ra ngoài phạm vi Lock.
        * **Mạng**: Tối ưu hóa bộ đệm Replay Buffer trong ZMQ Transport với cơ chế chỉ dọn dẹp khi kích thước vượt ngưỡng (>1000 entries).
        * **Đồng thuận**: Hạ ngưỡng kích hoạt xác minh chữ ký hàng loạt từ 15 xuống 4 để tận dụng tăng tốc đa luồng sớm hơn.

    * 2026-07-18

        * **Lưu trữ**: Tối ưu hóa giới hạn connection pool của IPFS (`max_keepalive_connections=50`, `max_connections=150`) giúp đẩy nhanh tốc độ upload/download đồng thời.
        * **Core**: Khắc phục lỗi tranh chấp chỉ mục (race conditions) khi tạo block đồng thời bằng cách đưa các phép tính hash và index vào phạm vi Lock.
        * **Database**: Tối ưu hóa SQLite Adapter bằng cách tăng thời gian timeout kết nối cơ sở dữ liệu lên 30.0 giây, loại bỏ lỗi khóa ghi (database lock) dưới tải song song cực lớn.

    * 2026-07-17

        * **Hiệu năng**: Thay thế `json` bằng `orjson` trên toàn bộ codebase (security, risk_management, network, monitoring, privacy, config, CLI, API và hierachain modules) cho serialization/deserialization nhanh hơn.
        * **Core**: Thêm tính năng phục hồi dữ liệu payload block tối ưu với phân tích cột `data` trực tiếp khi khả dụng.
        * **Bảo mật**: Tối ưu xác minh chữ ký với thread pool cấu hình được (CPU count) và tách `_get_verify_key` helper để giải mã public key.

    * 2026-07-12

        * **Mạng**: Sửa giải mã public key của seed node với xử lý đặc biệt cho ký tự phân cách `$$`.

    * 2026-07-09

        * **Risk Management**: Cải thiện xử lý kết nối cơ sở dữ liệu trong audit logger.
        * **Policy**: Sửa đánh giá giá trị Null trong Arrow `StructArray`.

    * 2026-07-05

        * **Database**: Nâng cấp SQL adapter hỗ trợ metadata và merkle root.
        * **API**: Đổi tên các tag phiên bản API (`v1` → `ledger`, `v2` → `business`, `v3` → `admin`); cập nhật script test bảo mật và endpoint kiểm tra sức khỏe tương ứng.

    * 2026-07-04

        * **API**: Tái cấu trúc các module API nâng cao bảo mật và khả năng bảo trì; sử dụng background tasks để ghi log sự kiện bảo mật bất đồng bộ.
        * **Giám sát**: Triển khai module giám sát hiệu năng toàn diện; thêm hệ thống cảnh báo phát hiện bất thường và thông báo.
        * **Risk Management**: Triển khai `DatabaseAuditStorage` cho lưu trữ audit log bền vững.
        * **Tái cấu trúc**: Loại bỏ detector phát hiện deadlock và các test liên quan; xóa các tham chiếu `sql_backend`; tổ chức lại quản lý phiên bản.

    * 2026-07-02

        * **Chuyển đổi Storage**: Thay thế `SqlStorageBackend` bằng `SQLiteAdapter`; xóa module storage cũ.
        * **Database**: Thêm bảng chain state cho tra cứu trạng thái nhanh; thêm hàm lưu trữ và truy xuất dữ liệu blockchain.

    * 2026-07-01

        * **API Routing**: Tái cấu trúc lớn cấu trúc định tuyến API và tên module; tối ưu hóa middleware và WebSocket manager.
        * **Domains**: Tái cấu trúc logic trích xuất sự kiện và quản lý transaction; loại bỏ lớp generic-level re-export shim.

    * 2026-06-30

        * **Dọn dẹp mã thừa**: Loại bỏ các module không dùng trong core (performance, parallel_engine), storage (`ChainModel`), network (các class ngoại lệ mã hóa message), error_mitigation, domains (entity reporting, compliance), consensus, API và adapters.
        * **State**: Loại bỏ hàm `apply_event_list` khỏi world state.
        * **Event Ledger**: Tái dựng cấu trúc dữ liệu event và logic lưu trữ.

    * 2026-06-24

        * **Dependencies**: Thêm `vulture` để phát hiện mã thừa.

    * 2026-06-23

        * **Hierarchical**: Modular hóa `MainChain` (proof + registry), `SubChain` (logic rehydration), `Rebalancer` (trích xuất event), `HierarchyManager` (khởi tạo đồng bộ cross-level), K8s namespace manager; thêm `compliance_checker`.
        * **Đồng thuận**: Cải thiện logic trích xuất và xác minh chữ ký.
        * **Giám sát/Cảnh báo**: Modular hóa thành các gói riêng biệt với types dùng chung.
        * **ERP**: Modular hóa các thành phần tích hợp cho khả năng bảo trì tốt hơn.
        * **Bảo mật**: Cải thiện lưu trữ API key và quản lý caching.
        * **Events**: Chuyển các domain event class kèm hàm factory; chuyển metrics và transaction manager sang module riêng.
        * **Core**: Cải thiện truy vấn event và xử lý type.

    * 2026-06-22

        * **BFT Consensus**: Tái cấu trúc thành các thành phần modular (engine, dispatcher, view_change).
        * **Ordering**: Tái cấu trúc xử lý batch và logic xác thực.
        * **Cluster**: Tách các helper xác thực node và authentication.
        * **Redis**: Tái cấu trúc adapter thành các manager class với các thao tác ủy quyền.
        * **Bảo mật**: Tách các kiểm tra bảo mật production thành hàm helper.
        * **API**: Tách các helper tra cứu và tạo block chain.
        * **WebSocket**: Thêm explicit `None` type annotations cho các tham số tùy chọn.
        * **Schemas**: Tối ưu hóa kiểm tra độ sâu payload sử dụng duyệt stack.

    * 2026-06-21

        * **Hiệu năng**: Thay thế `json` bằng `orjson` trên tầng cơ sở dữ liệu cho serialization nhanh hơn.
        * **Journal**: Thêm ghi file nền bất đồng bộ cho event logging.
        * **Bảo mật**: Tối ưu hóa xác minh chữ ký hàng loạt và serialization proof.

    * 2026-06-20

        * **Đồng thuận**: Tối ưu hóa xác minh chữ ký hàng loạt; ủy quyền kiểm tra thuật ngữ crypto cho core utility.

    * 2026-06-19

        * **Domains**: Tái cấu trúc gói; di chuyển các module generic; loại bỏ lớp `generic/`.
        * **Hierarchical**: Triển khai `HierarchyManager` điều phối chuỗi; tái cấu trúc xử lý sub-chain proof.
        * **Core**: Cải thiện xử lý block event và Merkle tree.
        * **Đồng thuận**: Tái cấu trúc BFT consensus; cập nhật các lớp PoA và PoF.
        * **Bảo mật**: Loại bỏ module certificate và backup cũ; đơn giản hóa imports.
        * **Lưu trữ**: Loại bỏ các module memory storage và world state cũ.
        * **State**: Thêm class `WorldState` quản lý trạng thái entity.
        * **Error Mitigation**: Loại bỏ các module rollback và recovery cũ.
        * **Integration**: Loại bỏ `ArrowClient` và các kiểu dữ liệu liên quan.
        * **Mạng**: Loại bỏ wrapper đồng bộ `NetworkClientSync`.
        * **Database**: Thêm `RedisStorageAdapter` cho lưu trữ blockchain trên Redis.
        * **Config**: Loại bỏ các cài đặt cache và xử lý song song không dùng.
        * **CLI**: Sửa đường dẫn import cho `DomainChain`.
        * **Version**: Đơn giản hóa module version; loại bỏ các hàm không dùng.
        * **Dependencies**: Thêm `orjson 3.11.9`.

    * 2026-06-17

        * **SDK**: Tái cấu trúc thành async và sync clients với shared types và exceptions.
        * **Bảo mật**: Modular hóa quản lý certificate và backup key.
        * **Risk Management**: Tái cấu trúc và tối ưu các module.

    * 2026-06-16

        * **Core Cache**: Thay thế `caching.py` đơn khối bằng các thành phần `Cache` và `CacheManager` modular.
        * **BFT**: Hợp nhất các BFT helper thành module đơn.
        * **Cluster**: Di chuyển các kiểu dữ liệu sang các module riêng (`lockdown_types`, `cross_level_sync_types`).
        * **Giám sát**: Hợp nhất các kiểu alert và performance vào module dùng chung.
        * **Integration**: Di chuyển các class error và sync sang module types.
        * **Hierarchical**: Tập trung các types dùng chung vào module `types.py` mới.
        * **Error Mitigation**: Thêm các module error mitigation toàn diện (consensus_validator, resource_validator, network_recovery, auto_scaler, backup_recovery).

    * 2026-06-15

        * **Tái cấu trúc API**: Tách `v1/endpoints.py` đơn khối thành các thành phần modular; modular hóa `v2/endpoints.py`; sửa đường dẫn import `v3`.
        * **GraphQL**: Tái cấu trúc schema và resolvers cho cấu trúc tốt hơn.
        * **Database**: Thêm base SQL adapter và tích hợp vào `SQLiteAdapter`.
        * **Server**: Modular hóa middleware và GraphQL handler; tối ưu hóa khởi tạo server; modular hóa blockchain explorer thành các thành phần.

??? warning "Breaking Changes (1)"

    * **API Routing & Data Schemas**: Tái cấu trúc toàn bộ đường dẫn API theo các không gian tên domain (`/api/ledger`, `/api/business`, `/api/admin`), đổi tên các trường payload từ `transaction_*` sang `event` / `details`, và tái cấu trúc SDK client.

---

## v0.0.6 (2026-07-15)

Phiên bản này tập trung vào củng cố bảo mật cho logging subsystem, đơn giản hóa core blockchain và các tầng hierarchical, cùng với hardening consensus với xử lý lỗi chính xác.

??? note "Improvements (6)"

    * **Secure Logging**: Thêm redaction dữ liệu nhạy cảm dựa trên regex trong `hierachain/security/`: các giá trị nhạy cảm được thay bằng `'***'` để ngăn rò rỉ thông tin xác thực. Giới thiệu `_SEVERITY_MAP` để logging nhất quán, thay thế các method log level trực tiếp bằng `logger.log()`, giảm trùng lặp trên toàn bộ call sites.
    * **Core Blockchain Refactoring**: Thêm `_rebuild_event_indexes` để reset và rebuild event indexes sau khi load blocks, đảm bảo index consistency giữa các lần khởi động. Thay đổi hash mismatch từ silent correction thành exception, không còn che giấu corruption tiềm ẩn. Thay thế dictionary access bằng `block.to_event_list()` cho event filtering sạch hơn.
    * **Consensus Hardening**: Cải thiện `_contains_forbidden_terms` với regex word-boundary matching để loại bỏ false positives. Loại bỏ fallback random signature generation; signing fail rõ ràng với error message khi thiếu private key. `ProofOfFederation` tự động sinh key pairs cho validators, expose `public_key` property, thêm `block_hash` vào consensus metadata. `_verify_block_quorum` nhận optional `signer_id` để tránh quét event dư thừa.
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
    * **Block Overwrite**: Trong `hierachain/storage/sql_backend.py`, `save_block` query existing block theo `index`/`chain_name`, xóa và ghi đè thay vì silent `UNIQUE constraint` handling.
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

    * **Tuân thủ Mypy đầy đủ**: Giải quyết các cảnh báo static typing trên tất cả module: consensus, API, security, network, monitoring, error mitigation, storage, adapters, hierarchical, domains, core và cluster.
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
