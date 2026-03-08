"""
Chaos Sync Test - Kill/Restart & State Integrity Test.

This test simulates node failures and restarts to test:
- State synchronization after node recovery
- Chain integrity during chaos
- Cluster resilience (resurrection)
- Data consistency across nodes

Run with: pytest tests/stress/test_chaos_sync.py -v
"""

import time
import random
import threading
import logging
from dataclasses import dataclass, field

import pytest

logger = logging.getLogger(__name__)

# Test configuration
DEFAULT_CONFIG = {
    "num_nodes": 4,
    "test_duration_seconds": 60,
    "events_per_second": 10,
    "kill_interval_seconds": 15,
    "restart_delay_seconds": 5,
    "target_nodes": ["localhost:5001", "localhost:5002", "localhost:5003", "localhost:5004"],
}


@dataclass
class NodeState:
    """Simulated node state."""
    node_id: str
    is_alive: bool = True
    block_index: int = 0
    block_hash: str = ""
    events_processed: int = 0
    restarts: int = 0
    last_heartbeat: float = field(default_factory=time.time)


class ChaosSyncTest:
    """Chaos sync test implementation."""

    def __init__(self, config: dict | None = None):
        self.config = config or DEFAULT_CONFIG.copy()
        self.nodes: dict[str, NodeState] = {}
        self.events_sent = 0
        self.events_confirmed = 0
        self.lock = threading.Lock()
        self.running = False
        self.chaos_events: list[dict] = []

    def initialize_nodes(self) -> None:
        """Initialize simulated nodes."""
        for i in range(self.config["num_nodes"]):
            _node_id = f"node-{i + 1}"
            self.nodes[_node_id] = NodeState(node_id=_node_id)
        logger.info(f"Initialized {len(self.nodes)} nodes")

    def simulate_node_kill(self, _node_id: str) -> None:
        """Simulate killing a node."""
        if _node_id in self.nodes:
            self.nodes[_node_id].is_alive = False
            self.chaos_events.append({
                "type": "kill",
                "node_id": _node_id,
                "timestamp": time.time(),
            })
            logger.warning(f"Node {_node_id} killed")

    def simulate_node_restart(self, _node_id: str) -> None:
        """Simulate restarting a node."""
        if _node_id in self.nodes:
            node = self.nodes[_node_id]
            node.is_alive = True
            node.restarts += 1
            node.last_heartbeat = time.time()
            self.chaos_events.append({
                "type": "restart",
                "node_id": _node_id,
                "timestamp": time.time(),
            })
            logger.info(f"Node {_node_id} restarted (restart #{node.restarts})")

    def simulate_sync(self, _node_id: str) -> bool:
        """
        Simulate state synchronization for a restarted node.

        Returns True if sync successful.
        """
        node = self.nodes.get(_node_id)
        if not node or not node.is_alive:
            return False

        # Find a healthy peer to sync from
        healthy_peers = [
            n for n in self.nodes.values()
            if n.is_alive and n.node_id != _node_id
        ]

        if not healthy_peers:
            logger.error(f"No healthy peers for {_node_id} to sync from")
            return False

        # Sync from the peer with highest block index
        sync_source = max(healthy_peers, key=lambda n: n.block_index)

        # Simulate gap-fill
        if node.block_index < sync_source.block_index:
            gap = sync_source.block_index - node.block_index
            node.block_index = sync_source.block_index
            node.block_hash = sync_source.block_hash
            logger.info(f"Node {_node_id} synced {gap} blocks from {sync_source.node_id}")

        return True

    def send_event(self) -> bool:
        """Send an event to the cluster."""
        alive_nodes = [n for n in self.nodes.values() if n.is_alive]
        if not alive_nodes:
            return False

        target = random.choice(alive_nodes)

        # Simulate event processing
        with self.lock:
            self.events_sent += 1
            target.events_processed += 1

            # Every 10 events, increment block
            if target.events_processed % 10 == 0:
                target.block_index += 1
                target.block_hash = f"hash-{target.block_index}-{time.time()}"

        return True

    def chaos_monkey(self) -> None:
        """Chaos monkey thread - randomly kills and restarts nodes."""
        kill_interval = self.config["kill_interval_seconds"]
        restart_delay = self.config["restart_delay_seconds"]

        while self.running:
            time.sleep(kill_interval)
            if not self.running:
                break

            # Pick a random node to kill (but keep at least 2 alive)
            victim = self._select_victim_node()
            if victim:
                self._kill_and_schedule_restart(victim, restart_delay)

    def _select_victim_node(self) -> NodeState | None:
        """Select a random node to kill (keeping at least 2 alive).
        
        Returns:
            Node to kill, or None if not enough alive nodes.
        """
        alive_nodes = [n for n in self.nodes.values() if n.is_alive]
        if len(alive_nodes) > 2:
            return random.choice(alive_nodes)
        return None

    def _kill_and_schedule_restart(self, victim: NodeState, restart_delay: float) -> None:
        """Kill a node and schedule its restart.
        
        Args:
            victim: Node to kill.
            restart_delay: Delay before restart.
        """
        self.simulate_node_kill(victim.node_id)

        # Schedule restart
        def delayed_restart(_node_id: str):
            time.sleep(restart_delay)
            if self.running:
                self.simulate_node_restart(_node_id)
                self.simulate_sync(_node_id)

        threading.Thread(
            target=delayed_restart,
            args=(victim.node_id,),
            daemon=True
        ).start()

    def verify_chain_integrity(self) -> dict:
        """Verify chain integrity across all nodes."""
        alive_nodes = [n for n in self.nodes.values() if n.is_alive]

        if not alive_nodes:
            return {"status": "no_alive_nodes", "consistent": False}

        # Check if all alive nodes have same block index
        block_indices = [n.block_index for n in alive_nodes]
        max_diff = max(block_indices) - min(block_indices) if block_indices else 0

        # Allow some lag (2 blocks difference is acceptable)
        consistent = max_diff <= 2

        return {
            "status": "checked",
            "alive_nodes": len(alive_nodes),
            "block_indices": block_indices,
            "max_difference": max_diff,
            "consistent": consistent,
        }

    def run_test(self) -> dict:
        """Execute the chaos sync test."""
        logger.info("Starting Chaos Sync Test")
        logger.info(f"Config: {self.config}")

        self.initialize_nodes()
        self.running = True

        start_time = time.time()
        duration = self.config["test_duration_seconds"]
        events_per_sec = self.config["events_per_second"]

        # Start chaos monkey
        chaos_thread = threading.Thread(target=self.chaos_monkey, daemon=True)
        chaos_thread.start()

        # Send events continuously
        self._send_events_loop(duration, events_per_sec)

        self.running = False
        elapsed = time.time() - start_time

        # Wait for any pending restarts
        time.sleep(2)

        # RECOVERY PHASE: Explicitly trigger sync for all nodes
        recovery_time = self._perform_recovery_phase()

        # Final integrity check
        _integrity = self.verify_chain_integrity()

        # Build and return results
        return self._build_test_results(elapsed, recovery_time, _integrity)

    def _send_events_loop(self, duration: float, events_per_sec: int) -> None:
        """Send events continuously for the test duration.
        
        Args:
            duration: Test duration in seconds.
            events_per_sec: Events to send per second.
        """
        start_time = time.time()
        event_interval = 1.0 / events_per_sec
        while time.time() - start_time < duration:
            self.send_event()
            time.sleep(event_interval)

    def _perform_recovery_phase(self) -> float:
        """Perform recovery phase to heal the cluster.
        
        Returns:
            Time taken for recovery in seconds.
        """
        logger.info("Entering Recovery Phase (Heal Cluster)...")
        recovery_start = time.time()
        
        # Try to heal for up to 10 seconds
        for _ in range(10):
            if not self._sync_all_nodes():
                logger.info("Cluster healed successfully.")
                break
            time.sleep(1)
        
        return time.time() - recovery_start

    def _sync_all_nodes(self) -> bool:
        """Sync all alive nodes to the same block index.
        
        Returns:
            True if nodes are not all synced, False if all synced.
        """
        alive_nodes = [n for n in self.nodes.values() if n.is_alive]
        if not alive_nodes:
            return False
            
        # Get max block index
        max_block = max(n.block_index for n in alive_nodes)
        
        # Trigger sync on all nodes
        all_synced = True
        for node in alive_nodes:
            self.simulate_sync(node.node_id)
            if node.block_index < max_block:
                all_synced = False
        
        return not all_synced

    def _build_test_results(self, elapsed: float, recovery_time: float, _integrity: dict) -> dict:
        """Build the test results dictionary.
        
        Args:
            elapsed: Total test elapsed time.
            recovery_time: Recovery phase time.
            _integrity: Chain integrity check result.
            
        Returns:
            Test results dictionary.
        """
        total_restarts = sum(n.restarts for n in self.nodes.values())
        total_kills = len([e for e in self.chaos_events if e["type"] == "kill"])

        return {
            "test_name": "chaos_sync",
            "status": "completed",
            "elapsed_seconds": elapsed,
            "recovery_seconds": recovery_time,
            "events_sent": self.events_sent,
            "events_per_second": self.events_sent / elapsed if elapsed else 0,
            "total_node_kills": total_kills,
            "total_node_restarts": total_restarts,
            "chaos_events": len(self.chaos_events),
            "integrity": _integrity,
            "chain_consistent": _integrity["consistent"],
            "final_node_states": {
                n.node_id: {
                    "alive": n.is_alive,
                    "block_index": n.block_index,
                    "events_processed": n.events_processed,
                    "restarts": n.restarts,
                }
                for n in self.nodes.values()
            },
        }


