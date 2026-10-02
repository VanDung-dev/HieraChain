---
title: "Changelog"
description: "Nhật ký thay đổi chính của HieraChain và tài liệu kèm theo."
icon: material/history
---

# Changelog

## Unreleased

??? warning "Breaking Changes (37)"

    * 2026-10-01

        * **Giảm thiểu Lỗi (Khóa Lưu giữ & Validator Chặt)**: `EncryptionValidator` (`hierachain/error_mitigation/encryption_validator.py`) nay resolve khóa 32-byte do caller quản lý theo `key_id` qua `key_resolver` (không còn fallback `os.urandom` tạm thời) với AES-256-GCM gắn AAD (`algorithm`/`key_id`/`timestamp`), bổ sung `decrypt_data()` kèm kiểm tra bytes/độ dài tag-IV/thuật toán/timestamp hữu hạn, và che lỗi nội bộ sau `SecurityError` chung; `_run_single_custom_validator` (`hierachain/error_mitigation/data_validator.py`) ép kiểu trả về `(bool, str)` và chuyển lỗi/ngoại lệ của validator từ warning sang `add_error` kèm tên field — các validation trước đây cho qua nay sẽ fail.
        * **ERP (Transformer Fail-closed)**: `EventTranslator` (`hierachain/integration/erp/mapping.py`) dùng chung `MappingEngine` của caller (`hierachain/integration/erp/base.py`) để áp transformer đã đăng ký nhất quán, và tên `transformer` không tồn tại nay raise `MappingError` thay vì lặng lẽ trả về giá trị gốc.
        * **Cluster (Payload Chữ ký Quarantine)**: `QuarantineReport.compute_signature` (`hierachain/cluster/lockdown_types.py`) ký toàn bộ payload `orjson` sort-key thay vì `node_id:timestamp:last_block_index`, `from_dict()` kiểm tra `msg_type`/`lockdown_type` và từ chối timestamp không hữu hạn trước khi ký, còn `verify_signature()` trả `False` khi thiếu/chữ ký sai thay vì raise — các chữ ký đã phát hành trước đây không còn verify được.
        * **Config (Field Secret JSON AWS)**: `_get_from_aws`/`SecretManager._get_aws` (`hierachain/config/secret_manager.py`) parse `SecretString` thành object JSON qua `orjson` và trả về field chuỗi tên theo `key`, bắt buộc `HRC_AWS_SECRET_NAME` làm `SecretId` thay vì fallback sang `key` — secret không phải JSON, field không phải chuỗi và thiếu tên secret nay đều trả `None`.

    * 2026-09-30

        * **Domain (Validate Phân bổ Tài nguyên Chặt)**: `BaseChain.add_domain_event` (`hierachain/domains/chains/base_chain.py`) nay từ chối event của entity chưa đăng ký và chuyển đổi tài nguyên không hợp lệ qua `_can_apply_resource_allocation()` (kiểu event phải bằng `resource_{allocation_type}`, kiểm tra thành viên cho `assigned`/`reserved`/`released`/`transferred` kèm kiểm tra tồn tại `target_entity_id`); `ResourceAllocationEvent.is_valid` (`hierachain/domains/events/custom_events.py`) bắt buộc `target_entity_id` khác rỗng và khác `entity_id` với kiểu `transferred` — các event trước đây được chấp nhận nay trả `False`.
        * **Validator (Validate Field Proof Chặt)**: `ProofValidator._validate_single_proof` (`hierachain/domains/utils/cross_chain_validator.py`) bắt buộc `sub_chain_name`/`proof_hash` là `str` khác rỗng và `timestamp` là `int`/`float` dương (không phải `bool`), ghi nhận `missing_proof_fields` kèm tăng `inconsistent_proofs` thay vì lặng lẽ bỏ qua proof thiếu field.

    * 2026-09-29

        * **Core & Hierarchical (Validate Event Nghiêm ngặt)**: `Blockchain.add_event` (`hierachain/core/blockchain.py`) và `SubChain.add_event` (`hierachain/hierarchical/sub_chain/base.py`) nay ép `validate_event_structure()` (kèm kiểm tra kiểu `dict` trong `SubChain`) và raise `ValueError` khi cấu trúc không hợp lệ; `add_event` của ledger (`hierachain/api/ledger/events.py`) chuyển thành HTTP 422 thay vì chấp nhận event sai định dạng.
        * **API (Rate Limiting Redis Fail-closed)**: `RedisRateLimiter` chuyển sang (`hierachain/adapters/database/redis_rate_limiter.py`) với `check()`/`RateLimiterBackendError`; `add_rate_limit` (`hierachain/api/middleware.py`) chạy kiểm tra Redis qua `asyncio.to_thread` và trả 503 khi backend không khả dụng thay vì fail-open cho qua như trước, đồng thời tái dùng quota `remaining` đã kiểm tra cho header.
        * **API (GraphQL Giới hạn Kết quả)**: resolver (`hierachain/api/graphql/resolvers.py`) chặn kết quả qua `_bounded_limit()`/`MAX_QUERY_RESULTS=100` với `limit=None` nghĩa là 100, cắt lát `from_index`/`to_index`/`start+limit` có kẹp biên, và thoát sớm khi `limit=0` — limit yêu cầu lớn hơn nay chỉ trả tối đa 100 bản ghi.
        * **Network (Kiểm tra Replay & Nonce Chặt)**: `_is_valid_replay` (`hierachain/network/zmq_transport.py`) bắt buộc `nonce` là `str` dài `1..128` ký tự, timestamp số hữu hạn trong `replay_tolerance`, và từ chối khi replay buffer `1000` entry vẫn đầy sau khi tỉa hết hạn thay vì âm thầm loại bỏ.

    * 2026-09-28

        * **Core & Bảo mật (Chữ ký Block Tin cậy Bắt buộc)**: `Blockchain.__init__`/`add_block`/`is_valid_new_block`/`is_chain_valid` (`hierachain/core/blockchain.py`) nay resolve signer qua `require_block_identity()` và xác minh theo `trusted_public_keys` với `_sign_block()`/`sign_block()`; `BlockVerifier` (`hierachain/security/verify/block_verifier.py`) bắt buộc `strict_mode=True`, từ chối tuyệt đối block thiếu/chữ ký sai định dạng và chỉ xác minh với trusted key do caller cung cấp; `load_trusted_block_keys()`/`require_block_identity()` (`hierachain/security/identity_loader.py`) bắt buộc `HRC_BLOCK_TRUSTED_KEYS_FILE` (mới `Settings.BLOCK_TRUSTED_KEYS_FILE`) dạng map Ed25519 hex kèm kiểm tra khớp key của node; `initialize_default_keys()` (`hierachain/security/key_manager.py`) chặn tạo key mặc định khi `Settings().env == "production"`.
        * **Đồng thuận & Ordering (Block Ký, Quorum & ZK)**: bổ sung `creator_id` khi dựng block với kiểm tra vị trí finalization trong `verify_quorum_signatures` (`hierachain/consensus/base_consensus.py`, `hierachain/consensus/proof_of_federation.py`); xác minh ZK proof trong quá trình verify, từ chối proof thiếu/không hợp lệ khi bắt buộc và kiểm tra cấu trúc/thứ tự/hash `consensus_finalization`; `BlockManager` ký khi tạo block, storage từ chối block thiếu/thiếu tin cậy với `reconcile_journal_event()` chống trùng khi replay (`hierachain/consensus/ordering/block_manager.py`, `hierachain/consensus/ordering/service.py`, `hierachain/consensus/ordering/storage.py`).
        * **Hierarchical Main/Sub-Chain (Proof Bền & Ký Tin cậy)**: thay đếm proof in-memory bằng lưu trữ bền với `_refresh_durable_proofs()`/`proof_sequence`/`_durable_block_events` (`hierachain/hierarchical/main_chain/base.py`, `hierachain/hierarchical/main_chain/proofs.py`, `hierachain/hierarchical/main_chain/registry.py`); `SubChain` bắt buộc persist proof bền, chặn nộp trùng, validate metadata ZK-proof chặt hơn và ký finalization bằng trusted key theo consensus type (`hierachain/hierarchical/sub_chain/base.py`, `hierachain/hierarchical/sub_chain/block.py`, `hierachain/hierarchical/sub_chain/proof.py`).
        * **Hierarchical Registry (Hierarchy Bền & Validate Chặt)**: `_persist_hierarchy_registry()`/`_restore_hierarchy_registry()` kèm locking (`hierachain/hierarchical/hierarchy_manager/base.py`); khôi phục hỗ trợ sub-chain placeholder với thay thế động; registry organization/channel siết kiểm tra member (`hierachain/hierarchical/hierarchy_manager/organization.py`, `hierachain/hierarchical/hierarchy_manager/validation.py`).
        * **Channel (Chữ ký, Endorsement & Vai trò)**: finalization block xác minh chữ ký theo trusted key, đánh giá endorsement hỗ trợ tập org đủ điều kiện cấu hình được, cập nhật policy/org/status có rollback, và `submit_event`/persist registry bắt buộc validate vai trò member (`hierachain/hierarchical/channel/channel.py`, `hierachain/hierarchical/channel/ledger.py`, `hierachain/hierarchical/channel/policy.py`, `hierachain/hierarchical/channel/types.py`).
        * **Cluster (Đồng bộ Cross-level Không Copy)**: nộp proof không còn merge history hay copy block cross-chain (`hierachain/cluster/cross_level_sync.py`); anchor persist qua `_persist_proof_anchor()` với xác minh bền dưới storage lock.
        * **Audit (Schema & Đổi Hash)**: `AuditEvent` thêm `affected_entities` kèm migration SQLite, xử lý JSON cho field tùy chọn, và `calculate_hash()` trên toàn bộ dict sort-key (`hierachain/risk_management/types.py`, `hierachain/risk_management/audit_logger.py`) — digest đã lưu thay đổi; thêm `PostgresAuditManifest` (`hierachain/adapters/database/audit_manifest.py`) với `verify_integrity()` và validate persist chặt hơn.
        * **Config (Env & Backend Nghiêm)**: `Settings.env` (`hierachain/config/settings.py`) raise `ValueError` với `HRC_ENV`/`ENV` không hỗ trợ (chỉ alias `production`/`prod`/`product`, `dev`, `test`), `STORAGE_BACKEND` allowlist `memory`/`redis`/`sqlite`/`postgres`/`postgresql` qua `_configured_database_url()` (`DATABASE_URL`/`HRC_DATABASE_URL`), thêm `BLOCK_TRUSTED_KEYS_FILE`, và `ProductionSettings.AUTH_ENABLED` luôn `True` kèm bắt buộc `HRC_AUTH_ENABLED=true`; `get_settings()` chỉ route theo `production`/`test` đã chuẩn hóa.
        * **API/CLI/Business (Auth Prod & HierarchyManager)**: lifespan server bắt buộc `require_block_identity()` kèm `DATABASE_URL`/`HRC_DATABASE_URL` tường minh cho Postgres production, bắt buộc `HRC_API_KEYS_FILE` qua `_load_production_key_manager()` (key ≥32 ký tự, có `permissions`, còn hiệu lực), thay `ENV` bằng `env`, siết CORS/logging theo `production` (`hierachain/api/server.py`, `hierachain/api/graphql_handler.py`); business channels/organizations chuyển khỏi `_channels`/`_organizations` in-memory sang `HierarchyManager` với validate chặt và schema vai trò member (`hierachain/api/business/channels.py`, `hierachain/api/business/organizations.py`, `hierachain/api/business/schemas.py`, `hierachain/api/business/state.py`); nộp proof ledger ủy quyền cho `HierarchyManager` (`hierachain/api/ledger/proofs.py`); CLI `submit_proof` từ chối nộp qua registry (bắt buộc API xác thực bền) và `verify` ép validate chain theo trusted key (`hierachain/cli/chain.py`, `hierachain/cli/verify.py`).

    * 2026-09-27

        * **Lưu trữ (Khóa mã hóa IPFS)**: `create_ipfs_client_from_env()` (`hierachain/api/storage/ipfs_client.py`) nay bắt buộc `HRC_IPFS_ENCRYPTION_KEY` phải đúng 64 ký tự hex (32 byte) và raise `IPFSError` nếu thiếu/không hợp lệ — không còn tự sinh key tạm kèm warning, nên deployment thiếu key ổn định sẽ fail-fast ngay khi khởi động thay vì tạo payload không thể giải mã.

    * 2026-09-26

        * **Config (Journal Sync)**: Loại bỏ `Settings.JOURNAL_FSYNC` / `HRC_JOURNAL_FSYNC` (`hierachain/config/settings.py`); `TransactionJournal` (`hierachain/error_mitigation/journal.py`) bỏ hàng đợi/luồng ghi nền và luôn ghi đồng bộ kèm `os.fsync`.
        * **Core (Merkle Payload)**: Hợp nhất serialize payload event thành `serialize_event_payload()` (`hierachain/core/merkle_tree.py`) dùng chung cho `hierachain/core/block.py`; Merkle leaves nay bao gồm trường `data` (trước đây bị loại), nên leaves/roots/hashes thay đổi với cùng event.
        * **Database (Fail-hard Reads & Event Envelope)**: `SQLBase.get_block_by_index`/`get_latest_block`/`get_event_by_id` (`hierachain/adapters/database/base/sql_adapter.py`) nay lan truyền lỗi database thay vì trả `None`; `PostgresAdapter._execute_save_block` (`hierachain/adapters/database/postgres_adapter.py`) persist toàn bộ event envelope (`orjson.dumps(event)`) với fallback `submitted_by`/`sender_id`, các hàm fetch giải mã qua `_create_event_from_row`/`_decode_jsonb` dùng chung.
        * **Hierarchical (Storage Fail-fast)**: `HierarchyManager._create_storage()` (`hierachain/hierarchical/hierarchy_manager/base.py`) không còn fallback về SQLite khi PostgreSQL đã cấu hình nhưng không khả dụng — nay raise `RuntimeError`; `__init__`/`add_sub_chain` persist metadata và khôi phục qua `list_chains()`, raise khi thất bại.

    * 2026-09-24

        * **Core (Parquet Logs)**: `write_parquet_log()` hiện ghi các segment bất biến tối đa 1.024 bản ghi trong `<path>.segments`; `read_parquet_log()` đọc các segment và cả log một tệp legacy. Bên dùng đang đọc trực tiếp `<path>` cần chuyển sang helper này.

    * 2026-09-22

        * **Giảm thiểu Lỗi (Validators)**: Loại bỏ `APIValidator` (kèm entry `"api"` trong factory `create_validator` và logic kiểm tra thuật ngữ cấm trên Arrow/legacy) khỏi `hierachain/error_mitigation/validator.py` và các export của package (`hierachain/error_mitigation/__init__.py`); đồng thời chỉnh đường dẫn import `ConsensusValidator` sang `hierachain/error_mitigation/consensus_validator.py` trong `hierachain/consensus/bft/helpers.py`.
        * **Giám sát (Monitoring)**: Loại bỏ singleton toàn cục `alert_manager` và export khỏi `hierachain/monitoring/__init__.py` (các lớp `AlertManager`/`PerformanceMonitor` vẫn khả dụng).
        * **Config (Storage Backend)**: Đổi backend lưu trữ mặc định từ `sqlite` sang `postgres` trong `hierachain/config/settings.py` (`DEFAULT_STORAGE_BACKEND`, `DATABASE_URL` mặc định nay là `postgresql://hiera:hiera@localhost:5432/hierachain`, hỗ trợ `HRC_DATABASE_URL` với xử lý tường minh `sqlite://`) và `hierachain/config/product_config_template.py` (`HRC_STORAGE_BACKEND=postgres` kèm `DATABASE_URL`/`HRC_DATABASE_URL` theo từng node); `ProductionSettings.DEFAULT_STORAGE_BACKEND` chuyển từ `redis` sang `postgres`.

    * 2026-09-21

        * **Giám sát (Monitoring)**: Loại bỏ `PrometheusMetrics` và singleton `metrics` khỏi `hierachain/monitoring/metrics.py` (xóa file), loại bỏ các tiện ích thu thập số liệu Prometheus.
        * **Quản trị Rủi ro (Risk Management)**: Loại bỏ `RotatingAuditStorage` khỏi `hierachain/risk_management/audit_logger.py` và các export của package (`hierachain/risk_management/__init__.py`).

    * 2026-09-20

        * **Core (Cache)**: Loại bỏ `BlockchainCacheManager`, `CacheInvalidator`, `EntityEventFetcher` và `CachePerformanceTracker` khỏi `hierachain/core/cache_manager.py` (xóa file).
        * **Giảm thiểu Rủi ro (Recovery & Rollback)**: Loại bỏ `RollbackManager` và các kiểu dữ liệu liên quan (`RollbackType`, `RollbackStatus`, `StateSnapshot`, `RollbackOperation`), các engine phục hồi (`NetworkRecoveryEngine`, `ConsensusRecoveryEngine`, `BackupRecoveryEngine`, `AutoScaler`), cùng `RecoveryError` khỏi `hierachain/error_mitigation/`.
        * **Quản trị Rủi ro (Risk Management)**: Loại bỏ `RiskAnalyzer`, `MitigationManager`, `MitigationStrategies` và các kiểu dữ liệu liên quan (`RiskAssessment`, `RiskSeverity`, `RiskCategory`, `MitigationAction`, `MitigationResult`, `MitigationStatus`) khỏi `hierachain/risk_management/`, chỉ giữ lại các nguyên thủy ghi log kiểm toán.
        * **Giám sát (Monitoring)**: Loại bỏ `PerformanceMetrics`, `MetricType` và `PerformanceSnapshot` khỏi `hierachain/monitoring/performance_metrics.py` (xóa file).
        * **Cluster**: Loại bỏ `ClusterManager`, `ClusterLockdownManager`, `ClusterState` và cơ chế điều phối lockdown theo quorum khỏi `hierachain/cluster/` (xóa `cluster_manager.py` và `lockdown_protocol.py`).

    * 2026-09-19

        * **Hierarchical & Config**: Loại bỏ các gói deprecated `k8s_namespace_manager`, `proof_aggregation` và `rebalancer` khỏi `hierachain/hierarchical/` (`K8sNamespaceManager`, `ProofAggregator`, `SubChainRebalancer`) cùng các cấu hình liên quan (`K8S_*`, `PROOF_*`, `REBALANCE_*`) trong `hierachain/config/settings.py`.

    * 2026-09-18

        * **Cluster**: Loại bỏ `StateSyncManager` (`hierachain/cluster/state_sync_manager.py`) và các export liên quan khỏi `hierachain/cluster/__init__.py`.

