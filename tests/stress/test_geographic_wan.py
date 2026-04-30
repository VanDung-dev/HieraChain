"""
Geographic WAN Simulation Stress Test.
Measures HieraChain throughput and consensus stability under simulated global distance.
"""

import pytest
import time
import subprocess
import logging
from tests.stress.real_stress_client import run_real_stress_test, RealStressClient, generate_event

logger = logging.getLogger(__name__)

def apply_chaos(latency=150, loss=1):
    """Apply network chaos to all nodes."""
    subprocess.run(
        ["python3", "scripts/chaos_controller.py", "apply", "--latency", str(latency), "--loss", str(loss)],
        check=True
    )

def reset_chaos():
    """Reset network to normal."""
    subprocess.run(["python3", "scripts/chaos_controller.py", "reset"], check=True)

@pytest.fixture(autouse=True)
def network_cleanup():
    """Ensure network is reset before and after each test."""
    reset_chaos()
    yield
    reset_chaos()

class TestGeographicWAN:
    @pytest.mark.stress
    def test_wan_impact_benchmark(self):
        """Compare performance: Local Network vs. Simulated WAN."""
        
        # 1. Baseline (Local Network)
        print("\n--- 🟢 STEP 1: Baseline Performance (Local) ---")
        baseline = run_real_stress_test(duration=15, events_per_second=50, workers=5)
        baseline_tps = baseline.successful_requests / 15
        print(f"  Baseline Throughput: {baseline_tps:.2f} events/sec")
        
        # 2. Apply WAN Chaos (150ms Latency - e.g. VN to USA)
        print("\n--- 🟠 STEP 2: Applying WAN Simulation (150ms latency, 1% loss) ---")
        apply_chaos(latency=150, loss=1)
        time.sleep(5) # Let network stabilize
        
        # 3. Measured Performance (WAN)
        print("\n--- 🔵 STEP 3: WAN Performance Under Distance ---")
        # We expect a drop in throughput due to BFT consensus waiting for multiple round-trips
        wan_test = run_real_stress_test(duration=15, events_per_second=50, workers=5)
        wan_tps = wan_test.successful_requests / 15
        print(f"  WAN Throughput: {wan_tps:.2f} events/sec")
        
        impact = ((baseline_tps - wan_tps) / baseline_tps) * 100
        print(f"\n📈 WAN IMPACT ANALYSIS:")
        print(f"  Throughput Drop: {impact:.1f}%")
        
        # In BFT, we expect some drop but the system MUST remain stable (no 0 success)
        assert wan_test.successful_requests > 0, "System collapsed under WAN latency!"
        assert impact < 90, "Performance drop too severe (>90%)"

    @pytest.mark.stress
    def test_consensus_resilience_high_latency(self):
        """Verify if BFT consensus can still commit blocks under extreme latency (250ms)."""
        print("\n--- 🔴 STEP 4: Extreme Latency Test (250ms) ---")
        apply_chaos(latency=250, loss=2)
        print("  Waiting 10s for BFT consensus to stabilize...")
        time.sleep(10)
        
        # Increase client timeout for extreme conditions
        client = RealStressClient(timeout=15.0)
        is_ready = client.wait_for_nodes(timeout=60, min_healthy=1) # At least 1 node for diagnosis
        
        healthy_nodes = [nid for nid, s in client.node_status.items() if s.is_healthy]
        
        print(f"\n🔍 POST-CHAOS CLUSTER STATUS:")
        for nid, s in client.node_status.items():
            status_str = "✅ HEALTHY" if s.is_healthy else "❌ UNHEALTHY"
            print(f"  - {nid}: {status_str} ({s.url})")

        if not is_ready:
            pytest.fail("Nodes became unreachable under high latency")
            
        success = 0
        target_node = healthy_nodes[0]
        print(f"  Attempting manual submission to: {target_node}")
        
        for i in range(10):
            if client.submit_event(target_node, generate_event()):
                success += 1
            time.sleep(1) # Slow submission for slow network
            
        print(f"  Extreme Latency Success: {success}/10 events committed")
        assert success > 0, "Consensus failed under extreme latency"
