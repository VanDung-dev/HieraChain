"""
BFT consensus helpers — cryptographic, network, view-change, and
consensus-phase logic extracted to reduce class complexity.
"""

import time
import hashlib
import logging
import asyncio
import threading
from typing import Any, Callable

from hierachain.config.settings import settings
from hierachain.security.security_utils import verify_signature
from hierachain.security.verify.zk_verifier import ZKVerifier
from hierachain.error_mitigation.validator import ConsensusValidator
from hierachain.error_mitigation.error_classifier import ErrorClassifier
from hierachain.consensus.bft.types import BFTMessage, MessageType, ConsensusState

logger = logging.getLogger(__name__)


# --- Cryptographic helpers ---
def sign_message(key_provider: Any, data: bytes) -> str:
    if not key_provider:
        return ""
    return key_provider.sign(data)

def verify_message_signature(
    message: BFTMessage, node_public_keys: dict[str, str]
) -> bool:
    if message.sender_id not in node_public_keys:
        logger.warning("No public key for node %s", message.sender_id)
        return False

    if abs(time.time() - message.timestamp) > 120.0:
        logger.warning(
            "BFTMessage timestamp drift too large: %.1fs",
            abs(time.time() - message.timestamp),
        )
        return False

    public_key = node_public_keys[message.sender_id]
    payload = message.get_signable_payload()
    try:
        return verify_signature(public_key, payload, message.signature)
    except Exception as e:
        logger.error("Signature verification error: %s", e)
        return False

def hash_request(request: dict[str, Any]) -> str:
    req_str = (
        f"{request.get('client_id')}:"
        f"{request.get('timestamp')}:"
        f"{request.get('operation')}"
    )
    return hashlib.sha256(req_str.encode()).hexdigest()

def verify_operation_zk_proof(data: dict[str, Any]) -> bool:
    operation = data.get("operation", {})
    zk_proof_hex = operation.get("zk_proof")

    if zk_proof_hex is None:
        return not settings.ZK_PROOF_REQUIRED_FOR_MAINCHAIN

    try:
        verifier = ZKVerifier(mode=settings.ZK_MODE)
        zk_proof = bytes.fromhex(zk_proof_hex)
        public_inputs = {
            "old_state_root": operation.get("previous_state", ""),
            "new_state_root": operation.get("current_state", ""),
            "block_index": operation.get("sequence", 0),
        }
        return verifier.verify(zk_proof, public_inputs)
    except Exception as e:
        logger.error("ZK verification error in BFT: %s", e)
        return False


# --- Network helpers ---

def send_via_zmq(zmq_node: Any, target_id: str, message: dict[str, Any]) -> None:
    if not zmq_node:
        logger.warning("No ZMQ node configured for direct send")
        return
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(zmq_node.send_direct(target_id, message))
        else:
            loop.run_until_complete(zmq_node.send_direct(target_id, message))
    except RuntimeError:
        asyncio.run(zmq_node.send_direct(target_id, message))

def _broadcast_via_zmq(zmq_node: Any, msg_dict: dict[str, Any]) -> None:
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(zmq_node.broadcast(msg_dict))
        else:
            loop.run_until_complete(zmq_node.broadcast(msg_dict))
    except RuntimeError:
        asyncio.run(zmq_node.broadcast(msg_dict))
    except Exception as e:
        logger.error("ZMQ Broadcast error: %s", e)

def _send_node_message(
    send_func: Callable, node_id: str, msg_dict: dict[str, Any],
    log_behavior_func: Callable,
) -> int:
    try:
        send_func(node_id, msg_dict)
        return 0
    except Exception as e:
        logger.error("Error sending to %s: %s", node_id, e)
        log_behavior_func(node_id, "network_send_failure")
        return 1

def _broadcast_manually(
    send_func: Callable, all_nodes: list[str], current_node_id: str,
    msg_dict: dict[str, Any], log_behavior_func: Callable,
) -> int:
    failed = 0
    for node_id in all_nodes:
        if node_id != current_node_id:
            failed += _send_node_message(send_func, node_id, msg_dict, log_behavior_func)
    return failed

def broadcast(
    zmq_node: Any, network_send_function: Callable | None,
    all_nodes: list[str], current_node_id: str, message: BFTMessage,
    log_behavior_func: Callable,
) -> int:
    msg_dict = message.to_dict()
    if zmq_node:
        _broadcast_via_zmq(zmq_node, msg_dict)
        return 0
    if network_send_function:
        return _broadcast_manually(
            network_send_function, all_nodes, current_node_id, msg_dict, log_behavior_func
        )
    return 0

