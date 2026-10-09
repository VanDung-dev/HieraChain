# HieraChain Architecture

The implementation under `hierachain/` is the source of truth. The maintained architecture pages are paired by language:

* [English architecture](en/architecture/overview.md) · [Kiến trúc tiếng Việt](vi/architecture/overview.md)
* [Consensus and ordering](en/architecture/consensus.md) · [Đồng thuận và ordering](vi/architecture/consensus.md)
* [Storage](en/modules/storage.md) · [Lưu trữ](vi/modules/storage.md)
* [Feature support](en/modules/hierarchical.md) · [Phạm vi tính năng](vi/modules/hierarchical.md)
* [Code map](en/reference/code-map.md) · [Bản đồ mã nguồn](vi/reference/code-map.md)
* [Authorization](en/security/authorization-access-control.md) · [Phân quyền](vi/security/authorization-access-control.md)
* [Network integration](en/modules/network.md) · [Tích hợp mạng](vi/modules/network.md)

Sub-Chains order business events into trusted signed blocks; the MainChain stores proof anchors. Durable hierarchical storage uses SQLite or PostgreSQL. PoA and PoF are the active hierarchical consensus paths; BFT is a separate component. ZK production proving/verifying, contract execution and private-data writes are not implemented. Built-in vendor ERP connectors are simulation fixtures.

Event acceptance is distinct from block finality and durable proof visibility. Applications must integrate WebSocket broadcasts with ledger commits and upload off-chain IPFS payloads explicitly. The API P2P client does not automatically apply the optional secure connection manager's MSP handshake or message-signature checks. See the linked pages for those entry-point and deployment limits.

Use the [developer guide](DEV_GUIDE.md) for local setup and the [codebase reference](CODEBASE_REFERENCE.md) for current source paths. These repository-level guides sit outside the English/Vietnamese Zensical source directories, so locale builds do not validate them.

See [the documentation build guide](README.md) for the English and Vietnamese Zensical configurations.

Dual licensed under [Apache-2.0](../LICENSE-APACHE) or [MIT](../LICENSE-MIT).
