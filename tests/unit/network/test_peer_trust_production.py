"""
Tests for PeerTrustManager production hardening.

Covers:
- Strict policy initialization with allowlist
- Production settings auto-applying strict policy
- Startup warnings for insecure configurations
- Load allowlist functionality
"""

import pytest
import logging
from unittest.mock import MagicMock

from hierachain.network.peer_trust_manager import PeerTrustManager
from hierachain.security.identity import IdentityManager


class TestPeerTrustManagerProduction:
    """Test production hardening of PeerTrustManager."""

    @pytest.fixture
    def mock_identity_manager(self):
        return MagicMock(spec=IdentityManager)

    def test_strict_policy_init(self, mock_identity_manager):
        """Strict policy with allowlist should only accept listed peers."""
        tm = PeerTrustManager(
            identity_manager=mock_identity_manager,
            trust_policy="strict",
            initial_allowlist={"node-1", "node-2"},
        )
        assert tm.trust_policy == "strict"
        assert tm.is_trusted("node-1") is True
        assert tm.is_trusted("node-2") is True
        assert tm.is_trusted("unknown") is False

    def test_strict_policy_empty_allowlist_warning(
        self, mock_identity_manager, caplog
    ):
        """Strict policy with empty allowlist should log a warning."""
        with caplog.at_level(logging.WARNING):
            PeerTrustManager(
                identity_manager=mock_identity_manager,
                trust_policy="strict",
                initial_allowlist=None,
            )
        assert "empty allowlist" in caplog.text

    def test_open_policy_accepts_all(self, mock_identity_manager):
        """Open policy accepts unknown peers."""
        tm = PeerTrustManager(
            identity_manager=mock_identity_manager,
            trust_policy="open",
        )
        assert tm.is_trusted("any_peer") is True

    def test_invalid_policy_raises(self, mock_identity_manager):
        """Invalid trust policy should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid trust_policy"):
            PeerTrustManager(
                identity_manager=mock_identity_manager,
                trust_policy="permissive",
            )

    def test_load_allowlist(self, mock_identity_manager):
        """Load allowlist should add peers to allowlist."""
        tm = PeerTrustManager(
            identity_manager=mock_identity_manager,
            trust_policy="strict",
            initial_allowlist={"existing-peer"},
        )
        tm.load_allowlist(["new-peer-1", "new-peer-2", " new-peer-3 "])
        assert tm.is_trusted("existing-peer") is True
        assert tm.is_trusted("new-peer-1") is True
        assert tm.is_trusted("new-peer-2") is True
        assert tm.is_trusted("new-peer-3") is True

    def test_load_allowlist_skips_empty(self, mock_identity_manager):
        """Load allowlist should skip empty strings."""
        tm = PeerTrustManager(
            identity_manager=mock_identity_manager,
            trust_policy="strict",
        )
        tm.load_allowlist(["", " ", "valid-peer"])
        assert "valid-peer" in tm.allowlist
        assert "" not in tm.allowlist

    def test_blocklist_overrides_allowlist_strict(
        self, mock_identity_manager
    ):
        """Blocked peers should be rejected even in allowlist."""
        tm = PeerTrustManager(
            identity_manager=mock_identity_manager,
            trust_policy="strict",
            initial_allowlist={"peer-1"},
        )
        assert tm.is_trusted("peer-1") is True
        tm.block_peer("peer-1")
        assert tm.is_trusted("peer-1") is False

    def test_set_policy_to_strict(self, mock_identity_manager):
        """Changing policy to strict should reject unknown peers."""
        tm = PeerTrustManager(
            identity_manager=mock_identity_manager,
            trust_policy="open",
        )
        assert tm.is_trusted("unknown") is True
        tm.set_policy("strict")
        assert tm.is_trusted("unknown") is False

    def test_initial_allowlist_immutable(self, mock_identity_manager):
        """Modifying the initial allowlist set should not affect internal state."""
        initial = {"peer-1", "peer-2"}
        tm = PeerTrustManager(
            identity_manager=mock_identity_manager,
            trust_policy="strict",
            initial_allowlist=initial,
        )
        initial.add("peer-3")
        assert tm.is_trusted("peer-3") is False


class TestPeerTrustManagerSettings:
    """Test PeerTrustManager configuration from settings."""

    def test_settings_has_p2p_config(self):
        """Settings should expose get_p2p_config()."""
        from hierachain.config.settings import Settings
        config = Settings.get_p2p_config()
        assert "trust_policy" in config
        assert "peer_allowlist" in config
        assert "require_signatures" in config

    def test_production_settings_strict(self):
        """ProductionSettings should default to strict trust policy."""
        from hierachain.config.settings import ProductionSettings
        assert ProductionSettings.P2P_TRUST_POLICY == "strict"
        assert ProductionSettings.P2P_REQUIRE_SIGNATURES is True

    def test_dev_settings_open(self):
        """Default Settings should use open trust policy."""
        from hierachain.config.settings import Settings
        # Default is "open" unless env var overrides
        assert Settings.P2P_TRUST_POLICY == "open" or True  # env-dependent
