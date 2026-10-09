---
title: "Add/Customize Consensus"
description: "Guide to configuring PoA/PoF or adding new consensus mechanisms; reference hierachain/consensus/base_consensus.py and hierachain/consensus/bft/."
icon: material/cog-sync
---

# Add/Customize Consensus

Use this guide to configure PoA or PoF for MainChain and SubChain, or to integrate another consensus mechanism through `BaseConsensus`.

## Configure PoA or PoF

1. Choose PoA or PoF for MainChain. The example uses `HRC_CONSENSUS_TYPE`; `HRC_MAINCHAIN_CONSENSUS` is also supported:

    ```dotenv
    # .env (example)
    HRC_CONSENSUS_TYPE=proof_of_authority   # or proof_of_federation
    HRC_ZK_REQUIRED_MAINCHAIN=false         # if using ZK, set true
    ```

MainChain and SubChain use PoA or PoF in the current runtime flow. BFT has a separate implementation under `hierachain/consensus/bft/`; the API Ledger does not select it, and there is no `HRC_BFT_ENABLED` environment variable. SubChain uses PoA by default; pass `config={"consensus_type": "proof_of_federation"}` when initializing it to use PoF.

2. Start API server and verify basic flow works:

    ```bash
    python -m hierachain
    ```

3. Provision the signing identity, trusted keys and any API key as described in [Quickstart](../getting-started/quickstart.md). The example below assumes authentication is disabled in dev/test. Submit an event, then read blocks to confirm commitment before submitting its proof:

    ```bash
    curl -s -X POST http://localhost:2661/api/ledger/chains/supply_chain/create
    curl -s -X POST http://localhost:2661/api/ledger/chains/supply_chain/events \
      -H 'Content-Type: application/json' \
      -d '{"entity_id":"PROD-001","event_type":"production_complete","details":{"quantity":100}}'
    curl -s http://localhost:2661/api/ledger/chains/supply_chain/blocks
    ```

After the event appears in a persisted block, submit the proof:

```bash
curl -s -X POST http://localhost:2661/api/ledger/chains/supply_chain/submit-proof
```

## Add a consensus implementation

1. Review the standard interface and existing implementations:

    * Base: `hierachain/consensus/base_consensus.py`
    * PoA: `hierachain/consensus/proof_of_authority.py`
    * PoF: `hierachain/consensus/proof_of_federation.py`
    * BFT (separate implementation, not selected by current MainChain/SubChain configuration): `hierachain/consensus/bft/`

2. Create new class extending `BaseConsensus` (example):

    ```python
    from hierachain.consensus.base_consensus import BaseConsensus
    from hierachain.core.block import Block

    class MyConsensus(BaseConsensus):
        def validate_block(self, block: Block, previous_block: Block) -> bool:
            raise NotImplementedError("Implement trusted validation")

        def finalize_block(self, block: Block, authority_id: str | None = None) -> Block:
            raise NotImplementedError("Implement signed finalization")

        def can_create_block(self, authority_id: str | None = None) -> bool:
            raise NotImplementedError("Implement proposer authorization")
    ```

3. Wiring at initialization point (factory/integration point):

    * Update the chain initialization or integration point to construct the new class. `HRC_CONSENSUS_TYPE` currently supports PoA/PoF; a new name also requires configuration validation and selector support.
    * If a factory exists, add the mapping case `my_consensus` → `MyConsensus`.

4. Test the implemented `can_create_block()`, `finalize_block()` and `validate_block()` methods, including invalid signatures and unauthorized proposers. Then verify the API integration: submit an event, wait for its persisted Sub-Chain block, and submit its proof. The base interface has no `propose` or `commit` methods.

The abstract-method stubs above are intentionally incomplete and cannot finalize valid blocks. Merely defining the class does not install it into MainChain, SubChain or the API.

## Related

* Architecture/Consensus: [Consensus & Ordering](../architecture/consensus.md)
* Hierarchical Module: [Hierarchical](../modules/hierarchical.md)
* Config Reference: [Config](../reference/config.md)
* API Ledger: [API Ledger](../reference/api-ledger.md)
