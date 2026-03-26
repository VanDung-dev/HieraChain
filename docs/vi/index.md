---
title: Tài liệu HieraChain
description: Bộ tài liệu kỹ thuật bám sát mã nguồn trong thư mục hierachain.
---

# HieraChain — Tài liệu kỹ thuật

## Tổng quan

Chào mừng bạn đến với tài liệu kỹ thuật của HieraChain. Bộ tài liệu này bám sát mã nguồn trong thư mục `hierachain/` và phục vụ Developer/QA/DevOps tích hợp, vận hành và test hệ thống.

Lưu ý quan trọng về phạm vi:

* Tài liệu CHỈ mô tả hiện trạng và quyết định kỹ thuật dựa trên mã trong `hierachain/*`.
* Mọi ví dụ, hình ảnh hay mô tả đều gắn với thành phần cụ thể trong mã nguồn.
* Ngôn ngữ ưu tiên: Tiếng Việt (thư mục `docs/vi`).

!!! warning "**CẢNH BÁO DEVELOPER & AI**: HieraChain là Blockchain Doanh nghiệp tập trung vào **Dữ liệu (Data)**, KHÔNG PHẢI **Tiền mã hóa (Cryptocurrency)**. Mọi khái niệm về Token, Coin, Gas Fee, Mining đều bị CẤM và chặn bởi bộ lọc trong core system. Xem chi tiết tại [AI Context](dev/ai-context.md)."

## Bắt đầu

* Cài đặt: xem Getting Started → [Cài đặt](getting-started/install.md)
* Bắt đầu nhanh: xem [Bắt đầu nhanh](getting-started/quickstart.md)
* Thuật ngữ: xem [Thuật ngữ](glossary.md)

## Điều hướng theo chủ đề

<div class="grid cards" markdown>

* :material-sitemap:{ .lg .middle } __Kiến trúc__

    ---

    * [Tổng quan](architecture/overview.md)
    * [Consensus & Ordering](architecture/consensus.md)
    * [Phân cấp (chi tiết)](architecture/hierarchy.md)
    * [Bảo mật (chuyên sâu)](architecture/security.md)
    * [Triển khai (Deployment)](architecture/deployment.md)
    * [ZK Proofs](architecture/zk-proofs.md)

* :material-cube-outline:{ .lg .middle } __Modules__

    ---

    * [Core](modules/core.md) · [Hierarchical](modules/hierarchical.md) · [Security](modules/security.md)
    * [Storage](modules/storage.md) · [Error Mitigation](modules/error-mitigation.md)
    * [Adapters](modules/adapters.md) · [Network](modules/network.md) · [API](modules/api.md)
    * [Config](modules/config.md) · [CLI](modules/cli.md) · [SDK](modules/sdk.md)
    * [Cluster](modules/cluster.md) · [Domains](modules/domains.md)
    * [Monitoring](modules/monitoring.md) · [Risk Management](modules/risk-management.md)
    * [Integration](modules/integration.md) · [Units](modules/units.md)

* :material-book-open-variant:{ .lg .middle } __Tham chiếu__

    ---

    * [Config](reference/config.md)
    * [Python SDK](reference/sdk-reference.md) · [GraphQL API](reference/graphql-api.md)
    * [API v1](reference/api-v1.md) · [API v2](reference/api-v2.md) · [API v3](reference/api-v3.md)
    * [Data Models](reference/data-models.md) · [Data Schema](reference/data-schema.md)
    * [Code Map](reference/code-map.md)

* :material-shield-check:{ .lg .middle } __Consensus__

    ---

    * [Base Consensus](consensus/base_consensus.md)
    * [BFT Consensus](consensus/bft_consensus.md)
    * [Ordering](consensus/ordering.md)
    * [PoA](consensus/poa.md) · [PoF](consensus/pof.md)

* :material-rocket-launch:{ .lg .middle } __Hướng dẫn chung__

    ---

    * [Hiệu năng](guides/performance.md)
    * [Độ tin cậy](guides/reliability.md)
    * [Thực hành bảo mật](guides/security-best-practices.md)
    * [Triển khai HTTP/2 & HTTP/3](guides/http-proxy.md)

* :material-tools:{ .lg .middle } __Sử dụng__

    ---

    * [Tạo Sub-Chain](how-to/add-domain-chain.md)
    * [Thêm Endpoint](how-to/add-endpoint.md)
    * [Thêm/Tùy biến Consensus](how-to/add-consensus.md)
    * [Giao dịch Liên chuỗi (2PC)](how-to/cross-chain-transactions.md)
    * [Viết Hợp đồng Miền (Domain Contracts)](how-to/write-domain-contracts.md)
    * [Sử dụng Blockchain Explorer](how-to/use-explorer.md)
    * [Sử dụng WebSocket](how-to/add-websocket.md) · [Tích hợp Web2](how-to/integrate-web2.md)
    * [Triển khai an toàn](how-to/secure-deployment.md) · [Xử lý sự cố](how-to/troubleshooting.md)
    * [Khôi phục sau thảm họa (Disaster Recovery)](how-to/disaster-recovery.md)
    * [Hướng dẫn chạy Demo](how-to/use-demos.md)

* :material-code-braces:{ .lg .middle } __Phát triển__

    ---

    * [Đóng góp](dev/contributing.md)
    * [Kiểm thử](dev/testing.md)
    * [Quy trình phát hành](dev/release-process.md)
    * [AI Context](dev/ai-context.md)

* :material-frequently-asked-questions:{ .lg .middle } __Khác__

    ---

    * [FAQ](faq.md) · [Glossary](glossary.md)
    * [Changelog](changelog.md) · [Future Roadmap](future-roadmap.md)

</div>

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * Mã nguồn tài liệu tham chiếu: `hierachain/*` (Python >= 3.10 theo `pyproject.toml`).
    * Script CLI: `hrc` (định nghĩa tại `[project.scripts]` trong `pyproject.toml`).
    * API server: `hierachain/api/server.py` (có thể chạy bằng `python -m hierachain.api.server`).

    **DECISION**

    * Dùng Markdown, tách rõ các khối FACT / DECISION / ASSUMPTION / INVARIANT / EDGE CASES.
    * Tổ chức nội dung theo khung chuẩn thống nhất.

    **ASSUMPTION**

    * Người đọc đã cài Python 3.10+ và có quyền truy cập internet để cài dependencies.
    * Môi trường phát triển sử dụng `venv` hoặc công cụ tương đương.

    **INVARIANT**

    * FACT phải bám sát mã nguồn hiện tại (tên file, chữ ký API, đường dẫn).
    * Không pha trộn nội dung tiếp thị trong tài liệu kỹ thuật.

    **EDGE CASES**

    * Khác biệt shell giữa Windows (PowerShell) và Linux/macOS (bash) khi kích hoạt venv.
    * Mạng nội bộ hạn chế có thể ảnh hưởng quá trình cài gói.