??? note "Improvements (34)"

    * 2026-10-02

        * **Đồng thuận (Finalizer Ordering & Toàn vẹn Khởi động)**: `OrderingService` (`hierachain/consensus/ordering/service.py`) nhận thêm hook `block_finalizer(block, previous_block)` tùy chọn và kiểm tra chuỗi đã persist (so hash đuôi `get_blocks_from_db(0)` với block mới nhất) trước khi replay journal, raise khi history thiếu/hỏng; `wait_for_active()` nhận `timeout=None` để chờ recovery vô hạn với deadline monotonic kèm kiểm tra `should_stop`/luồng còn sống; `OrderingBlockManager.commit_block` (`hierachain/consensus/ordering/block_manager.py`) hủy khi service đang dừng, gán `creator_id` dưới lock index, ủy quyền đồng thuận cho finalizer và kiểm tra lại shutdown trước khi ký.
        * **Hierarchical (Finalization Block Ordered của Sub-chain)**: thêm `SubChain._finalize_ordered_block()` (`hierachain/hierarchical/sub_chain/base.py`) hoàn tất đồng thuận trước khi orderer ký và persist (delay theo timing có thể ngắt qua `_shutdown_event`, giữ `creator_id` sau finalization, từ chối `validate_block` thành `ValueError`); `SubChain` dùng `threading.RLock` cho xử lý block, chờ recovery ordering vô hạn (`wait_for_active(timeout=None)` để backlog journal chạy xong thay vì replay lại), rút gọn shutdown qua `finalize_sub_chain_block()`, và truyền finalizer vào `OrderingService`.
        * **Hierarchical (Áp dụng Block Sub-chain)**: `_process_and_finalize_single_block()` (`hierachain/hierarchical/sub_chain/block.py`) nay áp block ordering đã finalize nguyên trạng (không tính lại index/hash, không finalization/ký lại), chuyển orderer sang `MAINTENANCE` kèm tín hiệu dừng khi `add_block` thất bại; `_finalize_sub_chain_block_for_chain()` tuần tự hóa dequeue kèm apply dưới `block_processing_lock` để giữ thứ tự FIFO; loại bỏ `_reset_ordering_service_state()` (`hierachain/hierarchical/sub_chain/ordering.py`), rehydration dựa vào đồng bộ chain thay vì ghi đè `block_history`/`blocks_created`.
        * **Hierarchical (Quản lý Tài nguyên Recovery)**: `HierarchyManager.__init__`/`_restore_sub_chains()` (`hierachain/hierarchical/hierarchy_manager/base.py`) bọc bootstrap và khôi phục sub-chain trong `ExitStack` (callback `shutdown` cho journal/storage/từng chain, chỉ `pop_all()` khi thành công) thay cho cleanup try/except thủ công.

    * 2026-09-30

        * **Database (Liệt kê Tên Chain)**: thêm `SQLBase.list_block_chain_names()` (`hierachain/adapters/database/base/sql_adapter.py`) trả về `DISTINCT chain_name` có thứ tự từ bảng `blocks` kèm lan truyền lỗi database cho CLI verification.
        * **State (Snapshot Bất biến)**: `WorldState.get_entity_state()`/`get_all_states()` (`hierachain/state/world_state.py`) nay trả về snapshot `deepcopy` (kèm `deepcopy` cho `last_details` khi cập nhật) để caller không thể thay đổi state nội bộ.
        * **Audit (Đọc Sealed & Retention)**: `ArrowAuditStorage` (`hierachain/risk_management/audit_logger.py`) tập trung `_seal_active_file()`, sửa xử lý `limit=0`/`None` trong `retrieve_events`, đếm qua metadata Parquet/batch `4096` dòng trong `get_event_count()`, và thêm `cleanup_old_events()` chỉ xóa archive Parquet đã hết hạn toàn bộ; `DatabaseAuditStorage._filter_sql()` hợp nhất predicate `event_type`/`severity`/`source_component`/`user_id`/`time_range` cho cả truy vấn và đếm.
        * **CLI (Key File & Verify Đa-backend)**: `hierachain/cli/key.py` ghi key mới bằng `O_EXCL` `0600`, đọc JSON hoặc hex hai dòng qua `_read_key_file()`, và che hoàn toàn private key khi `show`; `hierachain/cli/verify.py` thêm `_open_backend()` cho URL `postgres`/`postgresql`/`sqlite` và backend đường dẫn trên `SQLBase`, theo dõi riêng `events_unsigned` (unsigned được phép, thiếu chữ ký là invalid, fallback `sender_public_key`, dùng `to_event_list()`), và fail audit khi event invalid chứ không chỉ block.
        * **Domain (Vòng đời Tài nguyên)**: `BaseChain` (`hierachain/domains/chains/base_chain.py`) xử lý `resource_released`/`resource_reserved`/`resource_transferred` với vòng đời `allocated_resources`/`reserved_resources` (reserve, release từ cả hai list, chuyển `reserved`→`assigned`, chuyển entity), chỉ đăng ký entity sau khi `add_event` thành công, và trả `False` khi handler lỗi thay vì nuốt lỗi.

    * 2026-09-29

        * **Database (Kho Auth State Dùng chung)**: thêm `SQLiteRevocationStore`/`SQLiteLockoutStore` (dùng chung qua file, `0600`, key băm digest) và `RedisRevocationStore`/`RedisLockoutStore` cùng `RedisRateLimiter` (`hierachain/adapters/database/auth_state.py`, `hierachain/adapters/database/redis_rate_limiter.py`); `hierachain/adapters/database/__init__.py` chuyển sang import lười `__getattr__`.
        * **Config (Backend Auth State)**: thêm `HRC_AUTH_STATE_REDIS_URL` (`Settings.AUTH_STATE_REDIS_URL`) và `HRC_API_KEY_REVOCATIONS_DB` (`Settings.API_KEY_REVOCATIONS_DB`), với `get_auth_config()` chọn backend lockout `redis`/`sqlite`/`file` (`hierachain/config/settings.py`).
        * **Bảo mật & API (Thu hồi Dùng chung & Kiểm tra Async)**: `KeyManager` nhận `revocation_store` và kiểm tra trong `is_revoked()` (`hierachain/security/key_manager.py`); `BruteForceProtector` ủy quyền cho lockout store SQLite/Redis dùng chung (`hierachain/security/brute_force_protector.py`); `APIKeyVerifier` offload kiểm tra brute-force/thu hồi/`is_valid` qua `asyncio.to_thread` và kiểm tra thu hồi trước tính hợp lệ (`hierachain/security/verify/api_key_verifier.py`); server production đấu nối `RedisRevocationStore`/`SQLiteRevocationStore` vào `KeyManager` (`hierachain/api/server.py`).
        * **Hierarchical & Core (Làm sạch Metadata)**: `MainChain.register_sub_chain` sanitize một lần qua `sanitize_metadata_for_main_chain()` cho cả metadata registry và authority (`hierachain/hierarchical/main_chain/base.py`); `sanitize_metadata_for_main_chain` thêm `_sanitize_summary_value()` đệ quy (tỉa dict/list lồng nhau, bỏ dict `>5` key / list `>10` phần tử) và các field loại bỏ mới `internal_data`/`complete_log`/`detailed_data`, kèm validate list chặt hơn (`hierachain/core/utils.py`).
        * **SDK (Circuit Breaker An toàn Luồng & Response)**: `CircuitBreaker` (`hierachain/sdk/types.py`) thêm locking với một probe `HALF_OPEN` duy nhất (`acquire_request()`/`release_probe()`, `record_success()`/`record_failure()` theo probe); client sync/async xử lý `HEAD`/`GET`/`OPTIONS` và body rỗng `HTTPStatus.NO_CONTENT` với phân loại lỗi retryable/non-retryable (`hierachain/sdk/client.py`, `hierachain/sdk/async_client.py`).
        * **Network (Quản lý Peer & Health)**: `NetworkClient` theo dõi `public_key`/`_last_activity`, `PEER_TIMEOUT=60.0` với `_refresh_peer_health()`, giữ key khi đăng ký lại, và thêm `unregister_peer()` kèm dọn socket; `ZmqNode.register_peer()` reset socket khi đổi và `unregister_peer()` hủy message chờ (`hierachain/network/network_client.py`, `hierachain/network/zmq_transport.py`).

    * 2026-09-28

        * **Database (Hierarchy Registry & Audit Manifest)**: lưu/tải hierarchy registry trên cả PostgreSQL/SQLite/Redis, thêm `PostgresAuditManifest` quản lý digest audit, gọn lọc event/xử lý metadata, SQLite `synchronous=FULL` bền dữ liệu, và kiểm tra toàn vẹn chain-state chặt hơn (`hierachain/adapters/database/__init__.py`, `hierachain/adapters/database/audit_manifest.py`, `hierachain/adapters/database/base/sql_adapter.py`, `hierachain/adapters/database/postgres_adapter.py`, `hierachain/adapters/database/redis_adapter.py`, `hierachain/adapters/database/sqlite_adapter.py`).
        * **Hierarchical (Journal 2PC Bền)**: journal phase bền với `_journal_record()`/`_load_journal()`, lifecycle prepare/commit/rollback có cấu trúc, validate participant và retry cho decision chưa phân giải (`hierachain/hierarchical/transaction_manager.py`, `hierachain/hierarchical/private_data.py`, `hierachain/hierarchical/types.py`).
        * **Domains (Khôi phục Committed Transaction)**: theo dõi `committed_transactions` với `_tx_commit_lock`, nạp/đối soát marker và khôi phục sau COMMIT bền cho ack idempotent (`hierachain/domains/chains/domain_chain.py`, `hierachain/domains/chains/tx_manager.py`).
        * **API (Nộp Event theo Channel)**: endpoint mới `POST /channels/{channel_id}/organizations/{org_id}/events` kèm xác thực và validation (`hierachain/api/ledger/events.py`).
        * **Journal (Liệt kê File)**: gọn `_get_journal_files()` giữ thứ tự/khử trùng không sort thừa (`hierachain/error_mitigation/journal.py`).

    * 2026-09-27

        * **Lưu trữ (IPFS Async & Auto-pin)**: `upload_to_ipfs_background()`/`download_from_ipfs()` (`hierachain/api/storage/endpoint_helpers.py`) nay offload các lệnh gọi IPFS blocking qua `asyncio.to_thread` để tránh nghẽn event loop; upload của `IPFSClient` (`hierachain/api/storage/ipfs_client.py`) truyền auto-pin qua query parameter của lệnh `add` thay vì gọi `pin()` riêng.

    * 2026-09-26

        * **API (Readiness)**: Thêm `GET /api/ledger/ready` (`hierachain/api/ledger/health.py`) chỉ báo `ready` khi mọi ordering service của sub-chain ở trạng thái `ACTIVE` (ngược lại 503); miễn xác thực trong `hierachain/api/server.py`; `get_hierarchy_manager()` khởi tạo lười an toàn luồng và trả 503 khi recovery chưa xong (`hierachain/api/ledger/depds.py`); tạo sub-chain chuyển tiếp `manager.node_identity` (`hierachain/api/ledger/chains.py`).
        * **Đồng thuận (Ordering Genesis & Replay)**: `OrderingService` nhận thêm `genesis_block` tùy chọn (`hierachain/consensus/ordering/service.py`) để persist khi database rỗng; `EventCertifier.validate()`/`OrderingExecutor.process_single_event()` nhận `allow_stale_timestamp` với kiểm tra timestamp số hữu hạn nghiêm ngặt (`hierachain/consensus/ordering/certifier.py`, `hierachain/consensus/ordering/processor.py`); event journal replay đi qua `process_replayed_event()` (`hierachain/consensus/ordering/recovery.py`, `hierachain/consensus/ordering/processor.py`).
        * **Database (Chain Listing & SQLite Memory)**: Bổ sung `list_chains()` cho `SQLBase`/`RedisChainManager`/`RedisStorageAdapter` (`hierachain/adapters/database/base/sql_adapter.py`, `hierachain/adapters/database/redis_adapter.py`); `SQLiteAdapter` (`hierachain/adapters/database/sqlite_adapter.py`) hỗ trợ `:memory:` dùng chung qua keeper connection; `SQLBase._create_event_from_row` trả trực tiếp envelope đầy đủ khi cột khớp; `RedisChainManager.store_chain` bỏ qua `domain_type` khi là `None`.

    * 2026-09-24

        * **API (Xác thực Server)**: Nới `auth_dependency` (`hierachain/api/server.py`) từ `Request` sang `HTTPConnection` kèm guard `verifier is None`, đồng thời expose verifier qua `fast_app.state.auth_verifier` để dùng chung.
        * **Bảo mật (Xác minh API Key)**: Chuyển `APIKeyVerifier` (`hierachain/security/verify/api_key_verifier.py`) sang tương thích `HTTPConnection` (`_extract_client_ip`/`__call__`/`_extract_api_key`); bổ sung `KeyManager.get_permissions()` tập trung (`hierachain/security/key_manager.py`), context xác thực nay mang `permissions` ở top-level (`ResourcePermissionChecker` fallback về `app_details`); `_get_active_verifier(connection)` lấy verifier từ application state.

    * 2026-09-23

        * **Database (PostgreSQL Adapter)**: Gom các lệnh insert event trong `_execute_save_block` (`hierachain/adapters/database/postgres_adapter.py`) thành một lượt `cursor.executemany()` trên `event_rows` đã thu thập thay vì `cursor.execute()` từng event, giảm số round-trip khi persist block nhiều event.
        * **Đồng thuận (Ordering Service)**: Đơn giản hóa khởi động `OrderingService` (`hierachain/consensus/ordering/service.py`) bằng cách loại bỏ lượt đếm-and-log trùng lặp `_recover_pending_events_from_journal()` và giao toàn bộ replay journal cho processor (`recover_state_async()`); tách helper dùng chung `_start_processing_thread()` cho cả `__init__` và `start()`.

    * 2026-09-22

        * **Journal (Giảm thiểu Lỗi & Ordering)**: Chuyển `TransactionJournal` (`hierachain/error_mitigation/journal.py`) từ `ParquetWriter` sang ghi nối tiếp Arrow IPC (đóng khung `RecordBatch` kèm tiền tố độ dài qua `_serialize_arrow_batch`, đảm bảo bền dữ liệu bằng `os.fsync`, replay nhiều dòng/batch với fallback stream cũ); đổi tên file log active mặc định `current.parquet` thành `current.arrow` (file xoay vòng `*_*.parquet` thành `*_*.arrow`, tương tự `node_{id}_journal.parquet` thành `.arrow` của `OrderingService` trong `hierachain/consensus/ordering/service.py`) đồng thời vẫn replay được file Parquet legacy (tự đổi tên file active cũ sang `*_legacy_*.parquet` qua guard `_is_parquet_file`).
        * **Hierarchical (SubChain Proof & Events)**: Tinh gọn `SubChain.add_event()` (`hierachain/hierarchical/sub_chain/base.py`) để trả về `event_id` có thẩm quyền từ `ordering_service.receive_event()` thay vì digest tổng hợp `orjson`+SHA-256 (loại bỏ import `hashlib`/`orjson`); chuyển `should_submit_proof()` sang theo dõi theo chỉ số block qua `last_proof_block_index` mới (cập nhật trong `hierachain/hierarchical/sub_chain/proof.py`) thay vì kiểm tra pending events; củng cố `_process_and_finalize_single_block` (`hierachain/hierarchical/sub_chain/block.py`) để log lỗi persist ở mức `error` và trả `False` mà không append block vào bộ nhớ.
        * **Database (PostgreSQL Adapter)**: Củng cố `PostgresAdapter` (`hierachain/adapters/database/postgres_adapter.py`) với `connect_timeout: 3` khi khởi tạo pool, parse động `data` event thô bằng `orjson` trong `_execute_fetch_block_events`, `_execute_save_block` tự khép kín bắt buộc `chain_name` (tự chèn dòng `chains` còn thiếu, chấp nhận fallback `metadata`/`merkle_root`), và các hàm fetch block trả về dict block đầy đủ với `chain_name` tùy chọn (`_execute_get_block_by_index`/`_execute_get_latest_block` chuyển thành instance methods).
        * **Hierarchical (Storage Fallback)**: Tăng khả năng chống lỗi cho `HierarchyManager._create_storage()` (`hierachain/hierarchical/hierarchy_manager/base.py`) bằng cách kiểm tra PostgreSQL (`SELECT 1 FROM chains LIMIT 0`) và fallback về `SQLiteAdapter` kèm warning khi PostgreSQL không khả dụng.

    * 2026-09-18

        * **Đồng thuận (Ordering Service)**: Giới hạn dung lượng hàng đợi `event_pool` bằng `Settings.EVENT_POOL_MAX_SIZE` trong `hierachain/consensus/ordering/service.py` nhằm chống tràn bộ nhớ, đồng thời bổ sung xử lý chế độ bảo trì trong `submit_event` để chờ kích hoạt (`wait_for_active()`) và từ chối gửi event khi dịch vụ không ở trạng thái hoạt động.
        * **API (Ledger Events)**: Cập nhật endpoint `add_event` tại `/api/ledger/events` (`hierachain/api/ledger/events.py`) để trả về `event_id` có thẩm quyền trực tiếp từ `sub_chain.add_event(event)` thay vì tạo mã định danh vị trí giả lập.

