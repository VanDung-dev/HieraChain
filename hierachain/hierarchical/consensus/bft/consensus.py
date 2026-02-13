"""
Byzantine Fault Tolerance Consensus Implementation
"""

import time
import threading
import logging
from typing import Any, Callable

from hierachain.error_mitigation.validator import ConsensusValidator
from hierachain.error_mitigation.error_classifier import ErrorClassifier
from hierachain.security.security_utils import KeyPair
from hierachain.security.key_provider import LocalKeyProvider
from hierachain.network.zmq_transport import ZmqNode
from hierachain.config.settings import settings

from hierachain.hierarchical.consensus.bft.types import (
    ConsensusState, MessageType, BFTMessage, ConsensusError
)
from hierachain.hierarchical.consensus.bft.cryptographic import (
    sign_message,
    verify_message_signature,
    hash_request,
    verify_operation_zk_proof
)
from hierachain.hierarchical.consensus.bft.network import (
    send_via_zmq,
    broadcast,
    forward_to_primary
)
from hierachain.hierarchical.consensus.bft.view_manager import (
    validate_view_change_proof,
    start_view_change_timer
)

logger = logging.getLogger(__name__)

# --- Helper Functions (Moved to Module Level to Reduce Class Complexity) ---

def _execute_consensus_operation(chain: Any, operation: dict[str, Any], seq: int, view: int):
    """Execute operation by adding it to the chain reference."""
    try:
        event = {
            "entity_id": operation.get("entity_id"),
            "event": operation.get("event_type", "consensus_operation"),
            "timestamp": time.time(),
            "details": operation.get("details", {}),
            "consensus": {"sequence": seq,"view": view,"committed_at": time.time()}
        }
        if chain:
            chain.add_event(event)
    except Exception as e:
        logger.error("Error executing operation: %s", e)

def _log_behavior(
    error_classifier: Any,
    failure_counts: dict[str, int],
    max_failures: int,
    auto_recovery: bool,
    node_id: str,
    issue: str,
    view: int,
    seq: int,
    recovery_callback: Callable[[int], None]
):
    """Log node behavior and optionally initiate recovery."""
    if not error_classifier:
        return
        
    error_classifier.classify_error({
        "error_type": f"node_{issue}",
        "message": f"Node {node_id} exhibited {issue}",
        "metadata": {
            "node_id": node_id,
            "issue": issue,
            "timestamp": time.time(),
            "view": view,
            "sequence": seq
        }
    })
    
    failure_counts[node_id] = failure_counts.get(node_id, 0) + 1
    if failure_counts[node_id] >= max_failures and auto_recovery:
        recovery_callback(view + 1)

def _validate_consensus_message(
    message: BFTMessage,
    all_nodes: list[str],
    public_keys: dict[str, str],
    strictness: str,
    timeout: float,
    log_func: Callable[[str, str], None]
) -> bool:
    """Validate message basic parameters, signature, and timeliness."""
    if (
        message.sender_id not in all_nodes or 
        message.view < 0 or 
        message.sequence_number < 0
    ):
        return False
        
    if not verify_message_signature(message, public_keys):
        if strictness == "high":
            return False
        log_func(message.sender_id, "signature_verification_failed")
        
    if (time.time() - message.timestamp) > timeout:
        log_func(message.sender_id, "slow_message")
        
    return True

def _cleanup_messages(
    pre_prep: dict[int, BFTMessage],
    prep: dict[int, list[BFTMessage]],
    commit: dict[int, list[BFTMessage]],
    committed_seq: int
):
    """Cleanup message storage for old sequences."""
    threshold = committed_seq - 100
    for seq in list(pre_prep.keys()):
        if seq < threshold:
            pre_prep.pop(seq, None)
            prep.pop(seq, None)
            commit.pop(seq, None)

