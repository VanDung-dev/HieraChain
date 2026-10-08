---
title: "Proof of Authority (PoA)"
description: "Authority-based consensus protocol with node identities, block signatures, and round-robin rotation."
icon: material/account-check-outline
---

# Proof of Authority (`hierachain/consensus/proof_of_authority.py`)

## Overview

**Proof of Authority (PoA)** is an identity-based consensus protocol for **intra-organization enterprise networks**, where one MainChain manages internal domain Sub-Chains. In HieraChain's two-tiered consensus architecture, `SubChain` instances default to PoA for internal events without requiring consensus between organizations.

For cross-organizational inter-MainChain consensus between independent enterprises, see [Proof of Federation (PoF)](./pof.md).

---

## How It Works

The protocol operates based on trust in the identity of participating nodes:
1.  **Node Identity**: Each Authority is assigned an `authority_id` and a unique signing key pair.
2.  **Round-Robin Schedule**: The system uses a sequential algorithm to determine which node has the right to create the next block based on the block index (`BlockIndex % TotalAuthorities`).
3.  **Signature Verification**: Each new block must be signed by the designated Authority. Other nodes verify this signature before accepting the block into the ledger.

---

## Key Features

<div class="grid cards" markdown>

*   :material-lightning-bolt:{ .lg .middle } __Timing Validation__

    ---

    By default, PoA adds no minimum spacing delay. Consecutive block timestamps must still be nondecreasing. A positive `block_interval` requires timestamps to be at least half that value apart.

*   :material-account-multiple-check:{ .lg .middle } __Identity Management__

    ---

    The `ProofOfAuthority` class provides `add_authority()` and `remove_authority()` methods.

*   :material-shield-sync:{ .lg .middle } __Block Signatures__

    ---

    Each block is signed by its designated Authority. Other nodes verify the signature before accepting the block.

</div>

---

## Important Configuration Parameters

| Parameter | Description | Default |
| :--- | :--- | :--- |
| `block_interval` | Optional spacing setting; `0` adds no delay, while a positive value retains a validator threshold of half this value. | `0.0` seconds |
| `max_authorities` | Maximum number of Authority nodes in the network. | `100` |
| `require_authority_signature` | Mandatory valid signature to accept a block. | `True` |

MainChain and SubChain instances using PoA read this value from `HRC_BLOCK_INTERVAL`, which defaults to `0.0`. Direct `ProofOfAuthority()` construction also defaults to `0.0`. Negative or nonfinite values are rejected when constructing PoA.

The SubChain orderer still batches events according to `block_size` and `batch_timeout` (defaults: 50 events and 1.0 second). Removing the PoA spacing delay does not remove batching time, signature verification, journal synchronization, or storage work. PoF keeps its separate timing configuration.

For an existing deployment, an explicit `HRC_BLOCK_INTERVAL=10` retains the previous 5-second minimum spacing. Use `HRC_BLOCK_INTERVAL=0` to remove that spacing, and configure producers and validators consistently: a validator retaining the previous spacing rejects faster blocks. Existing blocks that satisfied the previous spacing remain valid with the new default.

---

## Deployment Example

```python
from hierachain.consensus import ProofOfAuthority

# Initialize PoA protocol
poa = ProofOfAuthority()

# Authorize nodes to participate in consensus
poa.add_authority("node_hq", metadata={"org": "Headquarters", "pubkey": "..."})
poa.add_authority("node_branch_1", metadata={"org": "Branch 01", "pubkey": "..."})

# Check block creation permission for current node
if poa.can_create_block("node_hq"):
    # Proceed to close block...
    pass
```

---

## Advantages and Limitations

*   **Advantages**: Resource-efficient (no powerful CPU needed for mining), high throughput, transparent governance.
*   **Limitations**: Lower decentralization compared to BFT, only suitable for networks with a certain level of trust between members.

---

## Related

*   [Base Consensus Interface](./base_consensus.md)
*   [Proof of Federation (PoF)](./pof.md)
*   [Hierarchical Architecture](../modules/hierarchical.md)
