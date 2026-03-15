"""
Network and communication logic for BFT consensus.
"""

import logging
import asyncio
from typing import Any, Callable
from hierachain.consensus.bft.types import BFTMessage

logger = logging.getLogger(__name__)

def send_via_zmq(zmq_node: Any, target_id: str, message: dict[str, Any]):
    """Send message using ZeroMQ transport (sync wrapper for async)."""
    if zmq_node:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(zmq_node.send_direct(target_id, message))
            else:
                loop.run_until_complete(zmq_node.send_direct(target_id, message))
        except RuntimeError:
            asyncio.run(zmq_node.send_direct(target_id, message))
    else:
        logger.warning("No ZMQ node configured for direct send")

def _broadcast_via_zmq(zmq_node: Any, msg_dict: dict[str, Any]):
    """Internal helper to handle ZMQ broadcast with async/sync detection."""
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
    send_func: Callable,
    node_id: str,
    msg_dict: dict[str, Any],
    log_behavior_func: Callable
) -> int:
    """Send message to a single node and return 1 if failed, 0 otherwise."""
    try:
        send_func(node_id, msg_dict)
        return 0
    except Exception as e:
        logger.error("Error sending to %s: %s", node_id, e)
        log_behavior_func(node_id, "network_send_failure")
        return 1

def _broadcast_manually(
    send_func: Callable,
    all_nodes: list[str],
    current_node_id: str,
    msg_dict: dict[str, Any],
    log_behavior_func: Callable
) -> int:
    """Iterate through nodes and send message manually."""
    failed_sends = 0
    for node_id in all_nodes:
        if node_id != current_node_id:
            failed_sends += _send_node_message(
                send_func, node_id, msg_dict, log_behavior_func
            )
    return failed_sends

def broadcast(
    zmq_node: Any,
    network_send_function: Callable | None,
    all_nodes: list[str],
    current_node_id: str,
    message: BFTMessage,
    log_behavior_func: Callable
) -> int:
    """Broadcast message to all other nodes with error handling"""
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
    primary_id: str,
    current_node_id: str,
    operation: dict[str, Any]
):
    """Forward request to primary node"""
    if network_send_function and primary_id != current_node_id:
        try:
            network_send_function(primary_id, {
                "type": "client_request",
                "operation": operation
            })
        except Exception as e:
            logger.error(f"Error forwarding to primary {primary_id}: {e}")