def forward_to_primary(
    network_send_function: Callable | None,
    primary_id: str, current_node_id: str, operation: dict[str, Any],
) -> None:
    if network_send_function and primary_id != current_node_id:
        try:
            network_send_function(primary_id, {
                "type": "client_request",
                "operation": operation,
            })
        except Exception as e:
            logger.error("Error forwarding to primary %s: %s", primary_id, e)


# --- View-change helpers ---

def _reconstruct_bft_message(msg_dict: dict[str, Any]) -> BFTMessage:
    return BFTMessage(
        message_type=MessageType(msg_dict.get("message_type")),
        view=msg_dict.get("view", 0),
        sequence_number=msg_dict.get("sequence_number", 0),
        sender_id=msg_dict.get("sender_id", ""),
        timestamp=msg_dict.get("timestamp", 0.0),
        signature=msg_dict.get("signature", ""),
        data=msg_dict.get("data", {}),
        nonce=msg_dict.get("nonce", ""),
    )

def _is_msg_metadata_valid(
    msg_dict: dict[str, Any], view: int, node_public_keys: dict[str, str]
) -> bool:
    sender_id = msg_dict.get("sender_id")
    if not sender_id or sender_id not in node_public_keys:
        return False
    if msg_dict.get("view") != view or msg_dict.get("message_type") != MessageType.VIEW_CHANGE.value:
        return False
    return True

def _validate_single_msg(
    msg_dict: dict[str, Any], view: int, node_public_keys: dict[str, str],
    verify_sig_func: Callable,
) -> str | None:
    if not _is_msg_metadata_valid(msg_dict, view, node_public_keys):
        return None
    try:
        bft_msg = _reconstruct_bft_message(msg_dict)
        if verify_sig_func(bft_msg):
            return bft_msg.sender_id
    except Exception as e:
        logger.error("Error validating proof message: %s", e)
    return None

def _collect_valid_senders(
    proof: list[dict[str, Any]], view: int, quorum: int,
    node_public_keys: dict[str, str], verify_sig_func: Callable,
) -> set[str]:
    valid_senders: set[str] = set()
    for msg_dict in proof:
        if len(valid_senders) >= quorum:
            break
        sender_id = _validate_single_msg(msg_dict, view, node_public_keys, verify_sig_func)
        if sender_id:
            valid_senders.add(sender_id)
    return valid_senders

def validate_view_change_proof(
    view: int, proof: list[dict[str, Any]], f: int,
    node_public_keys: dict[str, str], verify_sig_func: Callable,
) -> bool:
    quorum = 2 * f + 1
    if len(proof) < quorum:
        return False
    valid_senders = _collect_valid_senders(proof, view, quorum, node_public_keys, verify_sig_func)
    return len(valid_senders) >= quorum

def start_view_change_timer(timeout: float, handler: Callable) -> threading.Timer:
    timer = threading.Timer(timeout, handler)
    timer.daemon = True
    timer.start()
    return timer


# --- Consensus-phase helpers ---

def _execute_consensus_operation(
    chain: Any, operation: dict[str, Any], seq: int, view: int
) -> None:
    try:
        event = {
            "entity_id": operation.get("entity_id"),
            "event": operation.get("event_type", "consensus_operation"),
            "timestamp": time.time(),
            "details": operation.get("details", {}),
            "consensus": {"sequence": seq, "view": view, "committed_at": time.time()},
        }
        if chain:
            chain.add_event(event)
    except Exception as e:
        logger.error("Error executing operation: %s", e)

def _log_behavior(
    error_classifier: Any, failure_counts: dict[str, int],
    max_failures: int, auto_recovery: bool, node_id: str,
    issue: str, view: int, seq: int,
    recovery_callback: Callable[[int], None],
) -> None:
    if not error_classifier:
        return
    error_classifier.classify_error({
        "error_type": f"node_{issue}",
        "message": f"Node {node_id} exhibited {issue}",
        "metadata": {
            "node_id": node_id, "issue": issue,
            "timestamp": time.time(), "view": view, "sequence": seq,
        },
    })
    failure_counts[node_id] = failure_counts.get(node_id, 0) + 1
    if failure_counts[node_id] >= max_failures and auto_recovery:
        recovery_callback(view + 1)

