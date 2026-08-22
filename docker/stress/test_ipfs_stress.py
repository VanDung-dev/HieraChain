"""
IPFS Stress Tests.

Tests IPFS storage under load:
1. Pre-upload data to IPFS, submit events with CID references
2. Query blocks with resolve_cid=true
3. Measure throughput for IPFS-backed event flow

Requires running HieraChain nodes with IPFS enabled.
"""

import os
import time
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import pytest

from hierachain.api.storage.ipfs_client import IPFSClient, IPFSError

from docker.stress.real_stress_client import (
    RealStressClient,
    REAL_REQUESTS,
    DEFAULT_CHAIN_NAME,
)

IPFS_HOST = os.getenv("HRC_IPFS_HOST", "/ip4/127.0.0.1/tcp/5001")
IPFS_ENABLED = os.getenv("HRC_IPFS_ENABLED", "false").lower() == "true"
CHAIN_NAME = os.getenv("STRESS_CHAIN_NAME", DEFAULT_CHAIN_NAME)

pytestmark = [
    pytest.mark.skipif(
        not REAL_REQUESTS,
        reason="Real network tests disabled (set REAL_REQUESTS=true)",
    ),
    pytest.mark.stress,
]


def _check_ipfs() -> bool:
    if not IPFS_ENABLED:
        return False
    try:
        client = IPFSClient(ipfs_host=IPFS_HOST)
        client.get_daemon_version()
        client.close()
        return True
    except (IPFSError, Exception):
        return False


def _preload_ipfs_data(count: int) -> list[dict[str, Any]]:
    """Pre-load data to IPFS and return list of {cid, nonce, metadata} dicts."""
    client = IPFSClient(ipfs_host=IPFS_HOST, auto_pin=True)
    results = []
    try:
        for i in range(count):
            data = {
                "stress_id": i,
                "payload": "x" * random.randint(100, 500),
                "timestamp": time.time(),
            }
            metadata = {"stress_run": str(int(time.time()))}
            result = client.upload_json(data, encrypt=True, metadata=metadata)
            results.append({
                "cid": result["cid"],
                "nonce": result["nonce"],
                "metadata": metadata,
            })
    finally:
        client.close()
    return results


def _generate_ipfs_event(ipfs_ref: dict[str, Any]) -> dict[str, Any]:
    """Generate an event referencing IPFS data."""
    event_id = f"ipfs_stress_{int(time.time() * 1_000_000)}_{random.randint(0, 99999)}"
    return {
        "entity_id": f"ipfs_stress_entity_{event_id}",
        "event_type": "ipfs_stress_test",
        "details_cid": ipfs_ref["cid"],
        "details_nonce": ipfs_ref["nonce"],
        "details_metadata": ipfs_ref["metadata"],
    }


