"""
View change and timer logic for BFT consensus.
"""

import logging
import threading
from typing import Any, Callable
from hierachain.hierarchical.consensus.bft.types import BFTMessage, MessageType

logger = logging.getLogger(__name__)

def _reconstruct_bft_message(msg_dict: dict[str, Any]) -> BFTMessage:
    """Reconstruct BFTMessage object from dictionary representation."""
    return BFTMessage(
        message_type=MessageType(msg_dict.get("message_type")),
        view=msg_dict.get("view", 0),
        sequence_number=msg_dict.get("sequence_number", 0),
        sender_id=msg_dict.get("sender_id", ""),
        timestamp=msg_dict.get("timestamp", 0.0),
        signature=msg_dict.get("signature", ""),
        data=msg_dict.get("data", {}),
        nonce=msg_dict.get("nonce", "")
    )

def _is_msg_metadata_valid(
    msg_dict: dict[str, Any],
    view: int,
    node_public_keys: dict[str, str]
) -> bool:
    """Check if message metadata is basic valid for the current view and proof."""
    sender_id = msg_dict.get("sender_id")
    if not sender_id or sender_id not in node_public_keys:
        return False
    if msg_dict.get("view") != view or msg_dict.get("message_type") != MessageType.VIEW_CHANGE.value:
        return False
    return True


def _validate_single_msg(
    msg_dict: dict[str, Any],
    view: int,
    node_public_keys: dict[str, str],
    verify_sig_func: Callable
) -> str | None:
    """Validate a single message and return sender_id if valid."""
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
    proof: list[dict[str, Any]],
    view: int,
    quorum: int,
    node_public_keys: dict[str, str],
    verify_sig_func: Callable
) -> set[str]:
    """Collect up to quorum unique valid senders from the proof."""
    valid_senders = set()
    for msg_dict in proof:
        if len(valid_senders) >= quorum:
            break
            
        sender_id = _validate_single_msg(msg_dict, view, node_public_keys, verify_sig_func)
        if sender_id:
            valid_senders.add(sender_id)
            
    return valid_senders

def validate_view_change_proof(
    view: int,
    proof: list[dict[str, Any]],
    f: int,
    node_public_keys: dict[str, str],
    verify_sig_func: Callable
) -> bool:
    """
    Validate that the proof contains 2f+1 valid signatures for the view.
    Decomposed to achieve minimal cyclomatic complexity.
    """
    quorum = 2 * f + 1
    if len(proof) < quorum:
        return False
        
    valid_senders = _collect_valid_senders(proof, view, quorum, node_public_keys, verify_sig_func)
    
    return len(valid_senders) >= quorum

def start_view_change_timer(timeout: float, handler: Callable) -> threading.Timer:
    """Start view change timer"""
    timer = threading.Timer(timeout, handler)
    timer.daemon = True
    timer.start()
    return timer
