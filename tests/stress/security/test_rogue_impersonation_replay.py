import os
import time
import logging
from typing import Any

import pytest
import requests

from tests.stress.real_stress_client import (
    RealStressClient,
    generate_event,
    REAL_REQUESTS,
)


logger = logging.getLogger(__name__)

# Marks and skips
pytestmark = [
    pytest.mark.skipif(
        not REAL_REQUESTS, reason="Security phase requires REAL_REQUESTS=true"
    ),
    pytest.mark.stress,
    pytest.mark.security,
    pytest.mark.advanced,
]


ROGUE_NODE_TARGET = os.getenv("ROGUE_NODE_TARGET", "rogue-node:2661")
ROGUE_CHAIN = os.getenv("ROGUE_CHAIN_NAME_ADV", "rogue_node_advanced_security_test")
LEGITIMATE_NODES = ["node1", "node2", "node3", "node4"]


def _url(target: str) -> str:
    if target.startswith("http://") or target.startswith("https://"):
        return target
    return f"http://{target}"


def _safe_get(d: dict[str, Any], key: str, default: Any = None) -> Any:
    try:
        v = d.get(key, default)
    except Exception:
        return default
    return v


class TestAdvancedRogueAdversary:
    def setup_method(self) -> None:
        self.client = RealStressClient()
        # Require 4 healthy nodes, otherwise skip this security phase
        if not self.client.wait_for_nodes(timeout=30, min_healthy=4):
            pytest.skip("Not enough healthy nodes (need 4) for advanced rogue phase")

        self.rogue_url = _url(ROGUE_NODE_TARGET)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "HieraChain-SecurityTest/1.0",
                "Content-Type": "application/json",
            }
        )

    # ---------- Helpers ----------
    def _healthy_legitimate_nodes(self) -> list[str]:
        self.client.check_all_nodes()
        return [
            nid
            for nid, status in self.client.node_status.items()
            if nid in LEGITIMATE_NODES and status.is_healthy
        ]

    def _create_legitimate_chain(self) -> str:
        legit_nodes = self._healthy_legitimate_nodes()
        if not legit_nodes:
            pytest.skip("No healthy legitimate node available to create chain")

        node_id = legit_nodes[0]
        url = f"{self.client.node_status[node_id].url}/api/ledger/chains/{ROGUE_CHAIN}/create"
        payload = {
            "chain_type": "generic",
            "participants": LEGITIMATE_NODES,
        }
        resp = self.session.post(url, json=payload, timeout=15)
        assert resp.status_code in (200, 201, 409), (
            f"Unexpected status from chain create: {resp.status_code} {resp.text}"
        )
        return node_id

    def _get_total_events(self, node_id: str) -> int:
        stats_url = f"{self.client.node_status[node_id].url}/api/ledger/chains/{ROGUE_CHAIN}/stats"
        resp = self.session.get(stats_url, timeout=10)
        assert resp.status_code == 200, (
            f"Failed to fetch chain stats: HTTP {resp.status_code} {resp.text}"
        )
        data = resp.json() if resp.content else {}
        total_events = _safe_get(data, "total_events", 0)
        return int(total_events) if isinstance(total_events, int) else 0

    # ---------- Tests ----------
    def test_impersonating_rogue_cannot_submit_to_legitimate_chain(self) -> None:
        # Only run when impersonation mode is explicitly enabled in the runner
        if not os.getenv("ROGUE_IMPERSONATE_NODE_ID"):
            pytest.skip("Impersonation mode is disabled — set ROGUE_IMPERSONATE_NODE_ID to enable")

        node_id = self._create_legitimate_chain()

        # Craft an event and try to submit via rogue-node which is impersonating
        ev = generate_event()
        ev["entity_id"] = f"impersonation-attempt-{int(time.time())}"
        if isinstance(ev.get("details"), dict):
            ev["details"]["source"] = "rogue-node-impersonating"

        resp = self.session.post(
            f"{self.rogue_url}/api/ledger/chains/{ROGUE_CHAIN}/events",
            json=ev,
            timeout=15,
        )
        assert resp.status_code not in (200, 201, 202), (
            "Impersonating rogue was able to submit to a legitimate chain — critical security gap"
        )

        # Sanity: legitimate nodes remain writable
        ok = self.client.submit_event(node_id, generate_event(), chain_name=ROGUE_CHAIN)
        assert ok, "Legitimate chain became unwritable after impersonation attempt"

    def test_replay_from_rogue_is_rejected_or_has_no_effect(self) -> None:
        node_id = self._create_legitimate_chain()

        # Capture events count BEFORE baseline submit
        before_events = self._get_total_events(node_id)

        # Submit 1 legitimate event to establish a baseline
        base_event = generate_event()
        base_event["entity_id"] = f"replay-baseline-{int(time.time())}"
        ok = self.client.submit_event(node_id, base_event, chain_name=ROGUE_CHAIN)
        assert ok, "Failed to submit baseline event from legitimate node"

        # Wait briefly until the baseline event is reflected in stats (up to ~10s)
        target_events = before_events + 1
        deadline = time.time() + 10.0
        baseline_events = before_events
        while time.time() < deadline:
            baseline_events = self._get_total_events(node_id)
            if baseline_events >= target_events:
                break
            time.sleep(0.2)
        assert (
            baseline_events >= target_events
        ), f"Baseline event not reflected in stats (got {baseline_events}, expected >= {target_events})"

        # Attempt to replay the EXACT SAME payload from the rogue-node
        # Expectation: request is denied (non-2xx) and chain event count does not increase because of rogue replay
        replay_resp = self.session.post(
            f"{self.rogue_url}/api/ledger/chains/{ROGUE_CHAIN}/events",
            json=base_event,
            timeout=15,
        )
        assert replay_resp.status_code not in (200, 201, 202), (
            "Rogue replay should not be accepted (must be denied)"
        )

        # Give the system a brief moment in case of async handling and re-check stats
        time.sleep(1.0)
        after_replay_events = self._get_total_events(node_id)
        assert (
            after_replay_events >= baseline_events
        ), "Total events unexpectedly decreased"
        assert (
            after_replay_events == baseline_events
        ), "Rogue replay appears to have changed event count on the legitimate chain"
