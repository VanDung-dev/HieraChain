"""
Benchmarking Script for Hashing Methods

This script benchmarks the performance of two hashing methods:
1. The new method using Merkle Trees (Block.calculate_hash())
2. The old method simulating the old O(N) hashing method (simulate_old_calculate_hash())
"""


import time
import json
import hashlib

from hierachain.core.block import Block

def simulate_old_calculate_hash(block: Block) -> str:
    """Simulate the old O(N) hashing method."""
    events_list = block._table_to_list_of_dicts(block._events)
    
    block_data = {
        "index": block.index,
        "events": events_list,
        "timestamp": block.timestamp,
        "previous_hash": block.previous_hash,
        "nonce": block.nonce
    }
    
    # Convert to JSON string with sorted keys for consistent hashing
    block_string = json.dumps(block_data, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(block_string.encode()).hexdigest()

def benchmark_hashing():
    print("Preparing benchmark data...")
    # Create 10,000 events
    events = []
    for i in range(10000):
        events.append({
            "entity_id": f"ENTITY-{i}",
            "event": "BENCHMARK_EVENT",
            "timestamp": time.time(),
            "details": {"iteration": str(i), "data": "x" * 100} # Some payload
        })
    
    print(f"Created {len(events)} events.")
    
    print("Initializing Block (Builds Merkle Tree)...")
    start_time = time.time()
    block = Block(index=1, events=events)
    init_duration = time.time() - start_time
    print(f"Block Init Time: {init_duration:.4f}s")
    
    print("\n--- Benchmarking calculate_hash() ---")
    
    # New Method (Merkle)
    start_time = time.time()
    iterations = 1000
    for _ in range(iterations):
        _ = block.calculate_hash()
    new_duration = time.time() - start_time
    avg_new = new_duration / iterations
    print(f"New Method (Merkle Header Hash): {avg_new:.6f}s per call")
    
    # Old Method (Simulation)
    start_time = time.time()
    iterations_old = 10
    for _ in range(iterations_old):
        _ = simulate_old_calculate_hash(block)
    old_duration = time.time() - start_time
    avg_old = old_duration / iterations_old
    print(f"Old Method (Full JSON Serializ): {avg_old:.6f}s per call")
    
    speedup = avg_old / avg_new
    print(f"\nSpeedup Factor: {speedup:.2f}x")

if __name__ == "__main__":
    benchmark_hashing()
