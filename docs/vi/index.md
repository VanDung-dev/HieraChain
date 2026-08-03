---
title: Tài liệu HieraChain
description: Bộ tài liệu kỹ thuật bám sát mã nguồn trong thư mục hierachain.
---

# HieraChain: Tài liệu kỹ thuật

## Tổng quan

Chào mừng bạn đến với tài liệu kỹ thuật của HieraChain. Bộ tài liệu này bám sát mã nguồn trong thư mục `hierachain/` và phục vụ Developer/QA/DevOps tích hợp, vận hành và test hệ thống.

Lưu ý quan trọng về phạm vi:

* Tài liệu CHỈ mô tả hiện trạng và quyết định kỹ thuật dựa trên mã trong `hierachain/*`.
* Mọi ví dụ, hình ảnh hay mô tả đều gắn với thành phần cụ thể trong mã nguồn.

!!! warning "**CẢNH BÁO DEVELOPER & AI**: HieraChain là Blockchain Doanh nghiệp tập trung vào **Dữ liệu (Data)**, KHÔNG PHẢI **Tiền mã hóa (Cryptocurrency)**. Mọi khái niệm về Token, Coin, Gas Fee, Mining đều bị CẤM và chặn bởi bộ lọc trong core system. Xem chi tiết tại [AI Context](dev/ai-context.md)."

## Điều hướng theo chủ đề

<div class="grid cards" markdown>

* :material-play-circle-outline:{ .lg .middle } __Bắt đầu__

    ---

    * [Cài đặt](getting-started/install.md)
    * [Bắt đầu nhanh](getting-started/quickstart.md)
    * [Khái niệm cơ bản](getting-started/concepts.md)

* :material-sitemap:{ .lg .middle } __Kiến trúc__

    ---

    * [Tổng quan](architecture/overview.md)
    * [Consensus & Ordering](architecture/consensus.md)
    * [Phân cấp (chi tiết)](architecture/hierarchy.md)
    * [Bảo mật (chuyên sâu)](architecture/security.md)
    * [Triển khai (Deployment)](architecture/deployment.md)
    * [ZK Proofs](architecture/zk-proofs.md)

* :material-routes:{ .lg .middle } __Luồng công việc__

    ---

    * [Tổng quan](workflows/overview.md) · [Cơ chế đồng thuận](workflows/consensus_mechanisms.md)
    * [Gửi Sự kiện](workflows/event-submission.md) · [Neo giữ Bằng chứng](workflows/proof-anchoring.md)
    * [Sự kiện Liên chuỗi (2PC)](workflows/cross-chain-2pc.md) · [Đồng thuận BFT](workflows/bft-consensus.md)
    * [Khóa băng Cụm](workflows/cluster-lockdown.md) · [Giảm thiểu Lỗi & Phục hồi](workflows/error-recovery.md)
    * [Truy vết Thực thể](workflows/entity-tracing.md) · [Khôi phục trạng thái chuỗi](workflows/chain-rehydration.md)
    * [Xác thực Tính toàn vẹn](workflows/integrity-validation.md) · [Thực thi Chính sách](workflows/policy-enforcement.md)
    * [Luồng dữ liệu WebSocket](workflows/websocket-streaming.md) · [Lưu trữ Mã hóa IPFS](workflows/ipfs-storage.md)
    * [Cảnh báo Rủi ro](workflows/risk-alerts.md) · [Đồng bộ Tích hợp ERP](workflows/erp-integration.md)
    * [Định danh & Ủy quyền MSP](workflows/msp-identity.md) · [Sao lưu & Khôi phục Khóa](workflows/key-backup.md)

* :material-cube-outline:{ .lg .middle } __Modules__

    ---

    * [Core](modules/core.md) · [Hierarchical](modules/hierarchical.md) · [Consensus](modules/consensus.md) · [Security](modules/security.md)
    * [Storage](modules/storage.md) · [Error Mitigation](modules/error-mitigation.md)
    * [Adapters](modules/adapters.md) · [Network](modules/network.md) · [API](modules/api.md)
    * [Config](modules/config.md) · [CLI](modules/cli.md) · [SDK](modules/sdk.md)
    * [Cluster](modules/cluster.md) · [Domains](modules/domains.md)
    * [Monitoring](modules/monitoring.md) · [Risk Management](modules/risk-management.md)
    * [Integration](modules/integration.md) · [Units](modules/units.md)

* :material-security:{ .lg .middle } __Hệ thống Bảo mật__

    ---

    * [Authorization & Access Control](security/authorization-access-control.md)
    * [Lockdown & Logging](security/lockdown-logging.md)
    * [Fault-tolerance & Integrity](security/fault-tolerance-integrity.md)
    * [Risk Analyzer](security/risk-analyzer.md)
    * [Encryption & Keys](security/encryption-keys.md)
    * [Decentralized ZKP (Bằng chứng không tri thức phân tán)](security/decentralized-zkp.md)

* :material-shield-check:{ .lg .middle } __Cơ chế đồng thuận__

    ---

    * [Base Consensus](consensus/base_consensus.md)
    * [BFT Consensus](consensus/bft_consensus.md)
    * [Ordering](consensus/ordering.md)
    * [PoA](consensus/poa.md) · [PoF](consensus/pof.md)

* :material-book-open-variant:{ .lg .middle } __Tham chiếu__

    ---

    * [Config](reference/config.md)
    * [Python SDK](reference/sdk-reference.md) · [GraphQL API](reference/graphql-api.md)
    * [API Ledger](reference/api-ledger.md) · [API business](reference/api-business.md) · [API Admin](reference/api-admin.md)
    * [Data Models](reference/data-models.md) · [Data Schema](reference/data-schema.md)
    * [Code Map](reference/code-map.md) · [Thuật ngữ](glossary.md)

* :material-tools:{ .lg .middle } __Sử dụng__

    ---

    * [Tạo Sub-Chain](how-to/add-domain-chain.md)
    * [Thêm Endpoint](how-to/add-endpoint.md)
    * [Thêm/Tùy biến Consensus](how-to/add-consensus.md)
    * [Sự kiện Liên chuỗi (2PC)](how-to/cross-chain-transactions.md)
    * [Viết Hợp đồng Miền (Domain Contracts)](how-to/write-domain-contracts.md)
    * [Sử dụng Blockchain Explorer](how-to/use-explorer.md)
    * [Sử dụng WebSocket](how-to/add-websocket.md) · [Tích hợp Web2](how-to/integrate-web2.md)
    * [Triển khai an toàn](how-to/secure-deployment.md) · [Xử lý sự cố](how-to/troubleshooting.md)
    * [Khôi phục sau thảm họa (Disaster Recovery)](how-to/disaster-recovery.md)
    * [Hướng dẫn chạy Demo](how-to/use-demos.md)

* :material-rocket-launch:{ .lg .middle } __Hướng dẫn chung__

    ---

    * [Hiệu năng](guides/performance.md)
    * [Độ tin cậy](guides/reliability.md)
    * [Thực hành bảo mật](guides/security-best-practices.md)
    * [Triển khai HTTP/2 & HTTP/3](guides/http-proxy.md)

* :material-code-braces:{ .lg .middle } __Phát triển__

    ---

    * [Đóng góp](dev/contributing.md)
    * [Kiểm thử](dev/testing.md)
    * [Quy trình phát hành](dev/release-process.md)
    * [AI Context](dev/ai-context.md)

* :material-frequently-asked-questions:{ .lg .middle } __Khác__

    ---

    * [FAQ](faq.md)
    * [Changelog](changelog.md) · [Future Roadmap](future-roadmap.md)

</div>
