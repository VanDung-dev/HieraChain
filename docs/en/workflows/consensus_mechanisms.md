---
title: "Consensus mechanisms"
description: "Comparison and technical specifications of PoA and PoF consensus mechanisms in HieraChain."
icon: material/sync
---

# Consensus mechanisms

## Runtime selection

MainChain selects `HRC_MAINCHAIN_CONSENSUS`, falling back to `HRC_CONSENSUS_TYPE`; the default is `proof_of_authority`. Sub-Chains default to PoA and accept a Python `config` with `consensus_type="proof_of_federation"`. Use the documented PoA/PoF selectors.

## Implementation comparison

| Aspect | PoA | PoF |
|--------|-----|-----|
| Hierarchical runtime | Default MainChain/Sub-Chain | Explicit federation selection |
| Finalization signer | Registered authority | Registered validator; validation enforces scheduled leader when rotation is enabled |
| Default interval | 0.0 seconds | 5.0 seconds |
| Timestamp spacing check | At least half of a positive interval | At least 80% of interval (4 seconds by default) |
| Membership | At least one authority | `min_validators=3` for block creation |
| ZK | Shared optional verification | Shared optional verification |

## Ordering and durability

`SubChain.add_event()` journals and queues the event. Ordering batches events, finalizes consensus, signs the block header and saves the block before publishing it to the commit queue. The Sub-Chain consumer validates and applies the committed block without rewriting it. A submission acknowledgement is earlier than finality. Default Sub-Chain ordering uses 50 events and a 1-second batch timeout; this wait is independent of PoA block spacing.

## PoF boundary

`get_current_leader(index)` uses the sorted validator list and `index % count`. `validate_block()` checks structure, timestamp spacing, leader identity, the leader's signature over the reconstructed pre-finalization payload, and the shared optional ZK check. Despite its name, `_verify_block_quorum()` checks a single leader signature. `verify_quorum_signatures()` separately verifies distinct validator signatures with a default threshold of `floor(2n/3)+1`; ordinary block finalization/validation does not collect or enforce that quorum. No automatic leader failover is implemented by this class.

Register real validator public keys. If a caller omits `public_key` in `add_validator()`, the class generates a key unrelated to that remote validator; this is unsuitable for network provisioning.

## ZK boundary

`HRC_ENABLE_ZK_PROOFS=false` disables the shared ZK check. If enabled, missing-proof handling also depends on `HRC_ZK_REQUIRED_MAINCHAIN`. PoF does not independently require ZK by default. Mock proofs are forgeable development fixtures; `production` proving/verifying is unimplemented. Signed blocks and Merkle anchors remain separate integrity mechanisms.

## Configuration

```dotenv
HRC_MAINCHAIN_CONSENSUS=proof_of_authority
HRC_BLOCK_INTERVAL=0.0
HRC_ENABLE_ZK_PROOFS=false
HRC_ZK_REQUIRED_MAINCHAIN=false
```

PoF's `block_interval` is a separate consensus configuration value; `HRC_BLOCK_INTERVAL` controls PoA. Current chain constructors do not apply `CONSENSUS_FEDERATION_CONFIG`.

## Related

* [PoA](../consensus/poa.md) · [PoF](../consensus/pof.md)
* [Event submission](event-submission.md) · [Proof anchoring](proof-anchoring.md)
