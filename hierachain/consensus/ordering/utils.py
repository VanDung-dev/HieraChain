"""
Ordering storage handler for the HieraChain ordering service.
"""

import time
import hashlib
import logging
import os
import struct
from typing import Any
from queue import Queue
import orjson

from hierachain.consensus.ordering.types import PendingEvent

logger = logging.getLogger(__name__)


def make_serializable(obj: Any) -> Any:
    """Recursively make object JSON serializable"""
    if isinstance(obj, bytes):
        return obj.hex()
    if isinstance(obj, dict):
        return {k: make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [make_serializable(v) for v in obj]
    # Basic JSON types
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    # Fallback
    return str(obj)


def _orjson_default(obj: Any) -> Any:
    if isinstance(obj, bytes):
        return obj.hex()
    return str(obj)


def generate_event_id(event_data: dict[str, Any], channel_id: str) -> str:
    """Generate unique event ID"""
    json_bytes = orjson.dumps(event_data, default=_orjson_default)
    h = hashlib.sha256()
    h.update(channel_id.encode('utf-8'))
    h.update(json_bytes)
    h.update(struct.pack("<d", time.time()))
    return h.hexdigest()[:16]


def verify_event_signature(event: PendingEvent, certification: dict[str, Any]) -> None:
    """Verify event signature if sender and signature are provided."""
    if getattr(event, 'signature_verified', False):
        return

    signature = event.event_data.get("signature")
    sender = event.event_data.get("sender")

    if isinstance(signature, str) and isinstance(sender, str):
        details = event.event_data.get("details", {})
        payload = details.get("payload") if isinstance(details, dict) else None

        # Skip verification if no string payload to verify against
        if not isinstance(payload, str):
            return

        from hierachain.security.security_utils import verify_signature
        if not verify_signature(sender, payload.encode('utf-8'), signature):
            certification["valid"] = False
            certification["validation_errors"].append("Invalid signature")


def dump_forensic_data(
    pending_events: dict[str, PendingEvent], event_pool: Queue
) -> None:
    """Dump event pool summary for forensic analysis."""
    try:
        from hierachain.core.parquet_log import write_parquet_log
        sample_ids = list(pending_events.keys())[:100]
        dump_data = {
            "timestamp": time.time(),
            "total_pending": len(pending_events),
            "event_pool_size": event_pool.qsize(),
            "sample_event_ids": sample_ids
        }
        write_parquet_log("log/quarantine_dump.parquet", dump_data)
        logger.info("Forensic data dumped to %s", "log/quarantine_dump.parquet")
    except Exception as e:
        logger.error("Failed to dump forensic data: %s", e)
