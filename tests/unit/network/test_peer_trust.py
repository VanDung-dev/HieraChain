"""
Tests for PeerTrustManager production hardening.
"""
import pytest
from unittest.mock import MagicMock
from hierachain.network import PeerTrustManager
from hierachain.security import IdentityManager

class TestPeerTrustManager:
    @pytest.fixture
    def mock_identity_manager(self):
        return MagicMock(spec=IdentityManager)

    @pytest.fixture
    def trust_manager(self, mock_identity_manager):
        return PeerTrustManager(identity_manager=mock_identity_manager)

    def test_default_policy(self, trust_manager):
        """Test default 'open' policy."""
        assert trust_manager.trust_policy == "open"
        # In open policy, unknown peers are trusted (unless blocked)
        assert trust_manager.is_trusted("unknown_peer") is True

    def test_strict_policy(self, trust_manager):
        """Test 'strict' policy."""
        trust_manager.set_policy("strict")
        
        # Unknown peer should be rejected in strict mode
        assert trust_manager.is_trusted("unknown_peer") is False
        
        # Allowlisted peer should be accepted
        trust_manager.trust_peer("friend")
        assert trust_manager.is_trusted("friend") is True

    def test_blocklist_override(self, trust_manager):
        """Test that blocklist overrides allowlist and policy."""
        trust_manager.set_policy("open")
        trust_manager.trust_peer("bad_actor")
        
        # Initially trusted
        assert trust_manager.is_trusted("bad_actor") is True
        
        # Block
        trust_manager.block_peer("bad_actor")
        
        # Should now be untrusted
        assert trust_manager.is_trusted("bad_actor") is False

    def test_trust_peer_removes_from_blocklist(self, trust_manager):
        """Test that trusting a peer removes them from blocklist."""
        trust_manager.block_peer("redeemed_peer")
        assert "redeemed_peer" in trust_manager.blocklist
        
        trust_manager.trust_peer("redeemed_peer")
        assert "redeemed_peer" not in trust_manager.blocklist
        assert "redeemed_peer" in trust_manager.allowlist

    def test_invalid_policy_error(self, trust_manager):
        """Test setting invalid policy raises error."""
        with pytest.raises(ValueError):
            trust_manager.set_policy("invalid_mode")