class TestIPFSStress:
    """Stress tests for IPFS-backed event workflow."""

    def _ensure_chain(self, client: RealStressClient) -> bool:
        healthy = [nid for nid, s in client.node_status.items() if s.is_healthy]
        if not healthy:
            return False
        node_id = healthy[0]
        resp = client.session.post(
            f"{client.node_status[node_id].url}/api/ledger/admin/chains/{CHAIN_NAME}/sub-chain",
            json={"domain": "stress_test"},
            timeout=10,
        )
        return resp.status_code in (200, 201, 409)

    def _register_entity(self, client: RealStressClient, entity_id: str) -> bool:
        healthy = [nid for nid, s in client.node_status.items() if s.is_healthy]
        if not healthy:
            return False
        node_id = healthy[0]
        resp = client.session.post(
            f"{client.node_status[node_id].url}/api/ledger/chains/{CHAIN_NAME}/entities/{entity_id}",
            json={"type": "stress_test"},
            timeout=10,
        )
        return resp.status_code in (200, 201, 409)

    def _submit_ipfs_event(
        self, node_url: str, entity_id: str, ipfs_ref: dict[str, Any], client: RealStressClient
    ) -> dict[str, Any]:
        event = _generate_ipfs_event(ipfs_ref)
        event["entity_id"] = entity_id
        resp = client.session.post(
            f"{node_url}/api/ledger/chains/{CHAIN_NAME}/events",
            json=event,
            timeout=30,
        )
        return {"status": resp.status_code, "body": resp.json() if resp.ok else resp.text}

    @pytest.mark.skipif(
        not _check_ipfs(),
        reason="IPFS daemon not available",
    )
    def test_ipfs_connectivity(self):
        """Verify IPFS daemon is reachable before stress tests."""
        client = IPFSClient(ipfs_host=IPFS_HOST)
        version = client.get_daemon_version()
        client.close()
        print(f"\nIPFS daemon: v{version['version']}")

    @pytest.mark.stress
    @pytest.mark.skipif(
        not _check_ipfs(),
        reason="IPFS daemon not available",
    )
    def test_ipfs_upload_stress(self):
        """Stress test IPFS upload throughput."""
        COUNT = 50
        client = IPFSClient(ipfs_host=IPFS_HOST, auto_pin=True)

        start = time.time()
        results = []
        for i in range(COUNT):
            data = {"index": i, "data": "y" * 1000}
            t0 = time.time()
            result = client.upload_json(data, encrypt=True)
            elapsed = time.time() - t0
            results.append(elapsed)

        total = time.time() - start
        avg = sum(results) / len(results)
        print(f"\nUploaded {COUNT} IPFS entries in {total:.2f}s")
        print(f"Avg upload time: {avg*1000:.2f}ms")
        print(f"Throughput: {COUNT/total:.1f} entries/sec")

        client.close()

    @pytest.mark.stress
    @pytest.mark.skipif(
        not (_check_ipfs() and RealStressClient().wait_for_nodes(timeout=10)),
        reason="Both IPFS and HieraChain API required",
    )
    def test_ipfs_event_stress(self):
        """Submit events with IPFS CIDs under load.

        Pre-loads data to IPFS, then submits events referencing CIDs.
        """
        # Pre-load IPFS data
        ipfs_refs = _preload_ipfs_data(20)
        print(f"\nPre-loaded {len(ipfs_refs)} entries to IPFS")

        # Stress client setup
        stress_client = RealStressClient()
        if not stress_client.wait_for_nodes(timeout=10):
            pytest.skip("No HieraChain nodes available")

        self._ensure_chain(stress_client)

        healthy = [nid for nid, s in stress_client.node_status.items() if s.is_healthy]
        if not healthy:
            pytest.skip("No healthy nodes")
        node_id = healthy[0]
        node_url = stress_client.node_status[node_id].url

        # Submit events
        success = 0
        fail = 0
        times = []
        entity_id = f"ipfs_stress_run_{int(time.time())}"
        self._register_entity(stress_client, entity_id)

        for i, ref in enumerate(ipfs_refs):
            t0 = time.time()
            result = self._submit_ipfs_event(node_url, entity_id, ref, stress_client)
            elapsed = time.time() - t0
            times.append(elapsed)
            if result["status"] in (200, 201):
                success += 1
            else:
                fail += 1

        avg = sum(times) / len(times) if times else 0
        print(f"\n=== IPFS Event Stress Results ===")
        print(f"Submitted: {len(ipfs_refs)}")
        print(f"Success: {success}")
        print(f"Failed: {fail}")
        print(f"Avg response: {avg*1000:.2f}ms")
        success_rate = success / len(ipfs_refs) if ipfs_refs else 0
        print(f"Success rate: {success_rate*100:.1f}%")
        assert success_rate >= 0.8, f"Success rate too low: {success_rate*100:.1f}%"

    @pytest.mark.stress
    @pytest.mark.skipif(
        not (_check_ipfs() and RealStressClient().wait_for_nodes(timeout=10)),
        reason="Both IPFS and HieraChain API required",
    )
    def test_ipfs_resolve_stress(self):
        """Query blocks with resolve_cid=true under load.

        Submits events with IPFS CIDs, then queries blocks
        with resolve_cid=true to measure resolution throughput.
        """
        # Pre-load IPFS data and submit events
        ipfs_refs = _preload_ipfs_data(10)
        print(f"\nPre-loaded {len(ipfs_refs)} entries to IPFS")

        stress_client = RealStressClient()
        if not stress_client.wait_for_nodes(timeout=10):
            pytest.skip("No HieraChain nodes available")

        self._ensure_chain(stress_client)

        healthy = [nid for nid, s in stress_client.node_status.items() if s.is_healthy]
        if not healthy:
            pytest.skip("No healthy nodes")
        node_id = healthy[0]
        node_url = stress_client.node_status[node_id].url

        # Submit events
        entity_id = f"ipfs_resolve_run_{int(time.time())}"
        self._register_entity(stress_client, entity_id)

        for ref in ipfs_refs:
            self._submit_ipfs_event(node_url, entity_id, ref, stress_client)

        time.sleep(3)

        # Query with resolution
        resolve_start = time.time()
        resp = stress_client.session.get(
            f"{node_url}/api/ledger/chains/{CHAIN_NAME}/blocks?limit=10&resolve_cid=true",
            timeout=30,
        )
        resolve_time = time.time() - resolve_start

        assert resp.status_code == 200
        data = resp.json()
        blocks = data.get("blocks", []) if isinstance(data, dict) else data
        event_count = sum(len(b.get("events", [])) for b in blocks)

        print(f"\n=== IPFS Resolve Stress Results ===")
        print(f"Blocks retrieved: {len(blocks)}")
        print(f"Events found: {event_count}")
        print(f"Resolve query time: {resolve_time*1000:.2f}ms")