# Pytest test cases

class TestChaosSync:
    """Pytest test cases for chaos sync."""

    @pytest.fixture
    def quick_config(self):
        """Quick config for fast tests."""
        return {
            "num_nodes": 4,
            "test_duration_seconds": 10,
            "events_per_second": 5,
            "kill_interval_seconds": 3,
            "restart_delay_seconds": 1,
            "target_nodes": ["localhost:5001"],
        }

    def test_node_initialization(self):
        """Test node initialization."""
        _test = ChaosSyncTest()
        _test.initialize_nodes()
        assert len(_test.nodes) == 4
        assert all(n.is_alive for n in _test.nodes.values())

    def test_node_kill_restart(self):
        """Test node kill and restart simulation."""
        _test = ChaosSyncTest()
        _test.initialize_nodes()

        _test.simulate_node_kill("node-1")
        assert not _test.nodes["node-1"].is_alive

        _test.simulate_node_restart("node-1")
        assert _test.nodes["node-1"].is_alive
        assert _test.nodes["node-1"].restarts == 1

    def test_state_sync(self):
        """Test state synchronization."""
        _test = ChaosSyncTest()
        _test.initialize_nodes()

        # Advance one node
        _test.nodes["node-2"].block_index = 100
        _test.nodes["node-2"].block_hash = "hash-100"

        # Kill and restart node-1
        _test.simulate_node_kill("node-1")
        _test.simulate_node_restart("node-1")
        _test.simulate_sync("node-1")

        # Should have synced
        assert _test.nodes["node-1"].block_index == 100

    def test_quick_chaos(self, quick_config):
        """Test quick chaos run."""
        _test = ChaosSyncTest(quick_config)
        _result = _test.run_test()

        assert _result["status"] == "completed"
        assert _result["events_sent"] > 0

    def test_chain_integrity(self, quick_config):
        """Test chain integrity after chaos."""
        _test = ChaosSyncTest(quick_config)
        _result = _test.run_test()

        # Chain should be consistent
        assert _result["chain_consistent"]

    @pytest.mark.stress
    def test_full_chaos(self):
        """Full chaos test (marked as stress)."""
        _test = ChaosSyncTest(DEFAULT_CONFIG)
        _result = _test.run_test()

        assert _result["status"] == "completed"
        # In extreme chaos, temporary inconsistency IS acceptable during the run,
        # BUT eventual consistency IS REQUIRED after the recovery phase.
        
        assert _result["total_node_restarts"] > 0  # ensure chaos actually happened

        # ABSOLUTE RELIABILITY CHECK:
        # The chain MUST be consistent after recovery.
        if not _result["chain_consistent"]:
            # If failed, print detailed debug info
            print("\n!!! RELIABILITY FAILURE !!!")
            print(f"Max Difference: {_result['integrity']['max_difference']} blocks")
            print(f"Block Indices: {_result['integrity']['block_indices']}")
        
        assert _result["chain_consistent"], "Chain passed validation but failed Eventual Consistency check!"
        
        # Log successful recovery
        logger.info(f"Test passed with eventual consistency. Recovery took {_result['recovery_seconds']:.2f}s")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    test = ChaosSyncTest()
    result = test.run_test()

    print("\n" + "=" * 60)
    print("  CHAOS SYNC TEST RESULTS")
    print("=" * 60)
    
    print(f"\n📊 TEST SUMMARY")
    print(f"  Status:              {result['status']}")
    print(f"  Duration:            {result['elapsed_seconds']:.2f}s")
    print(f"  Recovery Time:       {result['recovery_seconds']:.2f}s")
    print(f"  Events/Second:       {result['events_per_second']:.2f}")
    
    print(f"\n🖧  NODE METRICS (TODO #7 - Hierarchical Resilience)")
    print(f"  Number of Nodes:     {len(result['final_node_states'])}")
    print(f"  Total Node Kills:    {result['total_node_kills']}")
    print(f"  Total Restarts:      {result['total_node_restarts']}")
    print(f"  Chaos Events:        {result['chaos_events']}")
    
    print(f"\n🔗 CHAIN INTEGRITY")
    print(f"  Chain Consistent:    {'✅ Yes' if result['chain_consistent'] else '❌ No'}")
    integrity = result.get("integrity", {})
    if integrity:
        print(f"  Alive Nodes:         {integrity.get('alive_nodes', 'N/A')}")
        print(f"  Block Indices:       {integrity.get('block_indices', [])}")
        print(f"  Max Difference:      {integrity.get('max_difference', 0)}")
    
    print(f"\n📝 EVENT STATISTICS")
    print(f"  Events Sent:         {result['events_sent']}")
    
    print(f"\n🖥️  INDIVIDUAL NODE STATES")
    for node_id, state in result["final_node_states"].items():
        status_icon = "🟢" if state['alive'] else "🔴"
        print(f"  {status_icon} {node_id}:")
        print(f"      Block Index:      {state['block_index']}")
        print(f"      Events Processed: {state['events_processed']}")
        print(f"      Restarts:         {state['restarts']}")
    
    print("=" * 60)