def _validate_consensus_message(
    message: BFTMessage, all_nodes: list[str],
    public_keys: dict[str, str], strictness: str, timeout: float,
    log_func: Callable[[str, str], None],
) -> bool:
    if message.sender_id not in all_nodes or message.view < 0 or message.sequence_number < 0:
        return False
    if not verify_message_signature(message, public_keys):
        log_func(message.sender_id, "signature_verification_failed")
        return False
    if (time.time() - message.timestamp) > timeout:
        log_func(message.sender_id, "slow_message")
    return True

def validate_consensus_message(
    message: BFTMessage, all_nodes: list[str],
    public_keys: dict[str, str], strictness: str, timeout: float,
    log_func: Callable[[str, str], None],
) -> bool:
    return _validate_consensus_message(message, all_nodes, public_keys, strictness, timeout, log_func)

def _cleanup_messages(
    pre_prep: dict[int, BFTMessage], prep: dict[int, list[BFTMessage]],
    commit: dict[int, list[BFTMessage]], committed_seq: int,
) -> None:
    threshold = committed_seq - 100
    for seq in list(pre_prep.keys()):
        if seq < threshold:
            pre_prep.pop(seq, None)
            prep.pop(seq, None)
            commit.pop(seq, None)

def _create_signed_bft_message(
    msg_type: MessageType, view: int, seq: int,
    node_id: str, key_provider: Any, data: dict[str, Any],
) -> BFTMessage:
    msg = BFTMessage(msg_type, view, seq, node_id, time.time(), "", data)
    if key_provider:
        msg.signature = sign_message(key_provider, msg.get_signable_payload())
    return msg

def _add_to_votes(votes: list[BFTMessage], message: BFTMessage) -> bool:
    if any(m.sender_id == message.sender_id for m in votes):
        return False
    votes.append(message)
    return True

def _validate_prepare_msg(
    message: BFTMessage, state: ConsensusState,
    pre_prep_messages: dict[int, BFTMessage],
    public_keys: dict[str, str], log_func: Callable[[str, str], None],
) -> bool:
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
    message: BFTMessage, pre_prep_messages: dict[int, BFTMessage],
    prep_messages: dict[int, list[BFTMessage]],
    public_keys: dict[str, str], log_func: Callable[[str, str], None],
) -> bool:
    seq = message.sequence_number
    if seq not in pre_prep_messages and seq not in prep_messages:
        return False
    if not verify_message_signature(message, public_keys):
        log_func(message.sender_id, "invalid_signature")
        return False
    return True

def _validate_pre_prep_basic(
    node_id: str, primary_id: str, view: int,
    committed_seq: int, message: BFTMessage, public_keys: dict[str, str],
) -> bool:
    if (
        node_id == primary_id
        or message.view != view
        or message.sequence_number <= committed_seq
        or message.sender_id != primary_id
    ):
        return False
    return verify_message_signature(message, public_keys)

def _process_prepare_quorum_logic(
    node_id: str, f: int, view: int, seq: int, digest: str | None,
    state: ConsensusState, prepare_count: int, key_provider: Any,
) -> tuple[ConsensusState, BFTMessage | None]:
    if prepare_count >= 2 * f and state == ConsensusState.PRE_PREPARED:
        msg = _create_signed_bft_message(
            MessageType.COMMIT, view, seq, node_id, key_provider, {"digest": digest}
        )
        return ConsensusState.PREPARED, msg
    return state, None

def _process_commit_quorum_logic(
    f: int, commit_msgs: list[BFTMessage],
    pre_prep_messages: dict[int, BFTMessage],
) -> tuple[bool, BFTMessage | None]:
    if len(commit_msgs) >= 2 * f + 1:
        for msg in commit_msgs:
            pre_prep = pre_prep_messages.get(msg.sequence_number)
            if pre_prep:
                return True, pre_prep
    return False, None

def _init_bft_mitigation_data(error_config: dict[str, Any]) -> dict[str, Any]:
    consensus_config = error_config.get("consensus", {}).get("bft", {})
    return {
        "validator": ConsensusValidator(consensus_config.get("node_validation", {})),
        "classifier": ErrorClassifier(error_config.get("classification", {})),
        "strictness": consensus_config.get("verification_strictness", "high"),
        "recovery": error_config.get("recovery", {}).get("auto_recovery", {}).get("enabled", False),
    }
