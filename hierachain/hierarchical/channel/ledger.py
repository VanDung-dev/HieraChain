"""
ChannelLedger — block storage and event journaling for channels.
"""

import logging
import time
from typing import Any

from hierachain.core.block import Block, convert_events_to_arrow
from hierachain.hierarchical.channel.query import _filter_block_events
from hierachain.security.identity_loader import NodeIdentity, require_block_identity
from hierachain.security.verify.block_verifier import get_block_verifier, sign_block

logger = logging.getLogger(__name__)


class ChannelLedger:
    def __init__(
        self,
        node_identity: NodeIdentity | None = None,
        trusted_public_keys: dict[str, bytes] | None = None,
    ) -> None:
        self.node_identity, self.trusted_public_keys = require_block_identity(
            node_identity, trusted_public_keys
        )
        self.blocks: list[Block] = []
        self.current_block_events: list[dict[str, Any]] = []
        self.height = 0
        self.last_block_hash = "0"

    def add_event(self, event: dict[str, Any]) -> bool:
        if not isinstance(event, dict):
            logger.warning("ChannelLedger: Rejected event - not a dict")
            return False

        if "entity_id" not in event or not event.get("entity_id"):
            logger.warning("ChannelLedger: Rejected event - missing entity_id")
            return False

        if "event" not in event or not event.get("event"):
            logger.warning("ChannelLedger: Rejected event - missing event type")
            return False

        event["timestamp"] = event.get("timestamp", time.time())
        event["channel_event"] = True
        self.current_block_events.append(event)
        return True

    def finalize_block(self) -> Block | None:
        if not self.current_block_events:
            return None

        table = convert_events_to_arrow(self.current_block_events)

        block = Block(
            index=self.height,
            events=table,
            timestamp=time.time(),
            previous_hash=self.last_block_hash,
        )
        sign_block(
            block, self.node_identity.node_id, self.node_identity.signing_keypair
        )
        public_key = self.trusted_public_keys[self.node_identity.node_id]
        if not get_block_verifier().verify_block(block, public_key=public_key).is_valid:
            raise ValueError("Channel block signature verification failed")

        self.blocks.append(block)
        self.height += 1
        self.last_block_hash = block.hash
        self.current_block_events.clear()

        return block

    def get_events_by_filter(
        self, filter_func, filter_expr: Any | None = None
    ) -> list[dict[str, Any]]:
        events = []
        for block in self.blocks:
            events.extend(_filter_block_events(block, filter_func, filter_expr))
        return events
