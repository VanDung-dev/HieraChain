
import pytest
import json
from hierachain.security.verify.signature_verifier import SignatureVerifier
from hierachain.security.security_utils import KeyPair

class TestSignatureVerifier:
    
    @pytest.fixture
    def verifier(self):
        return SignatureVerifier()

    @pytest.fixture
    def keypair(self):
        return KeyPair.generate()

    def test_verify_event_signature_ed25519(self, verifier, keypair):
        # 1. Create a sample event
        event = {
            "entity_id": "test_user",
            "event": "CREATE",
            "timestamp": 123456789.0,
            "details": {"foo": "bar"}
        }
        
        # 2. Sign it manually using the same canonicalization rule
        # Rule: json dump with sorted keys, separators=(',', ':')
        message = json.dumps(event, sort_keys=True, separators=(',', ':')).encode('utf-8')
        signature = keypair.sign(message)
        
        # 3. Add signature to event
        signed_event = event.copy()
        signed_event['signature'] = signature
        
        # 4. Verify
        assert verifier.verify_event_signature(signed_event, keypair.public_key) is True

    def test_verify_event_signature_invalid(self, verifier, keypair):
        event = {
            "entity_id": "test_user",
            "event": "CREATE",
            "timestamp": 123456789.0
        }
        message = json.dumps(event, sort_keys=True, separators=(',', ':')).encode('utf-8')
        signature = keypair.sign(message)
        
        signed_event = event.copy()
        signed_event['signature'] = signature
        
        # Tamper with data
        signed_event['timestamp'] += 1.0
        
        assert verifier.verify_event_signature(signed_event, keypair.public_key) is False

    def test_verify_transaction_signature(self, verifier, keypair):
        tx = {
            "tx_id": "tx_123",
            "entity_id": "test_user",
            "amount": 100,
            "details": {
                "sender_public_key": keypair.public_key
            }
        }
        
        message = json.dumps(tx, sort_keys=True, separators=(',', ':')).encode('utf-8')
        signature = keypair.sign(message)
        
        signed_tx = tx.copy()
        signed_tx['signature'] = signature
        
        # Verify using extracted key
        assert verifier.verify_transaction_signature(signed_tx) is True
        
        # Verify using explicit key
        assert verifier.verify_transaction_with_key(signed_tx, keypair.public_key) is True

    def test_batch_verify(self, verifier, keypair):
        # Create multiple events
        batch_input = []
        
        for i in range(5):
            event = {"index": i, "data": "test"}
            msg = json.dumps(event, sort_keys=True, separators=(',', ':')).encode('utf-8')
            sig = keypair.sign(msg)
            signed_event = event.copy()
            signed_event['signature'] = sig
            
            # Make one invalid
            if i == 2:
                signed_event['data'] = "tampered"
            
            batch_input.append({
                "item": signed_event,
                "public_key": keypair.public_key,
                "type": "event"
            })
            
        results = verifier.batch_verify(batch_input)
        
        assert len(results) == 5
        assert results[0] is True
        assert results[1] is True
        assert results[2] is False # The tampered one
        assert results[3] is True
        assert results[4] is True

    def test_missing_signature(self, verifier, keypair):
        event = {"foo": "bar"}
        assert verifier.verify_event_signature(event, keypair.public_key) is False

