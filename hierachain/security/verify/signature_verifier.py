"""
Signature Verification Module

This module provides robust signature verification for Events and Transactions,
supporting both Ed25519 (via PyNaCl) and ECDSA (via cryptography).
"""

import json
import unicodedata
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
        WITHOUT the 'signature' and 'data' (if strictly binary) fields, depending on
        signing spec.
        
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
            items: List of dicts -> [
                {'item': event_dict, 'public_key': hex_key, 'type': 'event'|'tx'}
            ]
            
        Returns:
            List of booleans.
        """
        batch_input = [self._build_batch_entry(entry) for entry in items]
        return verify_batch_signatures(batch_input)

    def _build_batch_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        """
        Build a single batch entry for verification, preserving index mapping.

        Args:
            entry: Dict with 'item', 'public_key' and optional 'type' ('event'|'tx')

        Returns:
            Dict suitable for verify_batch_signatures, or empty dict if invalid.
        """
        item_type = entry.get('type', 'event')
        item_data = entry.get('item')
        pk = entry.get('public_key')

        if not isinstance(item_data, dict) or not isinstance(pk, str) or 'signature' not in item_data:
            return {}

        if item_type == 'tx':
            msg = self._get_signable_transaction_content(item_data)
        else:
            msg = self._get_signable_event_content(item_data)

        return {
            'public_key': pk,
            'message': msg,
            'signature': item_data['signature']
        }

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
            logger.debug("ECDSA verification format error: %s", e)
            return False
        except Exception as e:
            logger.error(
                "Unexpected error during ECDSA verification: %s", e, error=str(e)
            )
            return False


    @staticmethod
    def _canonicalize_value(v: Any) -> Any:
        """Recursively canonicalize values for consistent hashing."""
        if isinstance(v, dict):
            return {k: SignatureVerifier._canonicalize_value(v[k]) for k in sorted(v.keys())}
        elif isinstance(v, list):
            return [SignatureVerifier._canonicalize_value(item) for item in v]
        elif isinstance(v, str):
            # Normalize Unicode to NFC form
            return unicodedata.normalize('NFC', v)
        elif isinstance(v, float):
            # Format floats consistently to avoid precision issues
            return f"{v:.16f}".rstrip('0').rstrip('.') if '.' in f"{v:.16f}" else f"{v:.16f}"
        else:
            return v

    @staticmethod
    def get_canonical_bytes(data: dict[str, Any]) -> bytes:
        """
        Get cryptographically canonical bytes for signing/hashing.
        Fixes JSON canonicalization vulnerabilities.
        """
        canonical = SignatureVerifier._canonicalize_value(data)
        return json.dumps(
            canonical,
            sort_keys=True,
            separators=(',', ':'),
            ensure_ascii=False,
            allow_nan=False
        ).encode('utf-8')

    @staticmethod
    def _get_signable_event_content(event: dict[str, Any]) -> bytes:
        """
        Get canonical bytes for event signing.
        Excludes 'signature'.
        """
        event_copy = event.copy()
        if 'signature' in event_copy:
            del event_copy['signature']

        return SignatureVerifier.get_canonical_bytes(event_copy)

    @staticmethod
    def _get_signable_transaction_content(tx: dict[str, Any]) -> bytes:
        """
        Get canonical bytes for transaction signing.
        Excludes 'signature'.
        """
        tx_copy = tx.copy()
        if 'signature' in tx_copy:
            del tx_copy['signature']

        return SignatureVerifier.get_canonical_bytes(tx_copy)
