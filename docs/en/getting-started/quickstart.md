---
title: "Quickstart"
description: "Quickly set up the environment and try HieraChain in minutes."
icon: material/lightning-bolt
---

# Quickstart

This example uses a new local SQLite ledger and a single PoA signer. Run it in an empty working directory after installing the package. Do not reuse a directory containing an existing ledger or identity.

## Install

From a source checkout:

```bash
git clone https://github.com/VanDung-dev/HieraChain.git
cd HieraChain
uv sync --frozen --extra dev
source .venv/bin/activate
```

`uv sync` installs base dependencies; `--extra dev` adds development tools. On Windows, activate with `.venv\Scripts\Activate.ps1`.

## Provision a local signing identity

Run the following Python code once in the new working directory. It creates the identity required by `NodeIdentity` and the matching trusted public-key map. Existing files are rejected. Keep the private identity out of Git.

```python
import json
import os
from pathlib import Path

import zmq
from hierachain.security.security_utils import KeyPair

signing = KeyPair.generate()
transport_public, transport_secret = zmq.curve_keypair()
identity = {
    "node_id": "local-node",
    "msp_id": "LocalMSP",
    "signing_key": signing.private_key,
    "signing_public_key": signing.public_key,
    "transport_public_key": transport_public.decode(),
    "transport_secret_key": transport_secret.decode(),
}
for filename, data in (
    ("identity.json", identity),
    ("trusted_block_keys.json", {"local-node": signing.public_key}),
):
    fd = os.open(Path(filename), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump(data, output)
```

Set these variables in the same terminal **before importing HieraChain**. This POSIX shell example disables dotenv loading, P2P and API authentication only for an isolated local demonstration:

```bash
export HRC_ENV=dev
export HRC_ENV_FILE=/dev/null
export HRC_STORAGE_BACKEND=sqlite
export DATABASE_URL=sqlite:///local-ledger.db
export HRC_VALIDATOR_IDENTITY="$PWD/identity.json"
export HRC_BLOCK_TRUSTED_KEYS_FILE="$PWD/trusted_block_keys.json"
export HRC_NODE_ID=local-node
export HRC_P2P_ENABLED=false
export HRC_AUTH_ENABLED=false
export HRC_ENABLE_ZK_PROOFS=false
export HRC_MAINCHAIN_CONSENSUS=proof_of_authority
export HRC_BLOCK_INTERVAL=0
```

SQLite stores blocks in `local-ledger.db`; ordering journals live under `data/<chain-name>` relative to the working directory. Keep both for recovery. Production needs independently provisioned identities and API keys; see [Configuration](../reference/config.md) and [Secure Deployment](../how-to/secure-deployment.md).

## Record and anchor an event

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

`start_operation()` acknowledges submission to ordering. `flush_pending_and_finalize()` drains pending work; the entity query verifies the business event reached a finalized block. Proof submission must succeed after durable MainChain storage and readback. `close()` releases owned orderers and storage. Use a different chain name when extending an existing ledger.

PoA defaults to no additional block-spacing delay (`HRC_BLOCK_INTERVAL=0`). Sub-Chain ordering still batches up to 50 events or waits up to 1 second by default. PoF retains its separate 5-second interval configuration.

## Start the API

With the same configured identity and database, run:

```bash
python -m hierachain
```

The CLI equivalent is `hrc node start`. Open `http://localhost:2661/docs`. `/api/ledger/health` is liveness; `/api/ledger/ready` initializes/checks hierarchy recovery. Event acceptance is asynchronous; read finalized blocks before relying on a proof anchor.

## Next steps

* [Architecture](../architecture/overview.md)
* [API Ledger](../reference/api-ledger.md)
* [Feature support](../modules/hierarchical.md)