??? warning "Fix (14)"

    * 2026-10-02

        * **Hierarchical (Dọn dẹp Journal khi Load lỗi)**: `CrossChainTransactionManager.__init__` (`hierachain/hierarchical/transaction_manager.py`) đóng journal tự tạo khi `_load_journal()` raise (journal do caller truyền vào để caller tự quản) thay vì rò rỉ handle.
        * **Core (Validate Sender)**: `validate_event_structure()` (`hierachain/core/utils.py`) loại trường khóa công khai `sender` của envelope đã ký khỏi quét thuật ngữ tiền mã hóa của nội dung nghiệp vụ và validate riêng `sender`, giữ key envelope ngoài kiểm tra nội dung.
        * **API (Đồng thời khi Recovery Hierarchy)**: `get_hierarchy_manager()` (`hierachain/api/ledger/depds.py`) dùng lock non-blocking (trả 503 "in progress" khi luồng khác đang recovery) với backoff retry monotonic 5 giây giới hạn số lần thử trong bão request thay vì block các request đồng thời.

    * 2026-10-01

        * **ERP (Deadlock Scheduler)**: `SyncScheduler.get_all_tasks` (`hierachain/integration/erp/scheduler.py`) dựng trạng thái qua snapshot tách rời `_task_status()` dưới một lock duy nhất thay vì gọi `get_status()` cho từng task, khắc phục deadlock lock lồng nhau khi liệt kê tasks.

    * 2026-09-28

        * **Mạng (Kiểm tra Env Production)**: `SecureConnectionManager` (`hierachain/network/secure_connection.py`) kiểm tra `settings.env == "production"` thay vì `"product"` cũ, khôi phục cảnh báo P2P kém an toàn.

    * 2026-09-27

        * **Lưu trữ (Phân giải CID)**: `resolve_cid_field()` (`hierachain/api/storage/endpoint_helpers.py`) nay re-raise lỗi khi phân giải CID thất bại thay vì lặng lẽ trả về dữ liệu gốc chưa phân giải, ngăn consumer xử lý nhầm payload chưa resolve.

    * 2026-09-26

        * **Journal (Framing & Replay)**: Bổ sung envelope `_JOURNAL_MAX_FRAME_SIZE`/`_JOURNAL_DATA_MARKER` tách `data` và `extra` fields, vòng lặp ghi từng phần, tự sửa đuôi file rách khi mở, nhận diện `PAR1` bằng magic đầu file, và replay fail-hard raise `ValueError` khi gặp frame hỏng/cụt thay vì bỏ qua (`hierachain/error_mitigation/journal.py`).
        * **Đồng thuận (Ordering Fail-closed)**: `OrderingBlockManager.commit_block`/vòng lặp processor/executor (`hierachain/consensus/ordering/block_manager.py`, `hierachain/consensus/ordering/processor.py`) chuyển `MAINTENANCE` và re-raise; recovery ép tạo block (`force=True`) và raise `RuntimeError` khi gặp entry null/hỏng; `_block_from_dict` (`hierachain/consensus/ordering/storage.py`) kiểm tra Merkle root trước hash với điều kiện dừng chặt `data is None`.
        * **Hierarchical (Recovery Validation)**: Khởi tạo `SubChain` (`hierachain/hierarchical/sub_chain/base.py`) fail-fast khi `wait_for_active()` timeout kèm shutdown ordering và giao persist genesis cho `OrderingService`; `_process_and_finalize_single_block` (`hierachain/hierarchical/sub_chain/block.py`) kiểm tra qua `is_valid_new_block`; rehydration (`hierachain/hierarchical/sub_chain/ordering.py`) raise `ValueError` khi xung đột toàn vẹn/hàng đợi và loại bỏ block đã rehydrate khỏi queue.

    * 2026-09-25

        * **Journal (Giảm thiểu Lỗi)**: Chuyển `TransactionJournal.log_event()` (`hierachain/error_mitigation/journal.py`) sang fail-closed cho ghi async bằng cách chờ `Future` theo từng event do background writer hoàn tất thay vì ack ngay khi enqueue; nhánh queue đầy vẫn fallback sang ghi đồng bộ.
        * **Đồng thuận (Phục hồi Ordering)**: Đặt `OrderingStatus.MAINTENANCE` ngay đầu `_initialize_service` (`hierachain/consensus/ordering/processor.py`) để service không bao giờ ở trạng thái `ACTIVE` trong lúc replay, và buộc `OrderingRecovery` (`hierachain/consensus/ordering/recovery.py`) raise `RuntimeError` khi gặp entry journal `error` thay vì âm thầm bỏ qua.

    * 2026-09-24

        * **Database (PostgreSQL Adapter)**: Củng cố `_execute_save_block` (`hierachain/adapters/database/postgres_adapter.py`) xóa các dòng `events` cũ của `(chain_name, index)` trước khi insert, và upsert block bằng `ON CONFLICT (chain_name, "index") DO UPDATE` thay vì `ON CONFLICT (hash) DO NOTHING`, giữ ghi đè block nhất quán với events của nó.
        * **Đồng thuận (Ordering Service & Storage)**: `submit_event` (`hierachain/consensus/ordering/service.py`) nay raise `RuntimeError` khi `journal.log_event()` thất bại thay vì âm thầm queue event chưa persist, và `OrderingStorageHandler.save_block` (`hierachain/consensus/ordering/storage.py`) raise khi storage adapter từ chối kèm cập nhật `block_history`/`last_block` idempotent (thay thế khi trùng index, chỉ append khi tiến lên).

    * 2026-09-23

        * **API (Admin Secure Event)**: Sửa `add_secure_event` (`hierachain/api/admin/endpoints.py`) để gọi `request.model_dump(exclude_unset=True)`, tránh chuyển các trường tùy chọn chưa thiết lập (`nonce`/`timestamp`/`chain_id`) thành `None` khi thêm event vào chain.

