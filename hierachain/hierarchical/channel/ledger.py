"""
ChannelLedger — block storage and event journaling for channels.
"""

import logging
import time
from typing import Any

import pyarrow as pa

from hierachain.core.block import Block, table_to_list_of_dicts
from hierachain.core import schemas
from hierachain.hierarchical.channel.query import _filter_block_events

logger = logging.getLogger(__name__)


def _format_details(val: Any) -> dict[str, str]:
    if isinstance(val, dict):
        return {str(k): str(v) for k, v in val.items()}
    return {}


class ChannelLedger:
    def __init__(self):
        self.blocks: list[Block] = []
        self.current_block_events: list[dict[str, Any]] = []
        self.height = 0
        self.last_block_hash = "0"

    def add_event(self, event: dict[str, Any]) -> None:
        if not isinstance(event, dict):
            logger.warning("ChannelLedger: Rejected event - not a dict")
            return

        if "entity_id" not in event or not event.get("entity_id"):
            logger.warning("ChannelLedger: Rejected event - missing entity_id")
            return

        if "event" not in event or not event.get("event"):
            logger.warning("ChannelLedger: Rejected event - missing event type")
            return

        event["timestamp"] = event.get("timestamp", time.time())
        event["channel_event"] = True
        self.current_block_events.append(event)

    def _prepare_event_data(self) -> dict[str, list[Any]]:
        schema_names = schemas.get_event_schema().names
        arrays: dict[str, list[Any]] = {name: [] for name in schema_names}

        for event in self.current_block_events:
            for name in schema_names:
                val = event.get(name)
                if name == "details":
                    val = _format_details(val)
                arrays[name].append(val)
        return arrays

    def finalize_block(self) -> Block | None:
        if not self.current_block_events:
            return None

        arrays = self._prepare_event_data()
        table = pa.table(arrays, schema=schemas.get_event_schema())

        block = Block(
            index=self.height,
            events=table,
            timestamp=time.time(),
            previous_hash=self.last_block_hash,
        )
        block.calculate_hash()

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
