---
title: "Changelog"
description: "Nhật ký thay đổi chính của HieraChain và tài liệu kèm theo."
icon: material/history
---

# Changelog

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

Phiên bản này tập trung vào hạ tầng mạng cấp production, toàn vẹn mật mã học và kiểm thử stress doanh nghiệp, giới thiệu Node Identity với keypairs Ed25519/Curve25519, mã hóa ZeroMQ CURVE cho P2P, endpoint API v3 cho event an toàn, bộ kiểm thử stress/chaos toàn diện, hỗ trợ Podman/OrbStack và tái cấu trúc tài liệu song ngữ.

??? note "Improvements (7)"

    * **Node Identity & P2P Networking**: Giới thiệu `NodeIdentity`, mã hóa ZeroMQ CURVE, `send_direct`/`broadcast`, ping-pong heartbeat, tích hợp xuyên suốt BFT consensus, ordering service và API. Thêm cấu hình P2P (`P2P_ENABLED`, `P2P_HOST`, `P2P_PORT`).
    * **API v3 & Chữ ký số**: Endpoint `POST /api/v3/chains/{chain_name}/secure-events` với xác thực chữ ký Ed25519, giới hạn payload 1MB và độ sâu tối đa 10. Thêm trường `sender`/`signature` vào schema.
    * **Củng cố Consensus**: Chữ ký Ed25519 cho Proof of Federation, xác thực timestamp BFT 30 giây chống replay, xác minh block hash khi reconstruction, `block_interval` cấu hình được.
    * **Bảo mật**: Từ chối ZK proof giả trong production (cho phép test), so sánh hằng số thời gian HMAC, `threading.RLock` trong LockdownProtocol, tăng PBKDF2 lên 310,000 iterations.
    * **Hạ tầng Docker/K8s**: Hỗ trợ Podman (Compose và K8s), di chuyển lên OrbStack, API Gateway Nginx với stealth explorer, Web2 gateway node, Redis deployment, sinh identity động, chaos controller.
    * **Kiểm thử Stress & Chaos**: Bộ kiểm thử mới cho network partition, kill node, CPU throttling, WAN simulation, DDoS, memory leak soak, WebSocket load, storage benchmark.
    * **Tài liệu đa ngôn ngữ**: Hỗ trợ tiếng Việt và tiếng Anh, dịch 16 quy trình công việc, hướng dẫn sử dụng, tài liệu tham khảo API. Viết lại `AGENTS.md` với nguyên tắc hành vi AI.

??? warning "Fix (3)"

    * **Consensus & Storage**: Sửa xác thực block signature và sinh key tự động trong PoA, sửa return value mặc định trong BFT message handler, thêm validation proof_hash 64-ký tự SHA-256, xác thực toàn vẹn chain sau deserialization.
    * **API & SDK**: Cập nhật default base URL SDK từ 8000 sang 2661, validation tên sub-chain bằng regex, thread-safe cho RateLimiter, validation CID/nonce trong IPFS client.
    * **Build & Dependency**: Thêm `uvicorn[standard]`, `websockets`, `click`, `build`, `twine`; pin `urllib3==2.7.0`; nâng cấp `zensical` và `pymdown-extensions`; ghim Python 3.12 trong CI.

---

## v0.0.3 (2026-05-02)

Phiên bản này tập trung vào sự sẵn sàng cho production thông qua các cải thiện toàn diện về type safety trong `hierachain/`, triển khai Kubernetes StatefulSet, hạ tầng stress testing mạnh mẽ, và tăng cường xác thực bảo mật.

??? note "Improvements (6)"

    * **Tuân thủ Mypy đầy đủ**: Giải quyết các cảnh báo static typing trên các module consensus, API, security, network, monitoring, error mitigation, storage, adapters, hierarchical, domains, core và cluster.
    * **Xác thực Signature Ed25519**: Thực thi chiều dài 64-byte nghiêm ngặt cho signature Ed25519 để ngăn chặn việc bypass validation.
    * **Canonicalization JSON**: Triển khai canonicalization JSON mạnh mẽ cho xác minh signature để đảm bảo các hoạt động cryptographic nhất quán.
    * **Chuyển đổi StatefulSet**: Di chuyển từ Deployment sang StatefulSet cho deployment node ổn định với identity persistent.
    * **Bảo mật**: Thêm middleware giới hạn payload, validation timestamp 24h, ngăn chặn API key mặc định trong production, refactor HMAC lockdown protocol.
    * **Build & Packaging**: Di chuyển quản lý dependency sang uv, pin dependency versions, thêm uv.lock.

??? warning "Fix (1)"

    * **Testing & Ổn định**: Giới hạn message log trong BFT consensus, cải thiện stress test client, sửa bare except clauses trong integration tests, cải thiện IPFS connection handling.

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

??? warning "Fix (3)"

    * **Ổn định Consensus & Ordering**:

        * Giải quyết race condition quan trọng trong commit khối và xử lý sự kiện chờ trong `OrderingService`.
        * Đảm bảo các hoạt động lockdown và resume là atomic để ngăn chặn trạng thái không nhất quán trong quá trình bảo trì.
        * Ngăn chặn mất dữ liệu im lặng trong quá trình phục hồi transaction journal với xác thực đúng đắn.
        * Cải thiện logic phục hồi state với xác thực config và modularized recovery từ transaction journal.

    * **Core & Hierarchical Chain**:

        * Sửa race condition trong quản lý hierarchical chain và thêm thủ tục shutdown graceful.

    * **Build & Packaging**:

        * Nhúng template cấu hình vào module Python để sửa lỗi thiếu file `.env.HRC.example` khi cài đặt qua pip.

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
        * Cải thiện độ tin cậy của CI/CD với matrix testing và xử lý flaky tests.
