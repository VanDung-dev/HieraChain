"""
Ordering storage handler for the HieraChain ordering service.
"""

import time
import hashlib
import json
import logging
import os
from typing import Any
from queue import Queue
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

def generate_event_id(event_data: dict[str, Any], channel_id: str) -> str:
    """Generate unique event ID"""
    clean_data = make_serializable(event_data)
    json_str = json.dumps(clean_data, sort_keys=True, separators=(',', ':'))
    data = f"{channel_id}:{json_str}:{time.time()}"
    return hashlib.sha256(data.encode()).hexdigest()[:16]

def verify_event_signature(event: PendingEvent, certification: dict[str, Any]) -> None:
    """Verify event signature if sender and signature are provided."""
    signature = event.event_data.get("signature")
    sender = event.event_data.get("sender")

    if signature and sender:
        details = event.event_data.get("details", {})
        payload = details.get("payload", "") if isinstance(details, dict) else ""

        from hierachain.security.security_utils import verify_signature
        if not verify_signature(sender, payload.encode('utf-8'), signature):
            certification["valid"] = False
            certification["validation_errors"].append("Invalid signature")

def dump_forensic_data(pending_events: dict[str, PendingEvent], event_pool: Queue) -> None:
    """Dump event pool summary for forensic analysis."""
    try:
        os.makedirs("log", exist_ok=True)
        dump_path = "log/quarantine_dump.json"

        # Collect sample of pending events (max 100)
        sample_ids = list(pending_events.keys())[:100]
        dump_data = {
            "timestamp": time.time(),
            "total_pending": len(pending_events),
            "event_pool_size": event_pool.qsize(),
            "sample_event_ids": sample_ids
        }

        with open(dump_path, "w") as f:
            json.dump(dump_data, f, indent=2)

        logger.info(f"Forensic data dumped to {dump_path}")
    except Exception as e:
        logger.error(f"Failed to dump forensic data: {e}")
