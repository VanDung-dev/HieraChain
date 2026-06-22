"""
BFT View Change Manager component.
"""

import logging
from typing import TYPE_CHECKING

from hierachain.consensus.bft.types import ConsensusState, MessageType, BFTMessage
from hierachain.consensus.bft.helpers import (
    verify_message_signature,
    validate_view_change_proof,
    start_view_change_timer,
    _create_signed_bft_message,
    _add_to_votes,
)

if TYPE_CHECKING:
    from hierachain.consensus.bft.consensus import BFTConsensus

logger = logging.getLogger(__name__)


class BFTViewChangeManager:
    """View change manager for BFT consensus"""
    def __init__(self, consensus: "BFTConsensus"):
        self.consensus = consensus

    def start_timer(self):
        """Start the view change timer if consensus is not shutting down."""
        if not self.consensus.is_shutting_down():
            self.consensus.view_change_timer = start_view_change_timer(
                self.consensus.view_change_timeout,
                self._timeout_handler
            )

    def reset_timer(self):
        """Reset the view change timer."""
        if self.consensus.view_change_timer:
            self.consensus.view_change_timer.cancel()
        self.start_timer()

    def _timeout_handler(self):
        """Handle view change timeout."""
        if not self.consensus.is_shutting_down():
            self.initiate_view_change(self.consensus.view + 1)

    def initiate_view_change(self, new_view: int):
        """Initiate a new view change."""
        with self.consensus.lock:
            self.consensus.state = ConsensusState.VIEW_CHANGE
            msg = _create_signed_bft_message(
                MessageType.VIEW_CHANGE,
                new_view,
                self.consensus.committed_sequence,
                self.consensus.node_id,
                self.consensus.key_provider,
                {}
            )
            if new_view not in self.consensus.view_change_votes:
                self.consensus.view_change_votes[new_view] = []
            self.consensus.view_change_votes[new_view].append(msg)
            self.consensus.broadcast_message(msg)

    def handle_view_change(self, message: BFTMessage) -> bool:
        """Handle incoming VIEW_CHANGE messages."""
        with self.consensus.lock:
            new_view = message.view
            if new_view <= self.consensus.view or not verify_message_signature(
                message,
                self.consensus.node_public_keys
            ):
                return False

            if new_view not in self.consensus.view_change_votes:
                self.consensus.view_change_votes[new_view] = []

            if not _add_to_votes(self.consensus.view_change_votes[new_view], message):
                return False

            # Check if we have 2f + 1 view change messages
            if len(self.consensus.view_change_votes[new_view]) >= 2 * self.consensus.f + 1:
                return self._process_view_change_quorum(new_view)
            return True

    def _process_view_change_quorum(self, new_view: int) -> bool:
        """Helper to process view change quorum."""
        # Convert BFTMessage objects to dict format as required by validate_view_change_proof
        proof_dicts = [msg.to_dict() for msg in self.consensus.view_change_votes[new_view]]
        
        valid = validate_view_change_proof(
            view=new_view,
            proof=proof_dicts,
            f=self.consensus.f,
            node_public_keys=self.consensus.node_public_keys,
            verify_sig_func=self._verify_sig
        )
        if valid:
            if self.consensus.node_id == self.consensus.all_nodes[new_view % self.consensus.n]:
                # We are primary for new view
                self._broadcast_new_view(new_view)
            return True
        return False

    def handle_new_view(self, message: BFTMessage) -> bool:
        """Handle incoming NEW_VIEW messages."""
        with self.consensus.lock:
            new_view = message.view
            if new_view <= self.consensus.view or not self._verify_sig(message):
                return False

            # Verify view change proofs in new_view message data
            proofs = message.data.get("proofs", [])
            # Convert BFTMessage proofs or dict proofs to dict format
            proof_dicts = [p.to_dict() if hasattr(p, 'to_dict') else p for p in proofs]
            
            valid = validate_view_change_proof(
                view=new_view,
                proof=proof_dicts,
                f=self.consensus.f,
                node_public_keys=self.consensus.node_public_keys,
                verify_sig_func=self._verify_sig
            )
            if not valid:
                return False

            self.consensus.view = new_view
            self.consensus.state = ConsensusState.IDLE
            self.reset_timer()
            logger.info("Node %s changed to view %d", self.consensus.node_id, new_view)
            return True

    def _verify_sig(self, message: BFTMessage) -> bool:
        return verify_message_signature(message, self.consensus.node_public_keys)

    def _broadcast_new_view(self, new_view: int):
        new_view_msg = _create_signed_bft_message(
            MessageType.NEW_VIEW,
            new_view,
            self.consensus.committed_sequence,
            self.consensus.node_id,
            self.consensus.key_provider,
            {"proofs": [m.to_dict() for m in self.consensus.view_change_votes[new_view]]}
        )
        self.consensus.view = new_view
        self.consensus.state = ConsensusState.IDLE
        self.consensus.broadcast_message(new_view_msg)
        self.reset_timer()
        logger.info(
            "Node %s is primary and broadcasted NEW_VIEW for view %d",
            self.consensus.node_id, new_view
        )
