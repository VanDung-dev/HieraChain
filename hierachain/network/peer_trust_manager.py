"""
Peer Trust Management Module

This module handles policy enforcement for network peers, including:
- Allowlisting (Trusted Peers)
- Blocklisting (Banned Peers)
- Integration with IdentityManager for organization-level trust
"""

import logging

from hierachain.security.identity import IdentityManager


logger = logging.getLogger(__name__)

class PeerTrustManager:
    """
    Manages trust relationships with network peers.
    """

    def __init__(self, identity_manager: IdentityManager | None = None):
        self.identity_manager = identity_manager
        self.allowlist: set[str] = set()
        self.blocklist: set[str] = set()
        self.trust_policy = "open"  # Options: "open", "strict" (allowlist only), "hybrid"

    def trust_peer(self, peer_id: str):
        """Add peer to allowlist."""
        self.allowlist.add(peer_id)
        if peer_id in self.blocklist:
            self.blocklist.remove(peer_id)
        logger.info(f"Peer {peer_id} added to allowlist")

    def block_peer(self, peer_id: str, reason: str = "administrative"):
        """Block a peer."""
        self.blocklist.add(peer_id)
        if peer_id in self.allowlist:
            self.allowlist.remove(peer_id)
        logger.warning(f"Peer {peer_id} blocked: {reason}")

    def is_trusted(self, peer_id: str) -> bool:
        """
        Check if a peer is trusted based on current policy.
        """
        # 1. Blocklist check (Override)
        if peer_id in self.blocklist:
            logger.debug(f"Peer {peer_id} rejected (blocklisted)")
            return False

        # 2. Allowlist check
        if peer_id in self.allowlist:
            return True

        # 3. Policy Enforcement
        if self.trust_policy == "strict":
            # Strict mode: Must be explicitly allowlisted
            logger.debug(f"Peer {peer_id} rejected (strict mode - not in allowlist)")
            return False

        if self.trust_policy == "open":
            # Open mode: Trusted if not blocked
            # Optional: Check IdentityManager if available
            if self.identity_manager:
                user_info = self.identity_manager.get_user_info(peer_id)
                if not user_info:
                    pass
            return True

        return False

    def set_policy(self, policy: str):
        """Set trust policy mode ('open' or 'strict')."""
        if policy not in ["open", "strict"]:
            raise ValueError("Invalid policy (use 'open' or 'strict')")
        self.trust_policy = policy
