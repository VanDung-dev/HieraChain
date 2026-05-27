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
]


ROGUE_NODE_TARGET = os.getenv("ROGUE_NODE_TARGET", "rogue-node:2661")
ROGUE_CHAIN = os.getenv("ROGUE_CHAIN_NAME", "rogue_node_security_test")
LEGITIMATE_NODES = ["node1", "node2", "node3", "node4"]


def _url(target: str) -> str:
    if target.startswith("http://") or target.startswith("https://"):
        return target
    return f"http://{target}"


def _parse_chain_list(data: Any) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        chains = data.get("chains", data.get("data", []))
        return chains if isinstance(chains, list) else []
    return []


def _chain_names(data: Any) -> set[str]:
    chains = _parse_chain_list(data)
    names: set[str] = set()
    for c in chains:
        if isinstance(c, str):
            names.add(c)
        elif isinstance(c, dict):
            name = c.get("name") or c.get("chain_name") or c.get("id")
            if isinstance(name, str):
                names.add(name)
    return names


class TestRogueNodeFinalPhase:
    def setup_method(self):
        self.client = RealStressClient()
        # Require 4 healthy nodes, otherwise skip this security phase
        if not self.client.wait_for_nodes(timeout=30, min_healthy=4):
            pytest.skip("Not enough healthy nodes (need 4) for rogue-node phase")

        self.rogue_url = _url(ROGUE_NODE_TARGET)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "HieraChain-SecurityTest/1.0",
                "Content-Type": "application/json",
            }
        )

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
        url = f"{self.client.node_status[node_id].url}/api/v1/chains/{ROGUE_CHAIN}/create"
        payload = {
            "chain_type": "generic",
            "participants": LEGITIMATE_NODES,
        }
        resp = self.session.post(url, json=payload, timeout=15)
        assert resp.status_code in (200, 201, 409), (
            f"Unexpected status from chain create: {resp.status_code} {resp.text}"
        )
        return node_id

    def test_rogue_node_is_reachable_but_not_part_of_target_nodes(self):
        resp = self.session.get(f"{self.rogue_url}/api/v1/health", timeout=10)
        assert resp.status_code == 200
        target_env = os.getenv("TARGET_NODES", "")
        assert "rogue-node" not in target_env
        assert "node5" not in target_env

    def test_legitimate_cluster_still_has_four_healthy_nodes_after_rogue_start(self):
        self.client.check_all_nodes()
        healthy_legit = self._healthy_legitimate_nodes()
        assert len(healthy_legit) == 4, f"Expected 4 healthy nodes, got {len(healthy_legit)}"

    def test_rogue_node_does_not_receive_legitimate_chain_by_default(self):
        self._create_legitimate_chain()
        time.sleep(3)

        try:
            resp = self.session.get(f"{self.rogue_url}/api/v1/chains", timeout=10)
        except requests.RequestException as e:
            pytest.skip(f"Rogue node API unreachable: {e}")

        if resp.status_code in (401, 403, 404):
            return  # pass
        if resp.status_code == 200:
            rogue_data = resp.json() if resp.content else {}
            rogue_chain_names = _chain_names(rogue_data)
            assert ROGUE_CHAIN not in rogue_chain_names, (
                f"Rogue node unexpectedly has chain '{ROGUE_CHAIN}'"
            )
            return
        pytest.fail(f"Unexpected status from rogue /chains: {resp.status_code} {resp.text}")

    def test_rogue_node_cannot_submit_to_legitimate_chain_as_trusted_participant(self):
        self._create_legitimate_chain()
        ev = generate_event()
        ev["entity_id"] = f"rogue-submit-{int(time.time())}"
        if isinstance(ev.get("details"), dict):
            ev["details"]["source"] = "rogue-node"

        resp = self.session.post(
            f"{self.rogue_url}/api/v1/chains/{ROGUE_CHAIN}/events",
            json=ev,
            timeout=15,
        )
        assert resp.status_code not in (200, 201, 202), (
            "Rogue node was able to submit to a legitimate chain — security gap"
        )

    def test_rogue_node_does_not_change_legitimate_chain_writability(self):
        node_id = self._create_legitimate_chain()
        successes = 0
        for _ in range(10):
            if self.client.submit_event(node_id, generate_event(), chain_name=ROGUE_CHAIN):
                successes += 1
        assert successes > 0, "Legitimate chain became unwritable after rogue start"

    def test_gateway_diagnostic_does_not_expose_rogue_or_internal_services(self):
        gateway_targets = ["gateway:80", "10.0.0.5:80"]
        dangerous_targets = ["rogue-node", "node5", "redis", "ipfs-node1", "127.0.0.1"]
        explorer_token = os.getenv("EXPLORER_TOKEN", "default_token")

        any_gateway_up = False
        for gw in gateway_targets:
            gw_url = _url(gw)
            try:
                h = self.session.get(f"{gw_url}/gateway-health", timeout=5)
            except requests.RequestException:
                continue
            if h.status_code != 200:
                continue
            any_gateway_up = True
            for target in dangerous_targets:
                diag = self.session.get(
                    f"{gw_url}/{explorer_token}/diag/{target}", timeout=8
                )
                assert diag.status_code in (400, 401, 403, 404), (
                    f"Gateway exposed internal/rogue target '{target}' with status {diag.status_code}"
                )

        if not any_gateway_up:
            pytest.skip("No reachable gateway for diagnostic test")