def _create_signed_bft_message(
    msg_type: MessageType,
    view: int,
    seq: int,
    node_id: str,
    key_provider: Any,
    data: dict[str, Any]
) -> BFTMessage:
    """Create and sign a BFT message helper."""
    msg = BFTMessage(
        msg_type, view, seq, node_id, time.time(), "", data
    )
    if key_provider:
        msg.signature = sign_message(key_provider, msg.get_signable_payload())
    return msg

def _add_to_votes(votes: list[BFTMessage], message: BFTMessage) -> bool:
    """Add message to votes list avoiding duplicates from same sender."""
    if any(m.sender_id == message.sender_id for m in votes):
        return False
    votes.append(message)
    return True

def _validate_prepare_msg(
    message: BFTMessage,
    state: ConsensusState,
    pre_prep_messages: dict[int, BFTMessage],
    public_keys: dict[str, str],
    log_func: Callable[[str, str], None]
) -> bool:
    """Validate PREPARE message parameters and signatures."""
    seq = message.sequence_number
    if seq not in pre_prep_messages and state != ConsensusState.PRE_PREPARED:
        return False
        
    if not verify_message_signature(message, public_keys):
        log_func(message.sender_id, "invalid_signature")
        return False
    
    pre_prep = pre_prep_messages.get(seq)
    if pre_prep and pre_prep.data.get("digest") != message.data.get("digest"):
        log_func(message.sender_id, "digest_mismatch")
        return False
        
    return True

def _validate_commit_msg(
    message: BFTMessage,
    pre_prep_messages: dict[int, BFTMessage],
    prep_messages: dict[int, list[BFTMessage]],
    public_keys: dict[str, str],
    log_func: Callable[[str, str], None]
) -> bool:
    """Validate COMMIT message parameters and signatures."""
    seq = message.sequence_number
    if seq not in pre_prep_messages and seq not in prep_messages:
        return False

    if not verify_message_signature(message, public_keys):
        log_func(message.sender_id, "invalid_signature")
        return False
    return True


def _validate_pre_prep_basic(
    node_id: str,
    primary_id: str,
    view: int,
    committed_seq: int,
    message: BFTMessage,
    public_keys: dict[str, str]
) -> bool:
    """Basic validation for PRE_PREPARE message."""
    if (
        node_id == primary_id or
        message.view != view or
        message.sequence_number <= committed_seq or
        message.sender_id != primary_id
    ):
        return False
    return verify_message_signature(message, public_keys)


def _process_prepare_quorum_logic(
    node_id: str,
    f: int,
    view: int,
    seq: int,
    digest: str | None,
    state: ConsensusState,
    prepare_count: int,
    key_provider: Any
) -> tuple[ConsensusState, BFTMessage | None]:
    """Determine if prepare quorum is reached and create commit message."""
    if prepare_count >= 2 * f and state == ConsensusState.PRE_PREPARED:
        msg = _create_signed_bft_message(
            MessageType.COMMIT, view, seq, node_id, key_provider, {"digest": digest}
        )
        return ConsensusState.PREPARED, msg
    return state, None


def _process_commit_quorum_logic(
    f: int,
    commit_msgs: list[BFTMessage],
    pre_prep_messages: dict[int, BFTMessage]
) -> tuple[bool, BFTMessage | None]:
    """Check if 2f+1 COMMIT messages received."""
    if len(commit_msgs) >= 2 * f + 1:
        for msg in commit_msgs:
            pre_prep = pre_prep_messages.get(msg.sequence_number)
            if pre_prep:
                return True, pre_prep
    return False, None