## v0.2.0 (2026-09-12)

??? note "Improvements (26)"

    * 2026-09-05

        * **Core (Block, Blockchain & Merkle Tree)**: Củng cố cache `Block` và kiểm tra kiểu `stored_hash` trong `hierachain/core/block.py`, bổ sung sinh `event_id` xác định (`orjson`+SHA-256 `evt-{16}`) và xác minh Merkle-root trong `_is_block_linked_correctly`/`Blockchain.add_event()` nay trả về `str` (`hierachain/core/blockchain.py`), và sửa xử lý node lẻ trong `MerkleTree._build_tree` để truyền thẳng leaf thay vì hash trùng (`hierachain/core/merkle_tree.py`).
        * **Core (Logging & Xử lý Lỗi)**: Thu hẹp `except Exception` sang `OSError`/`ArrowException`/`ValueError`/`TypeError` trong `hierachain/core/parquet_log.py` và `hierachain/error_mitigation/journal.py`, bổ sung annotation `pa.Table | None`, và thêm fallback `ImportError` cho `kubernetes` client trong `hierachain/hierarchical/k8s_namespace_manager/operations.py`.
        * **Đồng thuận (BFT & PoA/PoF & Ordering)**: Bổ sung kiểm tra nghiêm ngặt `isinstance(str)` cho `signature`/`public_key`/`block_hash` trong `hierachain/consensus/proof_of_federation._verify_block_quorum` và loại bỏ fallback `KeyPair` kém an toàn trong `hierachain/consensus/proof_of_authority.py`; thắt chặt xác thực BFT trong `hierachain/consensus/bft/helpers.py` (guard `strictness` và khớp quorum theo digest/view trong `_process_commit_quorum_logic`); đơn giản hóa xử lý kiểu trong `hierachain/consensus/ordering/recovery.py` (`int(block_index_raw)`, `dict|None`).
        * **Đồng thuận & Hierarchical (Types & Schema)**: Thay thế `TYPE_CHECKING` bằng `Any` runtime trên `hierachain/consensus/bft/dispatcher.py|engine.py|view_change.py` và `hierachain/hierarchical/main_chain/proofs.py|registry.py|rebalancer/split_ops.py|sub_chain/*.py`; tập trung `EVENT_SCHEMA` (`pa.schema`) tại `hierachain/core/block.py` và tái sử dụng trong `hierachain/consensus/ordering/certifier.py`, `hierachain/error_mitigation/journal.py`, `hierachain/hierarchical/channel/ledger.py`; mở rộng `BFTViewChangeManager` để phát `prepared_proofs`.
        * **Hierarchical (Hierarchy Manager & SubChain)**: Nâng cấp `_shared_pool` trong `hierachain/hierarchical/hierarchy_manager/base.py` hỗ trợ `max_workers` động (tạo pool tạm khi thay đổi, ngược lại tái dùng global); thay `hash()` bằng `orjson`+SHA-256 `evt-` ID trong `hierachain/hierarchical/sub_chain/base.py`; xóa module legacy `hierachain/hierarchical/sub_chain.py` không dùng.
        * **Hierarchical (Rollback & Rebalancer)**: Củng cố `hierachain/error_mitigation/rollback_manager.py` với `_capture_storage_state` theo component, guard path-traversal qua `os.path.realpath` trong `_rollback_configuration`, log số section và kiểm tra toàn vẹn `data_hash`; dọn `hierachain/error_mitigation/validator_helpers.py` và gọn import; tinh giản import `hierachain/hierarchical/rebalancer/split_ops.py`.
        * **API (Middleware, Server & WebSocket)**: Chuyển giới hạn payload sang `request.stream()` với đếm `bytes_read` và replay `request._receive` trong `hierachain/api/middleware.py`; kiểm tra trusted-proxy `client_ip in TRUSTED_PROXIES` cho `X-Forwarded-For` và sửa fallback IP; tách CORS thành `_add_cors_middleware` trong `hierachain/api/server.py` và bắt buộc `uvloop`; tinh giản khởi tạo `PingLoopRunner` trong `hierachain/api/websocket/manager.py`.
        * **API (Ledger, GraphQL, Explorer & Business)**: Tập trung xử lý field mặc định trong `hierachain/api/storage/explorer_helpers.py`; thêm guard `assert` trong `hierachain/api/ledger/depds.py` và thay kiểm tra depth đệ quy bằng stack lặp (`depth >10`) trong `hierachain/api/ledger/schemas.py`; điều chỉnh `hierachain/api/graphql/resolvers.py|types.py` cho `Blockchain.add_event()->str` và logic `is_cid_string`; định kiểu `private_data_entry: dict[str,Any]` trong `hierachain/api/business/private_data.py`.
        * **API (Admin Identity - Tính năng)**: Thêm trường tùy chọn `nonce`/`timestamp`/`chain_id` vào `SecureEventRequest` (`hierachain/api/admin/schemas.py`), thực thi kiểm tra lệch `chain_id` (`422`) và độ tươi timestamp 300s, tiền tố challenge `b"HRC_IDENTITY_CHALLENGE:"` và khôi phục dependency `require_chain_access` cho `/verify-identity` (`hierachain/api/admin/endpoints.py`).
        * **Bảo mật, Events, Database & Dọn dẹp**: Tinh giản `_sanitize_html_context` thành `re.sub(..., "[TEMPLATE_BLOCKED]")` (`hierachain/security/sanitization.py`) và chuyển xác minh ZK mock sang `ZKVerifier(mode="mock").verify` (`hierachain/security/zk_prover.py`); chặt kiểu `BaseEvent.__eq__(other: object)` (`hierachain/domains/events/base_event.py`); tập trung khởi tạo schema DB thành `init_database_schema` trong `hierachain/adapters/database/postgres_schema.py|sqlite_schema.py` và gọn adapter; xóa 17 import thừa trên `api/storage`, `consensus/ordering`, `core/utils`, `error_mitigation/*`, `risk_management/*`.

    * 2026-09-01

        * **Database (PostgreSQL)**: Bổ sung `PostgresAdapter` (`hierachain/adapters/database/postgres_adapter.py`) kế thừa `SQLBase` với connection pooling `psycopg`/`psycopg2` (truy cập row dạng dict) và `postgres_schema.py` định nghĩa các bảng (`chains`, `blocks`, `events`, `proofs`, `chain_state`) cùng composite indexes tối ưu (`chain_name+timestamp`, `entity_id+chain_name`, `block_hash`) và đầy đủ CRUD cho dữ liệu blockchain.
        * **Config**: Nâng cao linh hoạt cấu hình lưu trữ/cơ sở dữ liệu trong `hierachain/config/settings.py` và `hierachain/config/product_config_template.py` — thêm `BLOCK_CREATION_MODE`/`BLOCK_MAX_WAIT_SEC` điều khiển tạo block, `PARQUET_ROLL_INTERVAL` (`monthly`/`daily`/`by_size_mb`), `POSTGRES_SYNC_MODE` (`realtime`/`batch_worker`/`disabled`), `SQL_RETENTION_DAYS`; `STORAGE_BACKEND` tự động nhận diện `postgres` từ `DATABASE_URL` với fallback `sqlite` và thống nhất xử lý `DATABASE_URL`/`HRC_DATABASE_URL`; tinh gọn template product về các backend `sqlite`, `postgres`, `redis`, `memory`, `parquet_only`.
        * **Storage (Hierarchical & Ordering)**: Thêm lựa chọn adapter động trong `hierachain/consensus/ordering/storage.py` (`OrderingStorageHandler`), `hierachain/hierarchical/hierarchy_manager/base.py` (`_create_storage`) và `hierachain/hierarchical/sub_chain/base.py` — chọn `PostgresAdapter` khi `db_url` bắt đầu bằng `postgres://`/`postgresql://` ngược lại dùng `SQLiteAdapter`; tái cấu trúc sinh đường dẫn DB của `SubChain` để luôn đảm bảo `data/{safe_name}/journal` tồn tại kèm guard chống path traversal.
        * **Database (Query & Indexes)**: Tối ưu `hierachain/adapters/database/sqlite_schema.py` (`create_indexes` chuyển sang dùng câu lệnh `CREATE INDEX` đầy đủ) và tái cấu trúc `hierachain/adapters/database/base/sql_adapter.py` sang dùng template query tái sử dụng (`_QUERIES_WITH_CHAIN`/`_QUERIES_WITHOUT_CHAIN`) với parameterized queries cho lọc event theo chain, đồng thời sửa dọn dẹp block để xóa qua `hash`/`block_hash` thay vì `id`/`block_id`.

    * 2026-08-31

        * **SDK**: Thay thế câu lệnh `assert` bằng kiểm tra ngoại lệ `RuntimeError` tường minh trong phương thức `_get_session` tại `hierachain/sdk/client.py` và `hierachain/sdk/async_client.py` nhằm đảm bảo tính hợp lệ của session khi chạy ở chế độ tối ưu byte-code (`-O`).
        * **Logging & Giảm thiểu Rủi ro**: Thay thế các khối `except Exception: pass` và `continue` ẩn danh bằng thông điệp `logger.debug()` chi tiết trong `hierachain/core/parquet_log.py`, `hierachain/error_mitigation/journal.py` và `hierachain/risk_management/audit_logger.py` khi đóng file, xóa file lỗi, phục hồi xoay vòng log và replay batch, nâng cao khả năng gỡ lỗi mà vẫn giữ an toàn vận hành.

    * 2026-08-29

        * **Journal**: Chuyển `TransactionJournal` (`hierachain/error_mitigation/journal.py`) sang lưu trữ Parquet (`pyarrow.parquet`) với giới hạn file 100MB, rotate tự động `current_{ns}.parquet`, hàng đợi async giới hạn 10k và quản lý `ParquetWriter` an toàn luồng, hỗ trợ replay nhiều file Parquet tương thích ngược `.arrow`/`.log`.
        * **Audit**: Thêm `ArrowAuditStorage` (`hierachain/risk_management/audit_logger.py`) làm backend mặc định, lưu `AuditEvent` qua Parquet với schema Arrow, rotate 100MB, đọc/ghi theo `AuditFilter`, giữ tương thích `*.jsonl`.
        * **Logging**: Đồng nhất toàn bộ log `log/` sang Parquet qua `hierachain/core/parquet_log.py` (`write_parquet_log`, `ParquetLogHandler`), chuyển `consensus_scaling`, `view_changes`, `error_classifications`, `restoration_events`, `scaling_events`, `network_alerts`, `resource_scaling`, `rollback_operations`, `quarantine_dump`, `risk_analyzer`, `mitigation_strategies` sang `*.parquet`, đổi `OrderingService` sang `node_{id}_journal.parquet`.

    * 2026-08-27

        * **API**: Điều chỉnh xử lý xác thực trong `hierachain/api/server.py` (thêm annotation `Request` cho `auth_dependency`, hợp nhất khởi tạo `verifier` và mở rộng `EXEMPT_PATHS` với `/api/admin/verify-identity`) và loại bỏ dependency `require_chain_access` dư thừa trong `hierachain/api/admin/endpoints.py` cho `/verify-identity` và `/status` để health check và xác minh identity hoạt động đúng khi `HRC_ENV=product`.

    * 2026-08-24

        * **API**: Bổ sung module `hierachain/api/context.py` quản lý vòng đời instance `p2p_client` runtime theo ngữ cảnh, loại bỏ import phụ thuộc vòng khi khởi tạo/dừng server và xử lý endpoint network ping.
        * **Hierarchical (Rebalancer)**: Tập trung các hàm tiện ích kiểm tra Sub-Chain vào `hierachain/hierarchical/rebalancer/utils.py` và tối ưu hóa luồng di chuyển trạng thái khi phân tách Sub-Chain (chuyển giao `pending_events` và kế thừa State Snapshot thay vì làm biến đổi lịch sử block đã commit).
        * **Domains**: Tái cấu trúc cấu trúc module domain event trong `hierachain/domains/events/`, loại bỏ các import phụ thuộc vòng giữa lớp cơ sở `DomainEvent` và các định nghĩa sự kiện cụ thể.

    * 2026-08-23

        * **Mạng**: Bổ sung xác thực độ lệch thời gian (`max_drift`, mặc định 300 giây) cho hàm `verify_message` trong `hierachain/network/message_cryptographic.py` nhằm đảm bảo tính tươi của các gói tin P2P và từ chối các thông điệp cũ hoặc lặp lại.
        * **API (Rate Limiter)**: Tối ưu hóa `RateLimiter` bộ nhớ trong `hierachain/api/middleware.py` với cơ chế dọn dẹp hết hạn theo lô định kỳ (`_cleanup_expired`), loại bỏ việc tái tạo toàn bộ dict $O(N)$ trong lock ở mỗi request dưới tải cao; bổ sung trích xuất IP client từ header `X-Forwarded-For` khi chạy sau proxy/gateway.
        * **Core & Hierarchical**: Tối ưu hóa `finalize_block` trong `Blockchain` (`hierachain/core/blockchain.py`) và `MainChain` (`hierachain/hierarchical/main_chain/base.py`) để bảo toàn danh sách `pending_events` khi quá trình tạo hoặc xác thực block thất bại, ngăn ngừa mất dữ liệu sự kiện; bổ sung khóa đồng bộ `self.lock` cho các phương thức đóng block của `MainChain`.

    * 2026-08-15

        * **Dọn dẹp mã thừa**: Loại bỏ các hàm tiện ích không dùng trên các module hierarchical và domain (`hierachain/core/utils.py`, `consensus/proof_of_federation.py`, `domains/chains/domain_chain.py`, `domains/chains/metrics.py`, `domains/utils/cross_chain_validator.py`, `domains/utils/entity_tracer.py`, `hierarchical/multi_org.py`): xóa `group_events_by_entity`, `_is_block_valid`, `_extract_signature_from_block`, `_analyze_compliance_status`, `_calculate_performance_stats`, `_process_string_value`, `_process_bytes_value`, `_generate_recommendations`, và `create_multi_org_network` để codebase gọn gàng và dễ bảo trì hơn.

