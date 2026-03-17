"""
Peer Trust Management Module

This module handles policy enforcement for network peers, including:
- Allowlisting (Trusted Peers)
- Blocklisting (Banned Peers)
- Environment-aware trust policies (open for dev, strict for production)
- Integration with IdentityManager for organization-level trust
"""

import logging

from hierachain.security.identity import IdentityManager


logger = logging.getLogger(__name__)


def _evaluate_strict_policy(peer_id: str) -> bool:
    """Evaluate strict policy for a peer."""
    logger.debug("Peer %s rejected (strict mode - not in allowlist)", peer_id)
    return False


class PeerTrustManager:
    """
    Manages trust relationships with network peers.

    Supports two trust policies:
    - "open": All peers are trusted unless explicitly blocked.
    - "strict": Only allowlisted peers are trusted (production default).
    """

    VALID_POLICIES = ("open", "strict")

    def __init__(
        self,
        identity_manager: IdentityManager | None = None,
        trust_policy: str = "open",
        initial_allowlist: set[str] | None = None,
    ) -> None:
        if trust_policy not in self.VALID_POLICIES:
            raise ValueError(
                f"Invalid trust_policy '{trust_policy}'. "
                f"Use one of: {self.VALID_POLICIES}"
            )

        self.identity_manager = identity_manager
        self.allowlist: set[str] = set(initial_allowlist or set())
        self.blocklist: set[str] = set()
        self.trust_policy = trust_policy

        if trust_policy == "strict" and not self.allowlist:
            logger.warning(
                "PeerTrustManager initialized with 'strict' policy "
                "but empty allowlist. No peers will be accepted."
            )

    def trust_peer(self, peer_id: str):
        """Add peer to allowlist."""
        self.allowlist.add(peer_id)
        if peer_id in self.blocklist:
            self.blocklist.remove(peer_id)
        logger.info("Peer %s added to allowlist", peer_id)

    def block_peer(self, peer_id: str, reason: str = "administrative"):
        """Block a peer."""
        self.blocklist.add(peer_id)
        if peer_id in self.allowlist:
            self.allowlist.remove(peer_id)
        logger.warning("Peer %s blocked: %s", peer_id, reason)

    def is_trusted(self, peer_id: str) -> bool:
        """
        Check if a peer is trusted based on current policy.
        """
        if self._is_blocked(peer_id):
            return False
        if self._is_allowlisted(peer_id):
            return True
        if self.trust_policy == "strict":
            return _evaluate_strict_policy(peer_id)
        if self.trust_policy == "open":
            return self._evaluate_open_policy(peer_id)
        return False

    def _is_blocked(self, peer_id: str) -> bool:
        """Check if a peer is in the blocklist."""
        if peer_id in self.blocklist:
            logger.debug("Peer %s rejected (blocklisted)", peer_id)
            return True
        return False

    def _is_allowlisted(self, peer_id: str) -> bool:
        """Check if a peer is in the allowlist."""
        return peer_id in self.allowlist

    def _evaluate_open_policy(self, peer_id: str) -> bool:
        """Evaluate open policy trust for a peer"""
        if self.identity_manager:
            user_info = self.identity_manager.get_user_info(peer_id)
            if not user_info:
                return True
        return True

    def set_policy(self, policy: str):
        """Set trust policy mode ('open' or 'strict')."""
        if policy not in self.VALID_POLICIES:
            raise ValueError(
                f"Invalid policy '{policy}'. Use one of: {self.VALID_POLICIES}"
            )
        self.trust_policy = policy
        logger.info("Trust policy changed to '%s'", policy)

    def load_allowlist(self, peer_ids: list[str]):
        """Load a list of peer IDs into the allowlist."""
        for pid in peer_ids:
            pid = pid.strip()
            if pid:
                self.allowlist.add(pid)
        logger.info(
            "Loaded %s peers into allowlist. Total: %s",
            len(peer_ids), len(self.allowlist)
        )
