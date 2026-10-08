---
title: "Add/Customize Consensus"
description: "Guide to configuring PoA/PoF or adding new consensus mechanisms; reference core/consensus/* and hierarchical/consensus/bft_consensus.py."
icon: material/cog-sync
---

# Add/Customize Consensus

Use this guide to configure PoA or PoF for MainChain and SubChain, or to integrate another consensus mechanism through `BaseConsensus`.

## Configuration Only (No Coding Required)

1. Choose PoA or PoF for MainChain. The example uses `HRC_CONSENSUS_TYPE`; `HRC_MAINCHAIN_CONSENSUS` is also supported:

    ```dotenv
    # .env (example)
    HRC_CONSENSUS_TYPE=proof_of_authority   # or proof_of_federation
    HRC_ZK_REQUIRED_MAINCHAIN=false         # if using ZK, set true
    ```

MainChain and SubChain use PoA or PoF in the current runtime flow. BFT has a separate implementation under `hierachain/consensus/bft/`; the API Ledger does not select it, and there is no `HRC_BFT_ENABLED` environment variable. SubChain uses PoA by default; pass `consensus_type="proof_of_federation"` when initializing it to use PoF.

2. Start API server and verify basic flow works:

    ```bash
    python -m hierachain.api.server
    ```

3. Send a test request through API Ledger:

    ```bash
    curl -s -X POST http://localhost:2661/api/ledger/chains/supply_chain/create
    curl -s -X POST http://localhost:2661/api/ledger/chains/supply_chain/events \
      -H 'Content-Type: application/json' \
      -d '{"entity_id":"PROD-001","event_type":"production_complete","details":{"quantity":100}}'
    curl -s -X POST http://localhost:2661/api/ledger/chains/supply_chain/submit-proof
    ```

## Adding New Consensus Mechanism (Coding Required)

1. Review the standard interface and existing implementations:

    * Base: `hierachain/consensus/base_consensus.py`
    * PoA: `hierachain/consensus/proof_of_authority.py`
    * PoF: `hierachain/consensus/proof_of_federation.py`
    * BFT (separate implementation, not selected by current MainChain/SubChain configuration): `hierachain/consensus/bft/`

2. Create new class extending `BaseConsensus` (example):

    ```python
    class MyConsensus(BaseConsensus):
      def validate_block(self, block, previous_block):
        # validate signature/merkle/consistency
        ...
        return True
    
      def finalize_block(self, block):
        # close block/apply signature/consensus metadata
        ...
        return block
    
      def can_create_block(self, authority_id=None):
        # check block creation permission
        ...
        return True
    ```

3. Wiring at initialization point (factory/integration point):

    * At chain initialization (Sub-Chain/DomainChain) or Ordering service, reference the new mechanism when `HRC_CONSENSUS_TYPE=my_consensus`.
    * If a factory exists, add the mapping case `my_consensus` → `MyConsensus`.

4. Test with API Ledger as in part A (add event → finalize → submit proof). Monitor logs to confirm the new `propose/validate/commit` methods are called.

## Related

* Architecture/Consensus: [Consensus & Ordering](../architecture/consensus.md)
* Hierarchical Module: [Hierarchical](../modules/hierarchical.md)
* Config Reference: [Config](../reference/config.md)
* API Ledger: [API Ledger](../reference/api-ledger.md)