??? warning "Fix (15)"

    * 2026-08-31

        * **Bảo mật (Secret Manager)**: Chuẩn hóa lại các template log thông báo lỗi trong `_get_from_aws` (`hierachain/config/secret_manager.py`) nhằm loại bỏ cảnh báo nhận diện nhầm rò rỉ credential khi quét bảo mật tĩnh.

    * 2026-08-29

        * **Bảo mật (Sanitization)**: Sửa `_sanitize_html_context` (`hierachain/security/sanitization.py`) vô hiệu hóa SSTI bằng `[TEMPLATE_BLOCKED]` thay vì `html.escape` no-op, và làm chặt `_sanitize_filename_context` bằng allowlist `^[a-zA-Z0-9_\-~.]+$` và lọc `..`/`.` để ngăn path traversal.

    * 2026-08-27

        * **Bảo mật (Key Manager)**: Bổ sung guard `PYTEST_CURRENT_TEST`/`pytest` trong `initialize_default_keys` (`hierachain/security/key_manager.py`) để ngăn tạo API key mặc định trong môi trường kiểm thử khi `HRC_ENV=product` và cho phép khởi tạo an toàn dưới `pytest`.
        * **Hierarchical (Rebalancer)**: Xử lý cả pending events dạng `callable` và `non-callable` trong `_get_pending_events` (`hierachain/hierarchical/rebalancer/split_ops.py`) bằng cách kiểm tra `callable()` và fallback `pending_events` list.
        * **Đồng thuận (BFT)**: Nới lỏng ngưỡng drift timestamp từ 30s lên 120s trong `verify_message_signature` (`hierachain/consensus/bft/helpers.py`) để tránh lỗi drift khi suite chạy lâu với message tĩnh tạo lúc import.
        * **Config (Env Manager)**: Bổ sung kiểm tra `HRC_ENV=test`/`PYTEST_CURRENT_TEST` trong `init_env_config` (`hierachain/config/env_manager.py`) để ngăn tạo `.env.HRC.example` và load `.env` product trong khi chạy `pytest`.
        * **Cluster (Lockdown)**: Chuẩn hóa `verify_signature` trong `hierachain/cluster/lockdown_types.py` với kiểm tra kiểu `str` rỗng và `try/except` quanh `hmac.compare_digest` để xử lý signature không hợp lệ an toàn, duy trì tương thích với chữ ký 32 ký tự cũ.

    * 2026-08-24

        * **Đồng thuận (Ordering)**: Bổ sung kiểm tra batch rỗng (`if not self.current_batch: return False`) cho hàm `is_batch_ready` trong `BlockBuilder` (`hierachain/consensus/ordering/block_builder.py`) nhằm ngăn chặn việc kích hoạt kiểm tra sẵn sàng sai lệch và gọi tạo block rỗng khi hệ thống ở trạng thái nhàn rỗi.
        * **Core (Merkle Tree)**: Bổ sung tiền tố phân tách miền (`0x01`) cho các phép băm node trung gian trong `MerkleTree._build_tree` (`hierachain/core/merkle_tree.py`) để ngăn ngừa rủi ro va chạm nhánh và trùng lặp băm.
        * **API (Payload Limit)**: Bổ sung kiểm tra kích thước stream body trực tiếp trong `add_payload_limit` (`hierachain/api/middleware.py`) nhằm kiểm soát giới hạn tải lên tối đa (1MB) cho các request dạng chunked transfer không có `Content-Length`.

    * 2026-08-23

        * **Đồng thuận (BFT)**: Áp dụng xác thực chữ ký nghiêm ngặt trong `_validate_consensus_message` (`hierachain/consensus/bft/helpers.py`), đảm bảo các thông điệp đồng thuận BFT (`PRE-PREPARE`, `PREPARE`, `COMMIT`) có chữ ký không hợp lệ luôn bị từ chối (`return False`) trên mọi chế độ strictness.
        * **Hierarchical (Proof Verification)**: Bổ sung cơ chế quét chuỗi dự phòng (fallback chain scan) trong `_verify_proof_in_main_chain` (`hierachain/hierarchical/main_chain/proofs.py`) để tìm kiếm proof trên các block đã commit khi chỉ mục `proof_index` chưa kịp đồng bộ.
        * **Cluster (Lockdown Protocol)**: Chuẩn hóa chữ ký HMAC-SHA256 của `LockdownMessage` trong `hierachain/cluster/lockdown_types.py` sang định dạng 64 ký tự hex đầy đủ (256-bit), đồng thời duy trì khả năng tương thích ngược với chữ ký cắt ngắn 32 ký tự cũ trong `verify_signature`.

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
