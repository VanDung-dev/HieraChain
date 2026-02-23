
import pytest
from hierachain.core.consensus.proof_of_federation import ProofOfFederation
from hierachain.security.security_utils import generate_key_pair_hex, KeyPair


def _sign_message(private_key_hex, message):
    kp = KeyPair.from_private_key(private_key_hex)
    return kp.sign(message)


class TestQuorumVerification:
    @pytest.fixture
    def consensus(self):
        return ProofOfFederation()

    @pytest.fixture
    def validators(self):
        # Generate 3 validators
        vals = []
        for i in range(3):
            pub, priv = generate_key_pair_hex()
            vals.append({
                "id": f"val_{i}",
                "public_key": pub,
                "private_key": priv
            })
        return vals

    def test_verify_quorum_signatures_success(self, consensus, validators):
        """Test successful quorum verification."""
        # Add validators to consensus
        for v in validators:
            consensus.add_validator(v["id"], {"public_key": v["public_key"]})
            
        message = b"consensus_proposal"
        signatures = []
        
        # Sign with 2 validators
        for i in range(2): 
            sig = _sign_message(validators[i]["private_key"], message)
            signatures.append({
                "validator_id": validators[i]["id"],
                "signature": sig
            })
            
        # Should succeed with required_count=2
        assert consensus.verify_quorum_signatures(message, signatures, required_count=2) is True

    def test_verify_quorum_signatures_failure_count(self, consensus, validators):
        """Test failure due to insufficient signatures."""
        for v in validators:
            consensus.add_validator(v["id"], {"public_key": v["public_key"]})
            
        message = b"proposal"
        vals_to_sign = [validators[0]] # Only 1 signature
        
        signatures = []
        for v in vals_to_sign:
            sig = _sign_message(v["private_key"], message)
            signatures.append({
                "validator_id": v["id"],
                "signature": sig
            })
            
        # Default quorum for 3 is 3 (by my calc earlier). 1 is insufficient.
        assert consensus.verify_quorum_signatures(message, signatures) is False

    def test_verify_quorum_signatures_invalid_sig(self, consensus, validators):
        """Test failure due to invalid signature."""
        for v in validators:
            consensus.add_validator(v["id"], {"public_key": v["public_key"]})
            
        message = b"proposal"
        invalid_message = b"tampered_proposal"
        
        signatures = []
        # Proper signer, but signed DIFFERENT message
        sig = _sign_message(validators[0]["private_key"], invalid_message)
        signatures.append({
            "validator_id": validators[0]["id"],
            "signature": sig
        })
        
        assert consensus.verify_quorum_signatures(message, signatures, required_count=1) is False

    def test_verify_quorum_unknown_validator(self, consensus, validators):
        """Test ignoring signatures from unknown validators."""
        consensus.add_validator(validators[0]["id"], {"public_key": validators[0]["public_key"]})
        
        message = b"data"
        
        # Sign with unknown validator (validators[1] is not added)
        sig = _sign_message(validators[1]["private_key"], message)
        signatures = [{
            "validator_id": validators[1]["id"],
            "signature": sig
        }]
        
        assert consensus.verify_quorum_signatures(message, signatures, required_count=1) is False

    def test_verify_quorum_double_voting(self, consensus, validators):
        """Test that duplicate signatures from same validator don't count twice."""
        consensus.add_validator(validators[0]["id"], {"public_key": validators[0]["public_key"]})
        consensus.add_validator(validators[1]["id"], {"public_key": validators[1]["public_key"]})
        
        message = b"vote"
        sig = _sign_message(validators[0]["private_key"], message)
        
        # Submit same valid signature twice
        signatures = [
            {"validator_id": validators[0]["id"], "signature": sig},
            {"validator_id": validators[0]["id"], "signature": sig}
        ]
        
        # If we require 2 signatures, this should fail because it's only 1 unique validator
        assert consensus.verify_quorum_signatures(message, signatures, required_count=2) is False
