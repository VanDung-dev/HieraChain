---
title: "Proof of Authority (PoA)"
description: "Authority-based consensus protocol: Maximum performance, Node identity, and Round-Robin rotation."
icon: material/account-check-outline
---

# Proof of Authority (`hierachain/consensus/proof_of_authority.py`)

## Overview

**Proof of Authority (PoA)** is an identity-based consensus protocol optimized for private blockchain networks or enterprise internal networks. Instead of solving complex cryptographic problems (like mining), PoA relies on a group of authorized nodes (**Authorities**) to validate and close blocks, achieving extremely fast transaction speeds with minimal latency.

---

## How It Works

The protocol operates based on trust in the identity of participating nodes:
1.  **Node Identity**: Each Authority is assigned an `authority_id` and a unique signing key pair.
2.  **Round-Robin Schedule**: The system uses a sequential algorithm to determine which node has the right to create the next block based on the block index (`BlockIndex % TotalAuthorities`).
3.  **Signature Verification**: Each new block must be signed by the designated Authority. Other nodes verify this signature before accepting the block into the ledger.

---

## Key Features

<div class="grid cards" markdown>

*   :material-lightning-bolt:{ .lg .middle } __Breakthrough Performance__

    ---

    Blocks are created instantly according to the configured cycle (`block_interval`), suitable for real-time response applications.

*   :material-account-multiple-check:{ .lg .middle } __Identity Management__

    ---

    Supports flexible addition/removal of Authorities through the API, allowing network configuration changes without system downtime.

*   :material-shield-sync:{ .lg .middle } __Absolute Integrity__

    ---

    Every block carries the digital signature of a verified organization, completely eliminating risks from anonymous or spoofed nodes.

</div>

---

## Important Configuration Parameters

| Parameter | Description | Default |
| :--- | :--- | :--- |
| `block_interval` | Minimum time between two blocks. | `10.0` seconds |
| `max_authorities` | Maximum number of Authority nodes in the network. | `100` |
| `require_signature` | Mandatory valid signature to accept a block. | `True` |

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
