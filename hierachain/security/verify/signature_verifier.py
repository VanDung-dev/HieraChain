"""
Signature Verification Module

This module provides robust signature verification for Events and Transactions,
supporting both Ed25519 (via PyNaCl) and ECDSA (via cryptography).
"""

import json
from typing import Any

from hierachain.security.security_utils import verify_signature, verify_batch_signatures
from hierachain.security.secure_logging import get_security_logger

logger = get_security_logger()

class SignatureVerifier:
    """
    Verifies signatures for Events and Transactions.
    Supports Ed25519 (default) and ECDSA algorithms.
    """

    def __init__(self):
        pass

    def verify_event_signature(self, event: dict[str, Any], public_key: str) -> bool:
        """
        Verify the signature of an event.
        
        The event dict must contain a 'signature' field.
        The signature is verified against the canonical JSON representation of the event
        WITHOUT the 'signature' and 'data' (if strictly binary) fields, depending on signing spec.
        
        Assumes the signed content is the JSON dump of the event excluding 'signature'.
        
        Args:
            event: Event dictionary.
            public_key: Hex string of the public key.
            
        Returns:
            True if valid, False otherwise.
        """
        if 'signature' not in event or not event['signature']:
            logger.debug("Event has no signature")
            return False

        signature = event['signature']
        
        # Reconstruct the message that was signed
        message_bytes = self._get_signable_event_content(event)
        
        return self._verify_any(public_key, message_bytes, signature)

    def verify_transaction_signature(self, tx: dict[str, Any]) -> bool:
        """
        Verify the signature of a transaction.
        
        Args:
            tx: Transaction dictionary.
            
        Returns:
            True if valid, False otherwise.
        """
        if 'signature' not in tx or not tx['signature']:
            logger.debug("Transaction has no signature")
            return False

        signature = tx['signature']
        
        public_key = tx.get('details', {}).get('sender_public_key')
        if not public_key:
            # Fallback: maybe the entity_id IS the public key? (unlikely for short IDs)
            logger.warning("Cannot verify transaction: Public key not found in details")
            return False

        message_bytes = self._get_signable_transaction_content(tx)
        return self._verify_any(public_key, message_bytes, signature)

    def verify_transaction_with_key(self, tx: dict[str, Any], public_key: str) -> bool:
        """
        Verify transaction with an explicitly provided public key.
        """
        if 'signature' not in tx or not tx['signature']:
            return False
        
        signature = tx['signature']
        message_bytes = self._get_signable_transaction_content(tx)
        return self._verify_any(public_key, message_bytes, signature)

    def batch_verify(self, items: list[dict[str, Any]]) -> list[bool]:
        """
        Batch verify multiple items (events or transactions).
        Each item must have 'item' (the dict) and 'public_key'.
        
        Args:
            items: List of dicts -> [{'item': event_dict, 'public_key': hex_key, 'type': 'event'|'tx'}]
            
        Returns:
            List of booleans.
        """
        batch_input = []
        for entry in items:
            item_type = entry.get('type', 'event')
            item_data = entry.get('item')
            pk = entry.get('public_key')
            
            if not item_data or not pk or 'signature' not in item_data:
                # Add dummy invalid entry to preserve index mapping
                batch_input.append({}) 
                continue

            if item_type == 'tx':
                msg = self._get_signable_transaction_content(item_data)
            else:
                msg = self._get_signable_event_content(item_data)
                
            batch_input.append({
                'public_key': pk,
                'message': msg,
                'signature': item_data['signature']
            })
            
        return verify_batch_signatures(batch_input)

    def _verify_any(self, public_key: str, message: bytes, signature: str) -> bool:
        """
        Try to verify with supported algorithms.
        Attempts Ed25519 first (default standard).
        """
        # 1. Try Ed25519 (PyNaCl) - Fast and standard for HieraChain
        if verify_signature(public_key, message, signature):
            return True
            
        # 2. Try ECDSA (secp256k1/prime256v1) if Ed25519 failed
        # This allows hybrid networks or external wallet integration
        if self._verify_ecdsa(public_key, message, signature):
            return True
            
        return False

    @staticmethod
    def _verify_ecdsa(public_key_hex: str, message: bytes, signature_hex: str) -> bool:
        """
        Verify standard ECDSA signature (e.g., from generic crypto libs).
        Supports secp256k1 and other common curves if cryptography library is present.
        """
        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import ec
            from cryptography.exceptions import InvalidSignature
        except ImportError:
            logger.warning("cryptography library not available for ECDSA verification")
            return False

        try:
            # Decode hex strings
            pub_key_bytes = bytes.fromhex(public_key_hex)
            sig_bytes = bytes.fromhex(signature_hex)

            # Attempt to load public key (try different formats)
            try:
                # Try SubjectPublicKeyInfo (PEM/DER)
                public_key = serialization.load_der_public_key(pub_key_bytes)
            except (ValueError, TypeError):
                # Log and return False if format is unknown or unsupported
                logger.debug("Unsupported or invalid ECDSA public key format")
                return False

            # Verify signature if it's an Elliptic Curve key
            if isinstance(public_key, ec.EllipticCurvePublicKey):
                public_key.verify(sig_bytes, message, ec.ECDSA(hashes.SHA256()))
                return True
            
            return False

        except InvalidSignature:
            return False
        except (ValueError, TypeError) as e:
            logger.debug(f"ECDSA verification format error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during ECDSA verification: {e}", error=str(e))
            return False

    @staticmethod
    def _get_signable_event_content(event: dict[str, Any]) -> bytes:
        """
        Get canonical bytes for event signing.
        Excludes 'signature'.
        """
        event_copy = event.copy()
        if 'signature' in event_copy:
            del event_copy['signature']
        
        # Use simple JSON dump with sort_keys for determinism
        # Ensure separators are compact to match most signing implementations
        return json.dumps(event_copy, sort_keys=True, separators=(',', ':')).encode('utf-8')

    @staticmethod
    def _get_signable_transaction_content(tx: dict[str, Any]) -> bytes:
        """
        Get canonical bytes for transaction signing.
        Excludes 'signature'.
        """
        tx_copy = tx.copy()
        if 'signature' in tx_copy:
            del tx_copy['signature']
        
        return json.dumps(tx_copy, sort_keys=True, separators=(',', ':')).encode('utf-8')
