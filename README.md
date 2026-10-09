# HieraChain - Hierarchical Enterprise Ledger

![Python Versions](https://img.shields.io/badge/python-3.10%20|%203.11%20|%203.12%20|%203.13%20|%203.14-blue)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE-APACHE)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE-MIT)
[![PyPI version](https://img.shields.io/pypi/v/HieraChain.svg)](https://pypi.org/project/HieraChain/)

**English** | [Tiếng Việt](README.vi.md)

## Overview

HieraChain is a Python ledger for business events. Domain Sub-Chains record events in signed, hash-linked blocks; a MainChain anchors their proofs. `HierarchyManager` coordinates chain lifecycle, recovery and proof submission.

## Implemented capabilities

* Apache Arrow event tables, indexed entity/event queries and asynchronous ordering batches.
* Ed25519 signatures with an operator-approved trusted-key map, durable SQLite/PostgreSQL storage and ordering journals.
* PoA by default; configurable PoF with validator rotation. BFT components are separate from the MainChain/Sub-Chain runtime.
* REST, GraphQL, WebSocket, Python sync/async clients and CLI tools.
* API-key authentication when enabled, organization/channel policies, audit logging and optional AES-256-GCM encrypted IPFS payloads.

## Current limits

* ZK proving/verifying supports development mocks; the production backend is unimplemented.
* Contract registration keeps the implementation or CID reference and metadata in API-process memory. Contract execution and private-data writes return HTTP 501 for registered resources, or HTTP 404 for unknown contracts/collections after request validation and authorization.
* Built-in SAP/Oracle/Dynamics connectors require `simulation_mode=True` and provide simulation fixtures. Real ERP adapters must be supplied by the application.
* Redis supports auxiliary adapters, but cannot serve as the durable hierarchical block backend.
* PoF's ordinary block validation checks the leader signature; automatic multi-party quorum collection and failover are not provided by that path.
* WebSocket subscriptions receive messages sent through broadcast helpers; applications must connect those helpers to ledger events and block commits.
* Event and contract REST routes accept inline data or existing IPFS CID references. Applications must upload off-chain payloads explicitly; these routes do not automatically move large payloads to IPFS.

See [feature support](docs/en/modules/hierarchical.md) and [consensus scope](docs/en/workflows/consensus_mechanisms.md).

## Quick start

### Install from source

```bash
git clone https://github.com/VanDung-dev/HieraChain.git
cd HieraChain
uv sync --frozen --extra dev
source .venv/bin/activate
```

Without uv, create and activate `.venv`, then install:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

For the published package, use `python -m pip install HieraChain`. Its release may differ from the current source checkout. Base dependencies and optional `dev`/`doc` extras are defined in `pyproject.toml`.

### Configure and use the ledger

First complete the [local signing identity and SQLite setup](docs/en/getting-started/quickstart.md). It creates a fixed identity, trusted-key map and environment variables. Run the setup and example in the same empty working directory; SQLite and ordering-journal paths are relative to that directory:

```python
from hierachain.hierarchical import HierarchyManager

manager = HierarchyManager()
try:
    assert manager.create_sub_chain("supply_chain", "supply_chain")
    chain = manager.get_sub_chain("supply_chain")
    assert chain.register_entity("PROD-001", {"product": "sample"})
    assert manager.start_operation(
        "supply_chain", "PROD-001", "production_start", {"quantity": 100}
    )
    chain.flush_pending_and_finalize(timeout=10.0)
    assert any(
        event["event"] == "operation_start"
        for event in chain.get_events_by_entity("PROD-001")
    )
    assert manager.submit_proof_to_main_chain("supply_chain")
finally:
    manager.close()
```

Event acceptance acknowledges ordering; it does not establish block finality. This example explicitly drains ordering and verifies the finalized entity event before submitting a durable proof.

PoA defaults to `HRC_BLOCK_INTERVAL=0`; batching still affects latency. PoF keeps a separate 5-second interval. Measure committed-event throughput and p95/p99 latency with the [performance guide](docs/en/guides/performance.md).

### Start the API

Use the configured environment from the quickstart:

```bash
python -m hierachain
```

Open `http://localhost:2661/docs`. Check `/api/ledger/ready` for hierarchy recovery readiness. The isolated quickstart disables API-key authentication with `HRC_AUTH_ENABLED=false`; production requires authentication, provisioned API keys and signing identities. See [configuration](docs/en/reference/config.md).

## Documentation

* [English documentation](https://docs.hierachain.org/) · [Vietnamese documentation](https://docs.hierachain.org/vi/)
* [Installation](docs/en/getting-started/install.md) · [Architecture](docs/en/architecture/overview.md)
* [REST Ledger API](docs/en/reference/api-ledger.md) · [Python SDK](docs/en/reference/sdk-reference.md)
* [Testing](docs/en/dev/testing.md) · [Build documentation](docs/README.md)

## Technical scope

| Area | Current implementation |
|------|------------------------|
| Python | 3.10, 3.11, 3.12, 3.13, 3.14 |
| Hierarchical consensus | PoA / PoF; separate BFT components |
| Block signatures | Ed25519, including genesis |
| Hierarchical storage | SQLite / PostgreSQL |
| Off-chain encryption | Optional IPFS AES-256-GCM |

## License

Dual licensed under [Apache-2.0](LICENSE-APACHE) or [MIT](LICENSE-MIT). You may choose either license.
