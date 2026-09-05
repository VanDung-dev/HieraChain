"""
BFT Message Dispatcher component.
"""

from typing import Any

from hierachain.consensus.bft.types import BFTMessage
from hierachain.consensus.bft.helpers import send_via_zmq, broadcast


class BFTMessageDispatcher:
    """Handles network transmission and broadcasting for BFT consensus"""

    def __init__(self, consensus: Any):
        self.consensus = consensus

    def direct_send(self, target_node: str, message: dict[str, Any]) -> None:
        """Directly send a message to a node using ZMQ."""
        send_via_zmq(self.consensus.zmq_node, target_node, message)

    def broadcast_msg(self, msg: BFTMessage) -> None:
        """Broadcast message with failure detection."""
        failed = broadcast(
            self.consensus.zmq_node,
            self.consensus.network_send_function,
            self.consensus.all_nodes,
            self.consensus.node_id,
            msg,
            self.consensus.log_node_behavior
        )
        if failed > self.consensus.f and self.consensus.auto_recovery_enabled:
            self.consensus.view_change_manager.initiate_view_change(self.consensus.view + 1)
