---
title: "Base Consensus Interface"
description: "Abstract PoA/PoF interface, event content checks and shared optional ZK verification."
icon: material/puzzle-outline
---

# Base Consensus (`hierachain/consensus/base_consensus.py`)

## Scope

`BaseConsensus` defines the interface implemented by PoA and PoF. `BFTConsensus` is a separate class and does not inherit this interface. The base class stores `name` and `config`; concrete implementations supply block validation and finalization.

## Abstract methods

| Method | Contract |
|:-------|:---------|
| `validate_block(block, previous_block)` | Return whether a block satisfies the concrete protocol's rules |
| `finalize_block(block)` | Return the block after protocol-specific finalization |
| `can_create_block(authority_id=None)` | Return whether block creation is allowed |

PoA and PoF extend `finalize_block()` with an optional `authority_id`. The orderer's configured finalizer connects consensus to block creation; the ordering block manager signs and persists the finalized header separately.

`get_validator_count()` is a concrete helper that returns zero in the base class and is overridden by PoA/PoF. There is no `get_consensus_info()` method in this interface.

## Event content validation

`validate_event_for_consensus()` accepts a dictionary with `event` and `timestamp`. It checks the event name and selected content values against `FORBIDDEN_TERMS`: `transaction`, `mining`, `coin`, `token`, `wallet` and `fee`. Matching is case-insensitive and uses word boundaries.

`EXCLUDED_CONTENT_FIELDS` skips `authority_signature`, `signature`, `hash`, `proof_hash`, `zk_proof`, `merkle_root`, `previous_state`, `current_state`, `details`, `event` and `timestamp` in the generic field pass. The event name and details receive separate checks. Dictionary details use the same exclusion set; string details are checked directly. This is not recursive schema or permission validation. Arrow Table and RecordBatch input returns `True` without these content checks.

A failed check returns `False`. Callers must use that result; calling this helper does not itself reject or remove a queued event.

## Shared ZK helper

The module-level `_verify_block_zk_proof()` is called by PoA and PoF block validation. `HRC_ENABLE_ZK_PROOFS` enables it, while missing-proof handling depends on `HRC_ZK_REQUIRED_MAINCHAIN`. Development mocks check a public-input commitment; production proving/verifying is unimplemented. Hash and signature checks belong to the concrete protocols and block verifier.

## Related

* [PoA](./poa.md)
* [PoF](./pof.md)
* [Ordering Service](./ordering.md)
