"""
Byzantine Fault Tolerance Consensus Implementation
"""

import time
import threading
import logging
from typing import Any, Callable, cast

from hierachain.security.security_utils import KeyPair
from hierachain.security.key_provider import LocalKeyProvider
from hierachain.network.zmq_transport import ZmqNode
from hierachain.config.settings import settings

from hierachain.consensus.bft.types import (
    ConsensusState, MessageType, BFTMessage, ConsensusError
)
from hierachain.consensus.bft.helpers import (
    verify_message_signature,
    hash_request,
    verify_operation_zk_proof,
    send_via_zmq,
    broadcast,
    forward_to_primary,
    validate_view_change_proof,
    start_view_change_timer,
    _execute_consensus_operation,
    _log_behavior,
    _validate_consensus_message,
    _cleanup_messages,
    _create_signed_bft_message,
    _add_to_votes,
    _validate_prepare_msg,
    _validate_commit_msg,
    _validate_pre_prep_basic,
    _process_prepare_quorum_logic,
    _process_commit_quorum_logic,
    _init_bft_mitigation_data,
)

logger = logging.getLogger(__name__)


class BFTViewChangeManager:
    """View change manager for BFT consensus"""
    def __init__(self, consensus):
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

            return self._process_view_change_quorum(new_view)

    def _process_view_change_quorum(self, new_view: int) -> bool:
        """Check if view change quorum is reached."""
        if len(self.consensus.view_change_votes[new_view]) >= 2 * self.consensus.f + 1:
            is_new_primary = (
                self.consensus.node_id ==
                self.consensus.all_nodes[new_view % self.consensus.n]
            )
            if is_new_primary and self.consensus.state == ConsensusState.VIEW_CHANGE:
                self._broadcast_new_view(
                    new_view, self.consensus.view_change_votes[new_view]
                )
        return True

    def handle_new_view(self, message: BFTMessage) -> bool:
        """Handle incoming NEW_VIEW messages."""
        with self.consensus.lock:
            new_view = message.view
            if new_view <= self.consensus.view or not verify_message_signature(
                message,
                self.consensus.node_public_keys
            ):
                return False

            if not validate_view_change_proof(
                new_view,
                message.data.get("proof", []),
                self.consensus.f,
                self.consensus.node_public_keys,
                self._verify_sig
            ):
                self.consensus.log_node_behavior(
                    message.sender_id, "invalid_view_change_proof"
                )
                return False

            self.consensus.view = new_view
            self.consensus.state = ConsensusState.IDLE
            self.reset_timer()
            return True

    def _verify_sig(self, msg: BFTMessage) -> bool:
        """Verify message signature."""
        return verify_message_signature(msg, self.consensus.node_public_keys)

    def _broadcast_new_view(self, new_view: int, proof_messages: list[BFTMessage]):
        """Broadcast NEW_VIEW message."""
        msg = _create_signed_bft_message(
            MessageType.NEW_VIEW,
            new_view,
            self.consensus.committed_sequence,
            self.consensus.node_id,
            self.consensus.key_provider,
            {"proof": [m.to_dict() for m in proof_messages]}
        )
        self.consensus.view = new_view
        self.consensus.state = ConsensusState.IDLE
        self.reset_timer()
        self.consensus.broadcast_message(msg)


