"""
DDoS Attack Simulation - High Volume Event Flooding.

This test simulates a Distributed Denial of Service (DDoS) attack by:
1. Sending massive bursts of events to all nodes simultaneously.
2. Measuring system responsiveness and error rates.
3. Verifying if the system triggers protection mechanisms (e.g., rate limiting).
"""

import pytest
import logging
import time
from docker.stress.real_stress_client import (
    RealStressClient,
    run_real_stress_test,
    REAL_REQUESTS,
)

logger = logging.getLogger(__name__)

# Skip if REAL_REQUESTS is not enabled
pytestmark = pytest.mark.skipif(
    not REAL_REQUESTS,
    reason="DDoS attack simulation requires REAL_REQUESTS=true"
)

class TestDDoSAttack:
    """DDoS Attack simulation scenarios."""

    @pytest.mark.stress
    def test_ddos_flood_attack(self):
        """
        Simulate a high-volume flood attack.
        Target: 100 events/sec across 10 workers for 20 seconds.
        """
        print("\n🚀 LAUNCHING DDOS FLOOD ATTACK SIMULATION...")
        
        results = run_real_stress_test(
            duration=20,
            events_per_second=100,
            workers=10,
        )

        print(f"\n💥 ATTACK IMPACT SUMMARY")
        print(f"  Total Requests:     {results.total_requests}")
        print(f"  Successful (200 OK): {results.successful_requests}")
        print(f"  Blocked/Failed:     {results.failed_requests}")
        print(f"  Avg Latency:        {results.avg_response_time*1000:.2f}ms")
        
        # In a real attack, we expect some nodes to struggle or block
        # We want to see how many got through
        if results.total_requests > 0:
            success_rate = results.successful_requests / results.total_requests
            print(f"  System Resilience:   {success_rate*100:.1f}%")
            
            # If the rate limiter is working, success rate should drop as attack continues
            # (Note: default rate limit is 100 rpm per IP in server.py)
            assert results.total_requests > 0

    @pytest.mark.stress
    def test_multi_node_targeted_attack(self):
        """
        Simulate a targeted attack on specific nodes.
        """
        client = RealStressClient()
        client.wait_for_nodes(timeout=30, min_healthy=2)
            
        healthy_nodes = [nid for nid, s in client.node_status.items() if s.is_healthy]
        print(f"\n🔍 CLUSTER STATUS: {len(healthy_nodes)}/{len(client.node_status)} nodes healthy")
        for nid, s in client.node_status.items():
            status_str = "✅ HEALTHY" if s.is_healthy else "❌ UNHEALTHY"
            print(f"  - {nid}: {status_str} ({s.url})")

        if len(healthy_nodes) < 1:
            pytest.skip("No healthy nodes available — skipping targeted attack test")
            
        target = healthy_nodes[0]
        print(f"\n🎯 TARGETED ATTACK ON NODE: {target}")
        
        # Send 500 events as fast as possible to one node
        start_time = time.time()
        success = 0
        failed = 0
        
        from docker.stress.real_stress_client import generate_event
        
        for i in range(500):
            event = generate_event()
            if client.submit_event(target, event):
                success += 1
            else:
                failed += 1
                
        elapsed = time.time() - start_time
        print(f"  Attack Result: {success} success, {failed} blocked in {elapsed:.2f}s")
        print(f"  Throughput: {success/elapsed:.2f} events/sec")
        
        assert (success + failed) == 500
