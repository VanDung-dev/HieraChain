"""
Demonstration script for ZeroMQ-based BFT Consensus.

This script sets up a local network of nodes using AsyncIO and ZeroMQ to demonstrate
the Byzantine Fault Tolerance (BFT) consensus mechanism in the HieraChain Ledger.
"""


import sys
import os
import asyncio
import logging

# Add parent directory to path to allow importing hierachain modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hierachain.security import KeyPair
from hierachain.network import ZmqNode
from hierachain.consensus import BFTConsensus

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ConsensusDemo")

async def run_node(node_id: str, consensus: BFTConsensus, zmq_node: ZmqNode):
    """Run a single node's main loop"""
    logger.info(f"Starting Node {node_id}")
    
    msg_handler = create_message_handler(node_id, consensus)
    zmq_node.set_handler(msg_handler)
    await zmq_node.start()
    
    await node_main_loop(node_id, zmq_node)


def create_message_handler(node_id: str, consensus: BFTConsensus):
    """Factory function to create message handler with dependencies"""
    def msg_handler(msg, sender):
        handle_node_message(node_id, consensus, msg)
    return msg_handler


def handle_node_message(node_id: str, consensus: BFTConsensus, msg: dict):
    """Handle incoming message for a node"""
    try:
        message_type = get_message_type(msg)
        if message_type == "bft":
            process_bft_message(consensus, msg)
        elif message_type == "client_request":
            process_client_request(node_id, consensus, msg)
    except Exception as e:
        logger.error(f"Error handling message in {node_id}: {e}")


def get_message_type(msg: dict) -> str:
    """Determine the type of incoming message"""
    if "message_type" in msg:
        return "bft"
    if msg.get("type") == "client_request":
        return "client_request"
    return "unknown"


def process_bft_message(consensus: BFTConsensus, msg: dict):
    """Process BFT consensus message"""
    consensus.handle_message(msg)


def process_client_request(node_id: str, consensus: BFTConsensus, msg: dict):
    """Process client request message"""
    logger.info(f"{node_id} received client request")
    consensus.request(msg["operation"])


async def node_main_loop(node_id: str, zmq_node: ZmqNode):
    """Main loop for node - runs until cancelled"""
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        logger.info(f"Node {node_id} shutting down...")
        await zmq_node.stop()

def get_nodes_and_ports():
    nodes = ["node1", "node2", "node3", "node4"]
    base_port = 5555
    ports = {nid: base_port + i for i, nid in enumerate(nodes)}
    return nodes, ports


def generate_keys(nodes):
    logger.info("Generating keys...")
    keypairs = {nid: KeyPair() for nid in nodes}
    public_keys = {nid: kp.public_key for nid, kp in keypairs.items()}
    return keypairs, public_keys


def create_network_and_consensus(nodes, ports, keypairs, public_keys):
    zmq_nodes = {}
    consensus_map = {}

    for nid in nodes:
        znode = ZmqNode(nid, ports[nid])
        zmq_nodes[nid] = znode

        consensus = BFTConsensus(
            node_id=nid,
            all_nodes=nodes,
            f=1,
            keypair=keypairs[nid],
            node_public_keys=public_keys,
            zmq_node=znode,
        )
        consensus_map[nid] = consensus

    return zmq_nodes, consensus_map


def connect_peers_full_mesh(nodes, ports, zmq_nodes):
    logger.info("Connecting peers...")
    for nid in nodes:
        for peer in nodes:
            if nid != peer:
                address = f"tcp://127.0.0.1:{ports[peer]}"
                zmq_nodes[nid].register_peer(peer, address)


def start_node_tasks(nodes, zmq_nodes, consensus_map):
    tasks = []
    for nid in nodes:
        task = asyncio.create_task(
            run_node(nid, consensus_map[nid], zmq_nodes[nid])
        )
        tasks.append(task)
    return tasks


def build_client_request():
    return {
        "client_id": "client_001",
        "operation": {"type": "transfer", "amount": 100, "to": "bob"},
    }


def submit_client_request(consensus_map, client_request):
    logger.info("Submitting client request to Node1 (Primary)...")
    consensus_map["node1"].request(client_request)


async def monitor_consensus(consensus_map, timeout_seconds=15):
    """
    Monitor consensus state until supermajority is reached or timeout.
    
    Args:
        consensus_map: Dict of node_id -> BFTConsensus
        timeout_seconds: Maximum time to wait for consensus
    
    Returns:
        bool: True if consensus reached, False if timeout
    """
    logger.info("Monitoring consensus state...")
    
    # Calculate threshold based on node count: need > 2f nodes (Byzantine quorum)
    threshold = len(consensus_map) - len(consensus_map) // 3
    
    async def check_consensus_reached() -> bool:
        """Check if consensus has been reached"""
        committed_count = sum(
            1 for cons in consensus_map.values()
            if cons.get_consensus_status()["state"] == "committed"
        )
        return committed_count >= threshold
    
    try:
        async with asyncio.timeout(timeout_seconds):
            while True:
                if await check_consensus_reached():
                    logger.info(f"SUCCESS: Supermajority ({threshold}/{len(consensus_map)}) reached consensus!")
                    return True
                await asyncio.sleep(0.5)
    except asyncio.TimeoutError:
        logger.error("FAILED to reach consensus in time.")
        return False


async def cleanup_tasks(tasks):
    logger.info("Demo finished. Cleaning up...")
    for task in tasks:
        task.cancel()

    await asyncio.gather(*tasks, return_exceptions=True)


async def main():
    logger.info("Initializing Ed25519 + ZeroMQ Consensus Demo (AsyncIO)")

    nodes, ports = get_nodes_and_ports()
    keypairs, public_keys = generate_keys(nodes)
    zmq_nodes, consensus_map = create_network_and_consensus(
        nodes, ports, keypairs, public_keys
    )

    connect_peers_full_mesh(nodes, ports, zmq_nodes)

    tasks = start_node_tasks(nodes, zmq_nodes, consensus_map)

    await asyncio.sleep(2)

    client_request = build_client_request()
    submit_client_request(consensus_map, client_request)

    await monitor_consensus(consensus_map, timeout_seconds=15)

    await cleanup_tasks(tasks)

if __name__ == "__main__":
    try:
        # Windows selector event loop policy fix might be needed but python 3.12 usually handles it.
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
