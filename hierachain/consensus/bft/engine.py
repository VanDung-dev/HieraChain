"""
BFT Consensus Engine component.
"""

import logging
from typing import Any

from hierachain.config.settings import settings
from hierachain.consensus.bft.types import ConsensusState, MessageType, BFTMessage
from hierachain.consensus.bft.helpers import (
    verify_operation_zk_proof,
    _create_signed_bft_message,
    _add_to_votes,
    _validate_prepare_msg,
    _validate_commit_msg,
    _validate_pre_prep_basic,
    _process_prepare_quorum_logic,
    _process_commit_quorum_logic,
    _execute_consensus_operation,
    _cleanup_messages,
)

logger = logging.getLogger(__name__)


class BFTConsensusEngine:
    """Manages the 3-phase PBFT protocol consensus engine execution"""

    def __init__(self, consensus: Any):
        self.consensus = consensus

    def handle_pre_prepare(self, message: BFTMessage) -> bool:
        """Handle incoming PRE_PREPARE messages."""
        with self.consensus.lock:
            if not _validate_pre_prep_basic(
                self.consensus.node_id,
                self.consensus.primary(),
                self.consensus.view,
                self.consensus.committed_sequence,
                message,
                self.consensus.node_public_keys
            ):
                return False

            if (
                settings.ENABLE_ZK_PROOFS and
                not verify_operation_zk_proof(message.data)
            ):
                return False

            self.consensus.pre_prepare_messages[message.sequence_number] = message
            self.consensus.state = ConsensusState.PRE_PREPARED
            
            prep_msg = _create_signed_bft_message(
                MessageType.PREPARE,
                self.consensus.view,
                message.sequence_number,
                self.consensus.node_id,
                self.consensus.key_provider,
                {"digest": message.data.get("digest")}
            )
            self.consensus.dispatcher.broadcast_msg(prep_msg)
            self.consensus.message_log.append(prep_msg)
            if len(self.consensus.message_log) > self.consensus.MAX_MESSAGE_LOG:
                self.consensus.message_log = self.consensus.message_log[-self.consensus.MAX_MESSAGE_LOG:]
            self.consensus.view_change_manager.reset_timer()
            return True

    def handle_prepare(self, message: BFTMessage) -> bool:
        """Handle incoming PREPARE messages"""
        with self.consensus.lock:
            if not _validate_prepare_msg(
                message,
                self.consensus.state,
                self.consensus.pre_prepare_messages,
                self.consensus.node_public_keys,
                self.consensus.log_node_behavior
            ):
                return False

            seq = message.sequence_number
            if seq not in self.consensus.prepare_messages:
                self.consensus.prepare_messages[seq] = []

            if not _add_to_votes(self.consensus.prepare_messages[seq], message):
                return False

            # Check for preparation quorum
            digest = message.data.get("digest")
            return self.check_prepare_quorum(seq, digest)

    def check_prepare_quorum(self, seq: int, digest: str | None) -> bool:
        """Check if 2f PREPARE messages received."""
        self.consensus.state, commit_msg = _process_prepare_quorum_logic(
            self.consensus.node_id,
            self.consensus.f,
            self.consensus.view,
            seq,
            digest,
            self.consensus.state,
            len(self.consensus.prepare_messages[seq]),
            self.consensus.key_provider
        )
        if commit_msg:
            self.consensus.dispatcher.broadcast_msg(commit_msg)
            self.consensus.message_log.append(commit_msg)
            if len(self.consensus.message_log) > self.consensus.MAX_MESSAGE_LOG:
                self.consensus.message_log = self.consensus.message_log[-self.consensus.MAX_MESSAGE_LOG:]
            return True
        return False

    def handle_commit(self, message: BFTMessage) -> bool:
        """Handle incoming COMMIT messages"""
        with self.consensus.lock:
            if not _validate_commit_msg(
                message,
                self.consensus.pre_prepare_messages,
                self.consensus.prepare_messages,
                self.consensus.node_public_keys,
                self.consensus.log_node_behavior
            ):
                return False
                
            seq = message.sequence_number
            if seq not in self.consensus.commit_messages:
                self.consensus.commit_messages[seq] = []
                
            if not _add_to_votes(self.consensus.commit_messages[seq], message):
                return False
            
            return self.process_commit_quorum(seq)

    def process_commit_quorum(self, seq: int) -> bool:
        """Check if commit quorum is reached and execute."""
        reached, pre_prep = _process_commit_quorum_logic(
            self.consensus.f,
            self.consensus.commit_messages[seq],
            self.consensus.pre_prepare_messages
        )
        if reached and pre_prep:
            _execute_consensus_operation(
                self.consensus.chain,
                pre_prep.data["request"]["operation"],
                seq,
                self.consensus.view
            )
            self.consensus.committed_sequence = max(self.consensus.committed_sequence, seq)
            self.consensus.state = ConsensusState.COMMITTED
            _cleanup_messages(
                self.consensus.pre_prepare_messages,
                self.consensus.prepare_messages,
                self.consensus.commit_messages, seq
            )
            return True
        return False