def _init_bft_mitigation_data(error_config: dict[str, Any]) -> dict[str, Any]:
    """Extract mitigation configuration from error config."""
    consensus_config = error_config.get("consensus", {}).get("bft", {})
    return {
        "validator": ConsensusValidator(
            consensus_config.get("node_validation", {})
        ),
        "classifier": ErrorClassifier(
            error_config.get("classification", {})
        ),
        "strictness": consensus_config.get("verification_strictness", "high"),
        "recovery": error_config.get(
            "recovery", {}
        ).get("auto_recovery", {}).get("enabled", False)
    }


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
        zmq_node: ZmqNode | None = None
    ):
        """Initialize BFT consensus"""
        self.node_id = node_id
        self.all_nodes = all_nodes
        self.f = f
        self.n = len(all_nodes)
        self.node_public_keys = node_public_keys or {}
        self.zmq_node = zmq_node
        self.key_provider = LocalKeyProvider(keypair) if keypair else None
        
        self.network_send_function: Callable | None = None
        self.chain: Any | None = None
        
        if zmq_node:
            if zmq_node.node_id != node_id:
                logger.warning("ZmqNode ID %s mismatch with %s", zmq_node.node_id, node_id)
            self.network_send_function = self._direct_send

        if not self.key_provider:
            raise ConsensusError("Cryptographic keys are required for BFT consensus")

        if self.n < 3 * self.f + 1:
            raise ConsensusError(f"BFT requires n >= 3f+1, but n={self.n}, f={self.f}")
        
        # State and Storage
        self.view = 0
        self.sequence_number = 0
        self.state = ConsensusState.IDLE
        self.current_request: dict[str, Any] | None = None
        self.pre_prepare_messages: dict[int, BFTMessage] = {}
        self.prepare_messages: dict[int, list[BFTMessage]] = {}
        self.commit_messages: dict[int, list[BFTMessage]] = {}
        self.view_change_votes: dict[int, list[BFTMessage]] = {}
        self.committed_sequence = -1
        self.pending_requests: list[dict[str, Any]] = []
        self.message_log: list[BFTMessage] = []

        # Monitoring
        self.node_failure_counts: dict[str, int] = {}
        self.max_failure_count = 3
        self.view_change_timer: threading.Timer | None = None
        self.view_change_timeout = 30.0
        self.lock = threading.Lock()

        # Message Handlers with explicit type hint for IDE/Linting
        self.message_handlers: dict[MessageType, Callable[[BFTMessage], bool]] = {
            MessageType.PRE_PREPARE: self._handle_pre_prepare,
            MessageType.PREPARE: self._handle_prepare,
            MessageType.COMMIT: self._handle_commit,
            MessageType.VIEW_CHANGE: self._handle_view_change,
            MessageType.NEW_VIEW: self._handle_new_view
        }
        
        self._shutting_down = False
        self._start_view_change_timer()
        
        # Error mitigation
        self.error_config = error_config or {}
        mitigation = _init_bft_mitigation_data(self.error_config)
        self.consensus_validator = mitigation["validator"]
        self.error_classifier = mitigation["classifier"]
        self.verification_strictness = mitigation["strictness"]
        self.auto_recovery_enabled = mitigation["recovery"]

        if self.consensus_validator:
            nodes = [type('MockNode', (), {"node_id": n})() for n in self.all_nodes]
            self.consensus_validator.validate_node_count(nodes)
    
    def _direct_send(self, target_node: str, message: dict[str, Any]):
        """Directly send a message to a node using ZMQ."""
        send_via_zmq(self.zmq_node, target_node, message)

    def set_network_send_function(self, send_func: Callable):
        """Set custom network send function."""
        self.network_send_function = send_func

    def set_chain_reference(self, chain: Any):
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
            digest = hash_request(self.current_request)
            data = {"request": self.current_request, "digest": digest}
            
            msg = _create_signed_bft_message(
                MessageType.PRE_PREPARE, self.view, self.sequence_number,
                self.node_id, self.key_provider, data
            )
            
            self.pre_prepare_messages[self.sequence_number] = msg
            self._broadcast_msg(msg)
            self.state = ConsensusState.PRE_PREPARED
            self.message_log.append(msg)
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
        return self.all_nodes[self.view % self.n]

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
            self._initiate_view_change(self.view + 1)

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

            if settings.ENABLE_ZK_PROOFS and not verify_operation_zk_proof(message.data):
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
            self._reset_view_change_timer()
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
            return True
        return True

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

    def _handle_view_change(self, message: BFTMessage) -> bool:
        """Handle incoming VIEW_CHANGE messages"""
        with self.lock:
            new_view = message.view
            if new_view <= self.view or not verify_message_signature(message, self.node_public_keys):
                return False

            if new_view not in self.view_change_votes:
                self.view_change_votes[new_view] = []

            if not _add_to_votes(self.view_change_votes[new_view], message):
                return False

            return self._process_view_change_quorum(new_view)

    def _process_view_change_quorum(self, new_view: int) -> bool:
        """Check if 2f+1 view change votes received to become new primary and broadcast NEW_VIEW"""
        if len(self.view_change_votes[new_view]) >= 2 * self.f + 1:
            is_new_primary = self.node_id == self.all_nodes[new_view % self.n]
            if is_new_primary and self.state == ConsensusState.VIEW_CHANGE:
                self._broadcast_new_view(new_view, self.view_change_votes[new_view])
        return True
    
    def _handle_new_view(self, message: BFTMessage) -> bool:
        """Handle incoming NEW_VIEW messages."""
        with self.lock:
            new_view = message.view
            if new_view <= self.view or not verify_message_signature(message, self.node_public_keys):
                return False

            if not validate_view_change_proof(
                new_view,
                message.data.get("proof", []),
                self.f,
                self.node_public_keys,
                self._verify_sig_shim
            ):
                self._log_node_behavior(message.sender_id, "invalid_view_change_proof")
                return False

            self.view = new_view
            self.state = ConsensusState.IDLE
            self._reset_view_change_timer()
            return True

    def _verify_sig_shim(self, msg: BFTMessage) -> bool:
        """Shim for signature verification bypass of lambda lint."""
        return verify_message_signature(msg, self.node_public_keys)

    def _broadcast_new_view(self, new_view: int, proof_messages: list[BFTMessage]):
        """Broadcast NEW_VIEW message to all nodes."""
        msg = _create_signed_bft_message(
            MessageType.NEW_VIEW,
            new_view,
            self.committed_sequence,
            self.node_id,
            self.key_provider,
            {"proof": [m.to_dict() for m in proof_messages]}
        )
        self.view = new_view
        self.state = ConsensusState.IDLE
        self._reset_view_change_timer()
        self._broadcast_msg(msg)
    
    def _log_node_behavior(self, node_id: str, issue: str):
        """Log suspicious node behavior."""
        _log_behavior(
            self.error_classifier, self.node_failure_counts,
            self.max_failure_count, self.auto_recovery_enabled,
            node_id, issue, self.view, self.sequence_number,
            self._initiate_view_change
        )

    def _start_view_change_timer(self):
        """Start the view change timer."""
        if not self._shutting_down:
            self.view_change_timer = start_view_change_timer(
                self.view_change_timeout,
                self._view_change_timeout_handler
            )
    
    def _reset_view_change_timer(self):
        """Reset the view change timer."""
        if self.view_change_timer:
            self.view_change_timer.cancel()
        self._start_view_change_timer()

    def _view_change_timeout_handler(self):
        """Handle view change timer expiration."""
        if not self._shutting_down:
            self._initiate_view_change(self.view + 1)

    def _initiate_view_change(self, new_view: int):
        """Initiate view change protocol."""
        with self.lock:
            self.state = ConsensusState.VIEW_CHANGE
            msg = _create_signed_bft_message(
                MessageType.VIEW_CHANGE,
                new_view,
                self.committed_sequence,
                self.node_id,
                self.key_provider,
                {}
            )
            if new_view not in self.view_change_votes:
                self.view_change_votes[new_view] = []
            self.view_change_votes[new_view].append(msg)
            self._broadcast_msg(msg)

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
