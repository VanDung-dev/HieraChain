"""
Byzantine Fault Tolerance Consensus for HieraChain Framework

This module implements the BFT consensus mechanism with 3-phase protocol
(pre-prepare, prepare, commit) for enterprise blockchain applications.
Provides Byzantine fault tolerance with configurable fault tolerance levels.
"""

import time
import hashlib
import threading
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

from hierachain.error_mitigation.validator import ConsensusValidator
from hierachain.error_mitigation.error_classifier import ErrorClassifier
from hierachain.security.security_utils import KeyPair, verify_signature
from hierachain.network.zmq_transport import ZmqNode


class ConsensusState(Enum):
    """Consensus node states"""
    IDLE = "idle"
    PRE_PREPARED = "pre_prepared"
    PREPARED = "prepared"
    COMMITTED = "committed"


class MessageType(Enum):
    """BFT message types"""
    PRE_PREPARE = "pre_prepare"
    PREPARE = "prepare"
    COMMIT = "commit"
    VIEW_CHANGE = "view_change"
    NEW_VIEW = "new_view"


@dataclass
class BFTMessage:
    """BFT consensus message"""
    message_type: MessageType
    view: int
    sequence_number: int
    sender_id: str
    timestamp: float
    signature: str
    data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary for serialization"""
        return {
            "message_type": self.message_type.value,
            "view": self.view,
            "sequence_number": self.sequence_number,
            "sender_id": self.sender_id,
            "timestamp": self.timestamp,
            "signature": self.signature,
            "data": self.data
        }


    def get_signable_payload(self) -> bytes:
        """Get the payload bytes to be signed."""
        # Include critical fields in the signature
        digest = self.data.get("digest") if self.data else None
        
        # Base payload: Type:View:Seq
        payload = f"{self.message_type.value}:{self.view}:{self.sequence_number}"
        
        # Add digest if relevant for the message type
        if digest:
            payload += f":{digest}"
            
        return payload.encode('utf-8')

class ConsensusError(Exception):
    """Exception raised for consensus-related errors"""
    pass


class BFTConsensus:
    """Byzantine Fault Tolerance consensus implementation"""
    
    def __init__(self, node_id: str, all_nodes: List[str], f: int = 1, 
                 error_config: Optional[Dict[str, Any]] = None,
                 keypair: Optional[KeyPair] = None,
                 node_public_keys: Optional[Dict[str, str]] = None,
                 zmq_node: Optional[ZmqNode] = None):
        """
        Initialize BFT consensus
        
        Args:
            node_id: Current node ID
            all_nodes: All validator nodes in the network
            f: Maximum number of Byzantine faults tolerated
            error_config: Optional error mitigation configuration
            keypair: Ed25519 KeyPair for this node (required for signing)
            node_public_keys: Map of node_id -> public_key_hex (required for verification)
            zmq_node: Optional ZeroMQ node for network communication
        """
        self.node_id = node_id
        self.all_nodes = all_nodes
        self.f = f  # Max faulty nodes tolerated
        self.n = len(all_nodes)  # Total nodes
        
        self.keypair = keypair
        self.node_public_keys = node_public_keys or {}
        self.zmq_node = zmq_node
        
        # Network and chain references (initialize before use)
        self.network_send_function: Optional[Callable] = None
        self.chain: Optional[Any] = None
        
        if zmq_node:
            # Verify zmq_node matches our node_id
            if zmq_node.node_id != node_id:
                print(f"Warning: ZmqNode ID {zmq_node.node_id} does not match Consensus ID {node_id}")
            # Set up send function wrapper
            self.network_send_function = self._send_via_zmq
        
        # Validate BFT requirements (n >= 3f + 1)
        if self.n < 3 * self.f + 1:
            raise ConsensusError(
                f"BFT requires at least {3 * f + 1} nodes to tolerate {f} faults, "
                f"but only {self.n} nodes provided"
            )
        
        # Consensus state
        self.view = 0
        self.sequence_number = 0
        self.state = ConsensusState.IDLE
        self.current_request: Optional[Dict[str, Any]] = None
        
        # Message storage
        self.pre_prepare_messages: Dict[int, BFTMessage] = {}
        self.prepare_messages: Dict[int, List[BFTMessage]] = {}
        self.commit_messages: Dict[int, List[BFTMessage]] = {}
        self.committed_sequence = -1
        self.pending_requests: List[Dict[str, Any]] = []
        self.message_log: List[BFTMessage] = []

        # Node monitoring
        self.node_response_times: Dict[str, List[float]] = {}
        self.node_failure_counts: Dict[str, int] = {}
        self.max_failure_count = 3

        # View change state
        self.view_change_timer: Optional[threading.Timer] = None
        self.view_change_timeout = 30.0  # seconds
        self.last_heartbeat = time.time()
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Message handlers
        self.message_handlers = {
            MessageType.PRE_PREPARE: lambda msg: self._handle_pre_prepare(msg),
            MessageType.PREPARE: lambda msg: self._handle_prepare(msg),
            MessageType.COMMIT: lambda msg: self._handle_commit(msg),
            MessageType.VIEW_CHANGE: lambda msg: self._handle_view_change(msg),
            MessageType.NEW_VIEW: lambda msg: self._handle_new_view(msg)
        }
        
        # Shutdown flag to avoid starting timers during teardown
        self._shutting_down = False
        
        # Start view change timer
        self._start_view_change_timer()
        
        # Error mitigation integration
        self.error_config = error_config or {}
        self.consensus_validator = None
        self.error_classifier = None
        self.verification_strictness = "high"
        self.auto_recovery_enabled = False
        
        # Initialize error mitigation if available
        self._init_error_mitigation()
        self._validate_bft_requirements()
    
    def set_network_send_function(self, send_func: Callable):
        """Set function for sending messages over network"""
        self.network_send_function = send_func
    
    def set_chain_reference(self, chain: Any):
        """Set reference to the blockchain"""
        self.chain = chain
    
    def request(self, operation: Dict[str, Any]) -> bool:
        """
        Client request to the consensus protocol
        
        Args:
            operation: The operation to be consensus on
        
        Returns:
            bool: True if request was accepted for consensus
        """
        with self.lock:
            if not self._is_primary():
                # Forward request to primary
                self._forward_to_primary(operation)
                return False
            
            # Primary node creates pre-prepare message
            self.sequence_number += 1
            self.current_request = {
                "operation": operation,
                "client_id": operation.get("client_id", "unknown"),
                "timestamp": time.time()
            }
            
            # Prepare data and digest
            digest = self._hash_request(self.current_request)
            data = {
                "request": self.current_request,
                "digest": digest
            }
            
            # Create pre-prepare message (without signature first)
            pre_prepare_msg = BFTMessage(
                message_type=MessageType.PRE_PREPARE,
                view=self.view,
                sequence_number=self.sequence_number,
                sender_id=self.node_id,
                timestamp=time.time(),
                signature="",
                data=data
            )
            
            # Sign it
            pre_prepare_msg.signature = self._sign_message(pre_prepare_msg.get_signable_payload())
            
            # Store and broadcast
            self.pre_prepare_messages[self.sequence_number] = pre_prepare_msg
            self._broadcast(pre_prepare_msg)
            self.state = ConsensusState.PRE_PREPARED
            self.message_log.append(pre_prepare_msg)
            
            return True
    
    def handle_message(self, message: Dict[str, Any]) -> bool:
        """
        Handle incoming consensus messages
        
        Args:
            message: Message dictionary
        
        Returns:
            bool: True if message was processed successfully
        """
        try:
            # Convert dict to BFTMessage
            msg_type = MessageType(message["message_type"])
            bft_message = BFTMessage(
                message_type=msg_type,
                view=message["view"],
                sequence_number=message["sequence_number"],
                sender_id=message["sender_id"],
                timestamp=message["timestamp"],
                signature=message["signature"],
                data=message.get("data", {})
            )
            
            # Validate message
            if not self._validate_message(bft_message):
                return False
            
            # Handle based on type
            handler = self.message_handlers.get(msg_type)
            if handler:
                return handler(bft_message)
            
            return False
            
        except Exception as e:
            print(f"Error handling message: {e}")
            return False
    
    def _primary(self) -> str:
        """Determine the primary node for current view"""
        return self.all_nodes[self.view % self.n]
    
    def _is_primary(self) -> bool:
        """Check if current node is primary"""
        return self.node_id == self._primary()
    
    def _handle_pre_prepare(self, message: BFTMessage) -> bool:
        """Process pre-prepare message"""
        with self.lock:
            # Don't process if we're the primary
            if self._is_primary():
                return False
            
            # Verify view and sequence number
            if message.view != self.view:
                return False
                
            if message.sequence_number <= self.committed_sequence:
                return False
            
            # Verify sender is primary
            if message.sender_id != self._primary():
                return False
                
            # Verify signature
            if not self._verify_signature(message):
                return False
                
            # Accept message
            self.pre_prepare_messages[message.sequence_number] = message
            self.state = ConsensusState.PRE_PREPARED
            
            # Send prepare message
            prepare_msg = BFTMessage(
                message_type=MessageType.PREPARE,
                view=self.view,
                sequence_number=message.sequence_number,
                sender_id=self.node_id,
                timestamp=time.time(),
                signature="",
                data={
                    "digest": message.data.get("digest")
                }
            )
            prepare_msg.signature = self._sign_message(prepare_msg.get_signable_payload())
            
            self._broadcast(prepare_msg)
            self.message_log.append(prepare_msg)
            
            # Reset view change timer
            self._reset_view_change_timer()
            
            return True
    
    def _handle_prepare(self, message: BFTMessage) -> bool:
        """Process prepare message"""
        with self.lock:
            seq = message.sequence_number
            
            # Verify basic requirements
            if (seq not in self.pre_prepare_messages and 
                self.state != ConsensusState.PRE_PREPARED):
                return False
                
            # Verify signature and digest
            if not self._verify_signature(message):
                # Log potential malicious behavior
                self._log_node_behavior(message.sender_id, "invalid_signature")
                return False
            
            # Verify digest matches pre-prepare
            pre_prepare = self.pre_prepare_messages.get(seq)
            if pre_prepare and pre_prepare.data.get("digest") != message.data.get("digest"):
                # Log potential malicious behavior
                self._log_node_behavior(message.sender_id, "digest_mismatch")
                return False
                
            # Store message
            if seq not in self.prepare_messages:
                self.prepare_messages[seq] = []
            
            # Avoid duplicate messages from same sender
            existing_senders = [msg.sender_id for msg in self.prepare_messages[seq]]
            if message.sender_id in existing_senders:
                return False
            
            self.prepare_messages[seq].append(message)
            
            # Check if we have enough prepare messages (2f)
            if len(self.prepare_messages[seq]) >= 2 * self.f:
                # Send commit message
                commit_msg = BFTMessage(
                    message_type=MessageType.COMMIT,
                    view=self.view,
                    sequence_number=seq,
                    sender_id=self.node_id,
                    timestamp=time.time(),
                    signature="",
                    data={
                        "digest": message.data.get("digest")
                    }
                )
                commit_msg.signature = self._sign_message(commit_msg.get_signable_payload())
                
                self._broadcast(commit_msg)
                self.message_log.append(commit_msg)
                self.state = ConsensusState.PREPARED
            
            return True
    
    def _handle_commit(self, message: BFTMessage) -> bool:
        """Process commit message"""
        with self.lock:
            seq = message.sequence_number
            
            # Verify digest matches pre-prepare
            if (seq not in self.pre_prepare_messages and 
                seq not in self.prepare_messages):
                return False
                
            # Verify signature
            if not self._verify_signature(message):
                # Log potential malicious behavior
                self._log_node_behavior(message.sender_id, "invalid_signature")
                return False
                
            # Store message
            if seq not in self.commit_messages:
                self.commit_messages[seq] = []
            
            # Avoid duplicate messages from same sender
            existing_senders = [msg.sender_id for msg in self.commit_messages[seq]]
            if message.sender_id in existing_senders:
                return False
            
            self.commit_messages[seq].append(message)
            
            # Check if we have enough commit messages (2f + 1)
            if len(self.commit_messages[seq]) >= 2 * self.f + 1:
                # Execute operation and commit
                pre_prepare = self.pre_prepare_messages.get(seq)
                if pre_prepare:
                    self._execute_operation(pre_prepare.data["request"]["operation"])
                    self.committed_sequence = max(self.committed_sequence, seq)
                    self.state = ConsensusState.COMMITTED
                    
                    # Clean up old messages
                    self._cleanup_old_messages(seq)
                    
                    return True
            
            return False
    
    def _handle_view_change(self, message: BFTMessage) -> bool:
        """Process view change message"""
        # Simplified view change implementation
        with self.lock:
            if message.view > self.view:
                self._initiate_view_change(message.view)
            return True
    
    def _handle_new_view(self, message: BFTMessage) -> bool:
        """Process new view message"""
        # Simplified new view implementation
        with self.lock:
            if message.view > self.view:
                self.view = message.view
                self.state = ConsensusState.IDLE
                self._reset_view_change_timer()
            return True
    
    def _execute_operation(self, operation: Dict[str, Any]):
        """Execute the business operation"""
        try:
            # In our framework, this translates to creating an event
            event = {
                "entity_id": operation.get("entity_id"),
                "event": operation.get("event_type", "consensus_operation"),
                "timestamp": time.time(),
                "details": operation.get("details", {}),
                "consensus": {
                    "sequence": self.sequence_number,
                    "view": self.view,
                    "committed_at": time.time()
                }
            }
            
            # Add to chain if reference is set
            if self.chain:
                self.chain.add_event(event)
                
        except Exception as e:
            print(f"Error executing operation: {e}")

    def _send_via_zmq(self, target_id: str, message: Dict[str, Any]):
        """Send message using ZeroMQ transport (sync wrapper for async)."""
        import asyncio
        if self.zmq_node:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If event loop is running, create task
                    asyncio.create_task(self.zmq_node.send_direct(target_id, message))
                else:
                    loop.run_until_complete(self.zmq_node.send_direct(target_id, message))
            except RuntimeError:
                # No event loop, create one
                asyncio.run(self.zmq_node.send_direct(target_id, message))
        else:
            print("Warning: No ZMQ node configured for broadcast")

    def _broadcast(self, message: BFTMessage):
        """Broadcast message to all other nodes with error handling"""
        import asyncio
        # If we have ZMQ, use its efficient broadcast
        if self.zmq_node:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self.zmq_node.broadcast(message.to_dict()))
                else:
                    loop.run_until_complete(self.zmq_node.broadcast(message.to_dict()))
                return
            except RuntimeError:
                asyncio.run(self.zmq_node.broadcast(message.to_dict()))
                return
            except Exception as e:
                print(f"ZMQ Broadcast error: {e}")
                # Fallthrough to manual loop if ZMQ broadcast fails
        
        if self.network_send_function:
            successful_sends = 0
            failed_sends = 0

            for node_id in self.all_nodes:
                if node_id != self.node_id:
                    try:
                        self.network_send_function(node_id, message.to_dict())
                        successful_sends += 1
                    except Exception as e:
                        print(f"Error sending to {node_id}: {e}")
                        failed_sends += 1
                        # Log the network issue
                        self._log_node_behavior(node_id, "network_send_failure")

            # If too many sends failed, consider initiating recovery
            if failed_sends > self.f and self.auto_recovery_enabled:
                print(f"Too many network failures ({failed_sends}), initiating recovery")
                self._initiate_view_change(self.view + 1)

    def _forward_to_primary(self, operation: Dict[str, Any]):
        """Forward request to primary node"""
        if self.network_send_function:
            primary = self._primary()
            if primary != self.node_id:
                try:
                    self.network_send_function(primary, {
                        "type": "client_request",
                        "operation": operation
                    })
                except Exception as e:
                    print(f"Error forwarding to primary {primary}: {e}")

    def _log_node_behavior(self, node_id: str, issue: str):
        """Log node behavior issues for error classification"""
        if not self.error_classifier:
            return

        error_data = {
            "error_type": f"node_{issue}",
            "message": f"Node {node_id} exhibited {issue}",
            "metadata": {
                "node_id": node_id,
                "issue": issue,
                "timestamp": time.time(),
                "view": self.view,
                "sequence": self.sequence_number
            }
        }

        # Classify the error
        _error_info = self.error_classifier.classify_error(error_data)

        # Update node tracking
        if node_id not in self.node_failure_counts:
            self.node_failure_counts[node_id] = 0

        self.node_failure_counts[node_id] += 1

        # If node repeatedly has issues, consider initiating view change
        if self.node_failure_counts[node_id] >= self.max_failure_count and self.auto_recovery_enabled:
            self._initiate_view_change(self.view + 1)

    def _validate_message(self, message: BFTMessage) -> bool:
        """Validate incoming message with enhanced checks"""
        # Basic validation
        if message.sender_id not in self.all_nodes:
            return False
        
        if message.view < 0 or message.sequence_number < 0:
            return False
        
        # Signature validation
        if not self._verify_signature(message):
            # Use verification_strictness setting to determine action
            if self.verification_strictness == "high":
                return False
            # With lower strictness, we might just log the issue
            self._log_node_behavior(message.sender_id, "signature_verification_failed")

        # Check for message timeouts
        current_time = time.time()
        if (current_time - message.timestamp) > self.view_change_timeout:
            self._log_node_behavior(message.sender_id, "slow_message")

        return True

    def _sign_message(self, data: bytes) -> str:
        """
        Sign message data using Ed25519.
        
        Args:
            data: Bytes to sign
            
        Returns:
            Hex encoded signature
        """
        if not self.keypair:
            # Fallback for testing without keys (unsafe for prod)
            combined = f"{self.node_id}:{data}:{time.time()}"
            return hashlib.sha256(combined.encode()).hexdigest()

        return self.keypair.sign(data)
    
    def _verify_signature(self, message: BFTMessage) -> bool:
        """
        Verify message signature using Ed25519.
        """
        if not message.signature:
            return False

        # Fallback to length check if no keys configured (legacy mode)
        if not self.node_public_keys:
            return len(message.signature) == 64

        public_key = self.node_public_keys.get(message.sender_id)
        if not public_key:
            # Unknown sender
            return False
            
        try:
            payload = message.get_signable_payload()
            return verify_signature(public_key, payload, message.signature)
        except Exception as e:
            print(f"Signature verification error: {e}")
            return False
    
    @staticmethod
    def _hash_request(request: Dict[str, Any]) -> str:
        """Create hash of request"""
        request_str = str(sorted(request.items()))
        return hashlib.sha256(request_str.encode()).hexdigest()
    
    def _start_view_change_timer(self):
        """Start view change timer"""
        self._reset_view_change_timer()
    
    def _reset_view_change_timer(self):
        """Reset view change timer"""
        if self.view_change_timer:
            self.view_change_timer.cancel()
        
        # Avoid starting timers during shutdown
        if getattr(self, "_shutting_down", False):
            return
        self.view_change_timer = threading.Timer(
            self.view_change_timeout, 
            self._view_change_timeout_handler
        )
        # Ensure timer won't keep process alive at exit
        try:
            self.view_change_timer.daemon = True  # type: ignore[attr-defined]
        except AttributeError:
            pass
        self.view_change_timer.start()
        self.last_heartbeat = time.time()
    
    def _view_change_timeout_handler(self):
        """Handle view change timeout"""
        with self.lock:
            if self.state != ConsensusState.COMMITTED:
                self._initiate_view_change(self.view + 1)
    
    def _initiate_view_change(self, new_view: int):
        """Initiate view change to new view"""
        self.view = new_view
        self.state = ConsensusState.IDLE
        
        # Broadcast view change message
        view_change_msg = BFTMessage(
            message_type=MessageType.VIEW_CHANGE,
            view=new_view,
            sequence_number=self.committed_sequence,
            sender_id=self.node_id,
            timestamp=time.time(),
            signature="",
            data={
                "last_committed": self.committed_sequence
            }
        )
        view_change_msg.signature = self._sign_message(view_change_msg.get_signable_payload())
        
        self._broadcast(view_change_msg)
        self._reset_view_change_timer()
    
    def _cleanup_old_messages(self, committed_seq: int):
        """Clean up old messages to prevent memory bloat"""
        # Keep only recent messages
        cutoff_seq = committed_seq - 10
        
        # Clean up pre-prepare messages
        old_keys = [k for k in self.pre_prepare_messages.keys() if k < cutoff_seq]
        for k in old_keys:
            del self.pre_prepare_messages[k]
        
        # Clean up prepare messages
        old_keys = [k for k in self.prepare_messages.keys() if k < cutoff_seq]
        for k in old_keys:
            del self.prepare_messages[k]
        
        # Clean up commit messages
        old_keys = [k for k in self.commit_messages.keys() if k < cutoff_seq]
        for k in old_keys:
            del self.commit_messages[k]
        
        # Trim message log
        if len(self.message_log) > 1000:
            self.message_log = self.message_log[-500:]
    
    def get_consensus_status(self) -> Dict[str, Any]:
        """Get current consensus status"""
        with self.lock:
            return {
                "node_id": self.node_id,
                "view": self.view,
                "sequence_number": self.sequence_number,
                "state": self.state.value,
                "is_primary": self._is_primary(),
                "primary_node": self._primary(),
                "committed_sequence": self.committed_sequence,
                "fault_tolerance": self.f,
                "total_nodes": self.n,
                "last_heartbeat": self.last_heartbeat
            }
    
    def shutdown(self):
        """Shutdown consensus mechanism"""
        with self.lock:
            self._shutting_down = True
            if self.view_change_timer:
                try:
                    self.view_change_timer.cancel()
                finally:
                    self.view_change_timer = None
    
    def _init_error_mitigation(self):
        """Initialize error mitigation components"""
        try:
            # Extract consensus config
            consensus_config = self.error_config.get("consensus", {}).get("bft", {})
            
            # Initialize consensus validator
            validator_config = {
                "f": self.f,
                "auto_scale_threshold": consensus_config.get("node_validation", {}).get("auto_scale_threshold", 0.8)
            }
            self.consensus_validator = ConsensusValidator(validator_config)
            
            # Initialize error classifier with config
            self.error_classifier = ErrorClassifier(self.error_config)
            
            # Extract configuration settings
            self.verification_strictness = consensus_config.get("signature", {}).get("verification_strictness", "high")
            self.auto_recovery_enabled = self.error_config.get("recovery", {}).get("auto_recovery", {}).get("enabled", False)
            
        except Exception as e:
            print(f"Warning: Error mitigation initialization failed: {e}")
    
    def _validate_bft_requirements(self):
        """Validate BFT requirements using error mitigation"""
        if self.consensus_validator:
            try:
                # Validate node count
                self.consensus_validator.validate_node_count(self.all_nodes)
            except Exception as e:
                print(f"Warning: BFT validation failed: {e}")


# Factory function for easy setup
def create_bft_network(node_configs: List[Dict[str, Any]], fault_tolerance: int = 1) -> Dict[str, BFTConsensus]:
    """
    Create a BFT consensus network
    
    Args:
        node_configs: List of node configurations
        fault_tolerance: Number of Byzantine faults to tolerate
    
    Returns:
        Dict mapping node IDs to BFTConsensus instances
    """
    all_node_ids = [config["node_id"] for config in node_configs]
    consensus_nodes = {}
    
    # Validate configuration
    if len(all_node_ids) < 3 * fault_tolerance + 1:
        raise ConsensusError(
            f"BFT requires at least {3*fault_tolerance+1} nodes to tolerate {fault_tolerance} faults"
        )
    
    # Create keypairs for each node (for testing/demo purposes)
    # In production, keys would be loaded from secure storage
    keypairs = {nid: KeyPair() for nid in all_node_ids}
    public_keys = {nid: kp.public_key for nid, kp in keypairs.items()}
    
    # Create consensus instances
    for config in node_configs:
        node_id = config["node_id"]
        consensus = BFTConsensus(
            node_id=node_id, 
            all_nodes=all_node_ids, 
            f=fault_tolerance,
            keypair=keypairs[node_id],
            node_public_keys=public_keys
        )
        consensus_nodes[node_id] = consensus
    
    return consensus_nodes