class BFTConsensus:
    """Byzantine Fault Tolerance consensus implementation"""

    def __init__(
        self,
        node_id: str,
        all_nodes: list[str],
        f: int = 1,
        error_config: dict[str, Any] | None = None,
        keypair: KeyPair | None = None,
        node_public_keys: dict[str, str] | None = None,
        zmq_node: ZmqNode | None = None,
        node_identity: Any | None = None
    ):
        self.node_id = node_id
        self.all_nodes = all_nodes
        self.f = f
        self.n = len(all_nodes)
        
        # Identity and Keys
        if node_identity:
            self.node_id = getattr(node_identity, 'node_id', node_id)
            signing_kp = getattr(node_identity, 'signing_keypair', None)
            self.key_provider = LocalKeyProvider(cast(KeyPair, signing_kp)) if signing_kp else None
            self.node_public_keys = node_public_keys or {}
            self.node_public_keys[self.node_id] = getattr(
                node_identity, 'signing_public_key', ''
            )
        else:
            self.node_public_keys = node_public_keys or {}
            self.key_provider = LocalKeyProvider(keypair) if keypair else None

        self.zmq_node = zmq_node
        self.network_send_function: Callable | None = None
        self.chain: Any | None = None
        self.error_config = error_config or {}
        self._shutting_down = False
        self.view = 0
        self.sequence_number = 0
        self.state = ConsensusState.IDLE
        self.current_request: dict[str, Any] | None = None
        
        # Internal state
        self.pre_prepare_messages: dict[int, BFTMessage] = {}
        self.prepare_messages: dict[int, list[BFTMessage]] = {}
        self.commit_messages: dict[int, list[BFTMessage]] = {}
        self.view_change_votes: dict[int, list[BFTMessage]] = {}
        self.committed_sequence = -1
        self.pending_requests: list[dict[str, Any]] = []
        self.message_log: list[BFTMessage] = []
        self.MAX_MESSAGE_LOG = 10000
        self.seen_nonces: set[str] = set()
        self.MAX_SEEN_NONCES = 100000
        self.node_failure_counts: dict[str, int] = {}
        self.max_failure_count = 3
        self.view_change_timer: threading.Timer | None = None
        self.view_change_timeout = 30.0
        self.lock = threading.Lock()
        self.view_change_manager = BFTViewChangeManager(self)
        self.message_handlers: dict[MessageType, Callable[[BFTMessage], bool]] = {
            MessageType.PRE_PREPARE: self._handle_pre_prepare,
            MessageType.PREPARE: self._handle_prepare,
            MessageType.COMMIT: self._handle_commit,
            MessageType.VIEW_CHANGE: self.view_change_manager.handle_view_change,
            MessageType.NEW_VIEW: self.view_change_manager.handle_new_view
        }

        self._configure_network()
        self._validate_initial_requirements()
        self._init_error_mitigation()
        self._validate_bft_requirements()
        self.view_change_manager.start_timer()

    def _initiate_view_change(self, new_view: int):
        """Initiate a new view change."""
        self.view_change_manager.initiate_view_change(new_view)

    def _configure_network(self) -> None:
        """Configure network send function."""
        if self.zmq_node:
            if self.zmq_node.node_id != self.node_id:
                logger.warning(
                    "ZmqNode ID %s mismatch with %s",
                    self.zmq_node.node_id, self.node_id
                )
            self.network_send_function = self._direct_send

    def _validate_initial_requirements(self) -> None:
        """Validate initial consensus requirements."""
        if not self.key_provider:
            raise ConsensusError("Cryptographic keys are required for BFT consensus")
        if self.n < 3 * self.f + 1:
            raise ConsensusError(f"BFT requires n >= 3f+1, but n={self.n}, f={self.f}")


    def _direct_send(self, target_node: str, message: dict[str, Any]) -> None:
        """Directly send a message to a node using ZMQ."""
        send_via_zmq(self.zmq_node, target_node, message)

    def set_network_send_function(self, send_func: Callable) -> None:
        """Set custom network send function."""
        self.network_send_function = send_func

    def set_chain_reference(self, chain: Any) -> None:
        """Set blockchain reference for operation execution."""
        self.chain = chain
    
    def request(self, operation: dict[str, Any]) -> bool:
        """Client request to the consensus protocol"""
        with self.lock:
            if self.node_id != self._primary():
                forward_to_primary(
                    self.network_send_function, self._primary(),
                    self.node_id, operation
                )
                return False
            
            self.sequence_number += 1
            self.current_request = {
                "operation": operation,
                "client_id": operation.get("client_id", "unknown"),
                "timestamp": time.time()
            }
            digest = hash_request(cast(dict[str, Any], self.current_request))
            data = {"request": self.current_request, "digest": digest}
            
            msg = _create_signed_bft_message(
                MessageType.PRE_PREPARE, self.view, self.sequence_number,
                self.node_id, self.key_provider, data
            )
            
            self.pre_prepare_messages[self.sequence_number] = msg
            self._broadcast_msg(msg)
            self.state = ConsensusState.PRE_PREPARED
            self.message_log.append(msg)
            if len(self.message_log) > self.MAX_MESSAGE_LOG:
                self.message_log = self.message_log[-self.MAX_MESSAGE_LOG:]
            return True
    
    def handle_message(self, message: dict[str, Any]) -> bool:
        """Handle incoming consensus messages"""
        try:
            msg_type = MessageType(message["message_type"])
            bft_msg = BFTMessage(
                msg_type, message["view"],
                message["sequence_number"],
                message["sender_id"],
                message["timestamp"],
                message["signature"],
                message.get("data", {}),
                message.get("nonce", "")
            )
            
            if not _validate_consensus_message(
                bft_msg,
                self.all_nodes,
                self.node_public_keys,
                self.verification_strictness,
                self.view_change_timeout,
                self._log_node_behavior
            ):
                return False
            
            handler = self.message_handlers.get(msg_type)
            if handler:
                return handler(bft_msg)
            return False
        except (ValueError, KeyError, TypeError) as e:
            logger.error("Error handling message: %s", e)
            return False
        except Exception as e:
            logger.error("Unexpected error in handle_message: %s", e)
            return False
    
    def _primary(self) -> str:
        """Return the primary node for the current view."""
        return self.all_nodes[self.view % self.n]

    def is_shutting_down(self) -> bool:
        """Check if consensus is shutting down."""
        return self._shutting_down

    def broadcast_message(self, msg: BFTMessage):
        """Broadcast message with failure detection."""
        self._broadcast_msg(msg)

    def log_node_behavior(self, node_id: str, issue: str):
        """Log node behavior issues."""
        self._log_node_behavior(node_id, issue)

    def _broadcast_msg(self, msg: BFTMessage):
        """Broadcast message with failure detection."""
        failed = broadcast(
            self.zmq_node,
            self.network_send_function,
            self.all_nodes,
            self.node_id,
            msg,
            self._log_node_behavior
        )
        if failed > self.f and self.auto_recovery_enabled:
            self.view_change_manager.initiate_view_change(self.view + 1)

    # --- Message Handlers ---
    def _handle_pre_prepare(self, message: BFTMessage) -> bool:
        """Handle incoming PRE_PREPARE messages."""
        with self.lock:
            if not _validate_pre_prep_basic(
                self.node_id,
                self._primary(),
                self.view,
                self.committed_sequence,
                message,
                self.node_public_keys
            ):
                return False

            if (
                settings.ENABLE_ZK_PROOFS and
                not verify_operation_zk_proof(message.data)
            ):
                return False

            self.pre_prepare_messages[message.sequence_number] = message
            self.state = ConsensusState.PRE_PREPARED
            
            prep_msg = _create_signed_bft_message(
                MessageType.PREPARE,
                self.view,
                message.sequence_number,
                self.node_id,
                self.key_provider,
                {"digest": message.data.get("digest")}
            )
            self._broadcast_msg(prep_msg)
            self.message_log.append(prep_msg)
            if len(self.message_log) > self.MAX_MESSAGE_LOG:
                self.message_log = self.message_log[-self.MAX_MESSAGE_LOG:]
            self.view_change_manager.reset_timer()
            return True

    def _handle_prepare(self, message: BFTMessage) -> bool:
        """Handle incoming PREPARE messages"""
        with self.lock:
            if not _validate_prepare_msg(
                message,
                self.state,
                self.pre_prepare_messages,
                self.node_public_keys,
                self._log_node_behavior
            ):
                return False
            
            seq = message.sequence_number
            if seq not in self.prepare_messages:
                self.prepare_messages[seq] = []
            
            if not _add_to_votes(self.prepare_messages[seq], message):
                return False
            
            return self._check_prepare_quorum(seq, message.data.get("digest"))

    def _check_prepare_quorum(self, seq: int, digest: str | None) -> bool:
        """Check if 2f PREPARE messages received."""
        self.state, commit_msg = _process_prepare_quorum_logic(
            self.node_id,
            self.f,
            self.view,
            seq,
            digest,
            self.state,
            len(self.prepare_messages[seq]),
            self.key_provider
        )
        if commit_msg:
            self._broadcast_msg(commit_msg)
            self.message_log.append(commit_msg)
            if len(self.message_log) > self.MAX_MESSAGE_LOG:
                self.message_log = self.message_log[-self.MAX_MESSAGE_LOG:]
            return True
        return False

    def _handle_commit(self, message: BFTMessage) -> bool:
        """Handle incoming COMMIT messages"""
        with self.lock:
            if not _validate_commit_msg(
                message,
                self.pre_prepare_messages,
                self.prepare_messages,
                self.node_public_keys,
                self._log_node_behavior
            ):
                return False
                
            seq = message.sequence_number
            if seq not in self.commit_messages:
                self.commit_messages[seq] = []
                
            if not _add_to_votes(self.commit_messages[seq], message):
                return False
            
            return self._process_commit_quorum(seq)

    def _process_commit_quorum(self, seq: int) -> bool:
        """Check if commit quorum is reached and execute."""
        reached, pre_prep = _process_commit_quorum_logic(
            self.f,
            self.commit_messages[seq],
            self.pre_prepare_messages
        )
        if reached and pre_prep:
            _execute_consensus_operation(
                self.chain,
                pre_prep.data["request"]["operation"],
                seq,
                self.view
            )
            self.committed_sequence = max(self.committed_sequence, seq)
            self.state = ConsensusState.COMMITTED
            _cleanup_messages(
                self.pre_prepare_messages,
                self.prepare_messages,
                self.commit_messages, seq
            )
            return True
        return False

    def _log_node_behavior(self, node_id: str, issue: str):
        """Log suspicious node behavior."""
        _log_behavior(
            self.error_classifier, self.node_failure_counts,
            self.max_failure_count, self.auto_recovery_enabled,
            node_id, issue, self.view, self.sequence_number,
            self.view_change_manager.initiate_view_change
        )

    def get_consensus_status(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "view": self.view,
            "sequence_number": self.sequence_number,
            "state": self.state.value,
            "committed_sequence": self.committed_sequence,
            "n": self.n,
            "f": self.f
        }

    def shutdown(self):
        """Shutdown consensus node components."""
        self._shutting_down = True
        if self.view_change_timer:
            self.view_change_timer.cancel()

    def _init_error_mitigation(self):
        """Initialize error mitigation components."""
        mitigation = _init_bft_mitigation_data(self.error_config)
        self.consensus_validator = mitigation["validator"]
        self.error_classifier = mitigation["classifier"]
        self.verification_strictness = mitigation["strictness"]
        self.auto_recovery_enabled = mitigation["recovery"]

    def _validate_bft_requirements(self):
        """Validate BFT network requirements."""
        if self.consensus_validator:
            nodes = [type('MockNode', (), {"node_id": n})() for n in self.all_nodes]
            self.consensus_validator.validate_node_count(nodes)
