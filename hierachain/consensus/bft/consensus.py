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
from hierachain.consensus.bft.types import (
    ConsensusState, MessageType, BFTMessage, ConsensusError
)
from hierachain.consensus.bft.helpers import (
    hash_request,
    forward_to_primary,
    _log_behavior,
    _validate_consensus_message,
    _create_signed_bft_message,
    _init_bft_mitigation_data,
)
from hierachain.consensus.bft.view_change import BFTViewChangeManager
from hierachain.consensus.bft.dispatcher import BFTMessageDispatcher
from hierachain.consensus.bft.engine import BFTConsensusEngine

logger = logging.getLogger(__name__)


class BFTConsensus:
    """Byzantine Fault Tolerance consensus implementation"""

    def _setup_node_identity_and_keys(
        self,
        node_id: str,
        node_identity: Any | None,
        keypair: KeyPair | None,
        node_public_keys: dict[str, str] | None
    ) -> None:
        """Helper to initialize node identifier, signing key, and public keys dict."""
        self.node_id = node_id
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
        self.all_nodes = all_nodes
        self.f = f
        self.n = len(all_nodes)
        
        self._setup_node_identity_and_keys(node_id, node_identity, keypair, node_public_keys)

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

        # Helper managers
        self.view_change_manager = BFTViewChangeManager(self)
        self.dispatcher = BFTMessageDispatcher(self)
        self.engine = BFTConsensusEngine(self)

        self.message_handlers: dict[MessageType, Callable[[BFTMessage], bool]] = {
            MessageType.PRE_PREPARE: self.engine.handle_pre_prepare,
            MessageType.PREPARE: self.engine.handle_prepare,
            MessageType.COMMIT: self.engine.handle_commit,
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
        self.dispatcher.direct_send(target_node, message)

    def set_network_send_function(self, send_func: Callable) -> None:
        """Set custom network send function."""
        self.network_send_function = send_func
    
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
            self.dispatcher.broadcast_msg(msg)
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
    
    def primary(self) -> str:
        """Return the primary node for the current view."""
        return self._primary()

    def _primary(self) -> str:
        """Return the primary node for the current view."""
        return self.all_nodes[self.view % self.n]

    def is_shutting_down(self) -> bool:
        """Check if consensus is shutting down."""
        return self._shutting_down

    def broadcast_message(self, msg: BFTMessage):
        """Broadcast message with failure detection."""
        self.dispatcher.broadcast_msg(msg)

    def log_node_behavior(self, node_id: str, issue: str):
        """Log node behavior issues."""
        self._log_node_behavior(node_id, issue)

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
