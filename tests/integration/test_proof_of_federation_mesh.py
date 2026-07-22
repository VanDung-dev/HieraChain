"""
Integration Test: Proof of Federation (PoF) Multi-MainChain Alliance Verification.

Demonstrates that:
1. Without PoF (Pure PoA): Independent MainChains (Hospital A, Hospital B, Insurance Z) REJECT block/event proofs from external chains due to lack of central authority trust.
2. With PoF (Federation): Independent MainChains validate cross-organizational events via Federated Consortium consensus without any central RootChain.
"""

import pytest
import time
from nacl.signing import SigningKey
from nacl.encoding import HexEncoder

from hierachain.consensus.proof_of_authority import ProofOfAuthority
from hierachain.consensus.proof_of_federation import ProofOfFederation
from hierachain.core.block import Block, convert_events_to_arrow


def _generate_ed25519_keypair():
    sk = SigningKey.generate()
    pk_hex = sk.verify_key.encode(encoder=HexEncoder).decode("utf-8")
    sk_hex = sk.encode(encoder=HexEncoder).decode("utf-8")
    return sk_hex, pk_hex


def test_phase_1_without_pof_rejection():
    """
    Phase 1: Without PoF (Pure PoA Mode)
    Hospital A creates a block and sends it to Hospital B.
    Hospital B rejects Hospital A's block because Hospital A is not an authority in Hospital B's PoA network.
    """
    print("\n[Phase 1] Testing Cross-MainChain without PoF (Pure PoA)...")
    
    # Hospital A setup
    _, pk_a = _generate_ed25519_keypair()
    poa_hospital_a = ProofOfAuthority("PoA_Hospital_A")
    poa_hospital_a.add_authority("hospital-a-node", {"public_key": pk_a})
    
    # Hospital B setup
    _, pk_b = _generate_ed25519_keypair()
    poa_hospital_b = ProofOfAuthority("PoA_Hospital_B")
    poa_hospital_b.add_authority("hospital-b-node", {"public_key": pk_b})
    
    # Genesis block & Hospital A block
    genesis_block = Block(index=0, events=convert_events_to_arrow([]), previous_hash="")
    
    events_a = [
        {
            "event_id": "med-rec-001",
            "entity_id": "patient-999",
            "event": "medical_record_created",
            "timestamp": time.time(),
            "details": {"diagnosis": "flu", "hospital": "Hospital A"}
        }
    ]
    block_a = Block(index=1, events=convert_events_to_arrow(events_a), previous_hash=genesis_block.hash)
    signed_block_a = poa_hospital_a.finalize_block(block_a, "hospital-a-node")
    
    # Hospital B attempts to validate Hospital A's block using Hospital B's PoA rules
    is_valid_at_b = poa_hospital_b.validate_block(signed_block_a, genesis_block)
    
    # ASSERTION: Hospital B REJECTS Hospital A's block because Hospital A is not in Hospital B's authority list!
    assert is_valid_at_b is False, "Hospital B should REJECT Hospital A's block in pure PoA mode!"
    print("  ✓ SUCCESS: Hospital B correctly REJECTED Hospital A's block under isolated PoA rules.")


def test_phase_2_with_pof_federation_consensus():
    """
    Phase 2: With PoF (Federation Consortium Mode)
    Hospital A, Hospital B, and Insurance Z form a Federation Alliance via PoF.
    Cross-organizational events are validated across all 3 MainChains using Federated Leader & Signature verification.
    """
    print("\n[Phase 2] Testing Cross-MainChain WITH PoF (Federation Consortium)...")
    
    # Generate keys for 3 MainChains
    sk_a, pk_a = _generate_ed25519_keypair()
    sk_b, pk_b = _generate_ed25519_keypair()
    sk_z, pk_z = _generate_ed25519_keypair()
    
    # Consortium PoF Engine instance initialized with matching signing keys
    pof_consortium_a = ProofOfFederation("Healthcare_Federation", signing_key_hex=sk_a)
    pof_consortium_b = ProofOfFederation("Healthcare_Federation", signing_key_hex=sk_b)
    pof_consortium_z = ProofOfFederation("Healthcare_Federation", signing_key_hex=sk_z)
    
    # Configure test environment with 0 block interval timeout
    for pof in (pof_consortium_a, pof_consortium_b, pof_consortium_z):
        pof.config["block_interval"] = 0.0
        pof.add_validator("hospital-a-mainchain", {"public_key": pk_a})
        pof.add_validator("hospital-b-mainchain", {"public_key": pk_b})
        pof.add_validator("insurance-z-mainchain", {"public_key": pk_z})
        
    assert pof_consortium_a.get_validator_count() == 3
    assert pof_consortium_b.get_validator_count() == 3
    assert pof_consortium_z.get_validator_count() == 3
    
    genesis_block = Block(index=0, events=convert_events_to_arrow([]), previous_hash="")
    
    # Scheduled Leader for Block #1
    scheduled_leader = pof_consortium_a.get_current_leader(block_index=1)
    assert scheduled_leader in ["hospital-a-mainchain", "hospital-b-mainchain", "insurance-z-mainchain"]
    print(f"  ✓ Scheduled Federation Leader for Block #1: {scheduled_leader}")
    
    # Scheduled leader creates cross-organizational event proof
    cross_org_events = [
        {
            "event_id": "cross-claim-101",
            "entity_id": "patient-999",
            "event": "insurance_claim_transfer",
            "timestamp": time.time(),
            "details": {
                "origin_hospital": "hospital-a-mainchain",
                "target_insurance": "insurance-z-mainchain",
                "amount_usd": 1500
            }
        }
    ]
    block = Block(index=1, events=convert_events_to_arrow(cross_org_events), previous_hash=genesis_block.hash)
    
    # Map leader ID to its corresponding PoF instance with matching private signing key
    pof_instances = {
        "hospital-a-mainchain": pof_consortium_a,
        "hospital-b-mainchain": pof_consortium_b,
        "insurance-z-mainchain": pof_consortium_z,
    }
    leader_engine = pof_instances[scheduled_leader]
    
    # Leader signs block via PoF
    federation_signed_block = leader_engine.finalize_block(block, authority_id=scheduled_leader)
    
    # Both Hospital B and Insurance Z validate the block using PoF rules!
    valid_at_b = pof_consortium_b.validate_block(federation_signed_block, genesis_block)
    valid_at_z = pof_consortium_z.validate_block(federation_signed_block, genesis_block)
    
    # ASSERTION: Both B and Z accept the block under PoF rules!
    assert valid_at_b is True, "Hospital B should ACCEPT the PoF federation block!"
    assert valid_at_z is True, "Insurance Z should ACCEPT the PoF federation block!"
    
    print("  ✓ SUCCESS: Both Hospital B and Insurance Z ACCEPTED the block via PoF Alliance Consensus!")
