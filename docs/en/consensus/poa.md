---
title: "Proof of Authority (PoA)"
description: "Authority membership, block signatures, optional timing checks and scheduling helpers."
icon: material/account-check-outline
---

# Proof of Authority (`hierachain/consensus/proof_of_authority.py`)

## Overview

Proof of Authority (PoA) is an identity-based consensus protocol for intra-organization enterprise networks, where one MainChain manages internal domain Sub-Chains. In HieraChain's two-tiered consensus architecture, `SubChain` instances default to PoA for internal events without requiring consensus between organizations.

For cross-organizational inter-MainChain consensus between independent enterprises, see [Proof of Federation (PoF)](./pof.md).

## How it works

The protocol operates based on trust in the identity of participating nodes:
1. Register an authority ID and its approved signing public key with `add_authority()`.
2. `can_create_block(authority_id)` checks membership. It does not require that the authority be next in a rotation.
3. `validate_block()` checks the block structure, timing, events and signature from a registered authority. `get_next_authority()` supplies a round-robin scheduling helper, but these creation and validation methods do not enforce its result.

## Features

<div class="grid cards" markdown>

*   :material-lightning-bolt:{ .lg .middle } __Timing Validation__

    ---

    By default, PoA adds no minimum spacing delay. Consecutive block timestamps must still be nondecreasing. A positive `block_interval` requires timestamps to be at least half that value apart.

*   :material-account-multiple-check:{ .lg .middle } __Identity Management__

    ---

    The `ProofOfAuthority` class provides `add_authority()` and `remove_authority()` methods.

*   :material-shield-sync:{ .lg .middle } __Block Signatures__

    ---

    A block signature must verify against a registered authority key. The validation path does not require the next authority returned by the scheduling helper.

</div>

## Configuration parameters

| Parameter | Description | Default |
| :--- | :--- | :--- |
| `block_interval` | Optional spacing setting; `0` adds no delay, while a positive value retains a validator threshold of half this value. | `0.0` seconds |
| `max_authorities` | Maximum number of Authority nodes in the network. | `100` |
| `require_authority_signature` | Mandatory valid signature to accept a block. | `True` |

MainChain and SubChain instances using PoA read this value from `HRC_BLOCK_INTERVAL`, which defaults to `0.0`. Direct `ProofOfAuthority()` construction also defaults to `0.0`. Negative or nonfinite values are rejected when constructing PoA.

The SubChain orderer still batches events according to `block_size` and `batch_timeout` (defaults: 50 events and 1.0 second). Removing the PoA spacing delay does not remove batching time, signature verification, journal synchronization, or storage work. PoF keeps its separate timing configuration.

For an existing deployment, an explicit `HRC_BLOCK_INTERVAL=10` retains the previous 5-second minimum spacing. Use `HRC_BLOCK_INTERVAL=0` to remove that spacing, and configure producers and validators consistently: a validator retaining the previous spacing rejects faster blocks. Existing blocks that satisfied the previous spacing remain valid with the new default.

## Deployment example

```python
from hierachain.consensus import ProofOfAuthority
from hierachain.security.security_utils import KeyPair

# Generate temporary keys for this library example.
# Deployments provision stable keys and register approved public keys.
hq_key = KeyPair.generate()
branch_key = KeyPair.generate()
poa = ProofOfAuthority()
poa.add_authority("node_hq", metadata={"public_key": hq_key.public_key})
poa.add_authority("node_branch_1", metadata={"public_key": branch_key.public_key})

assert poa.can_create_block("node_hq")
assert poa.can_create_block("node_branch_1")
```

## Advantages and limitations

* Authority membership and signature checks avoid work-based consensus. Throughput depends on batching, journal synchronization and storage.
*   Limitations: Lower decentralization compared to BFT, only suitable for networks with a certain level of trust between members.

## Related

*   [Base Consensus Interface](./base_consensus.md)
*   [Proof of Federation (PoF)](./pof.md)
*   [Hierarchical Architecture](../modules/hierarchical.md)
