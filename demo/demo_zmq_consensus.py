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

from hierachain.security.security_utils import KeyPair
from hierachain.network.zmq_transport import ZmqNode
from hierachain.hierarchical.consensus.bft_consensus import BFTConsensus

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ConsensusDemo")

async def run_node(node_id: str, consensus: BFTConsensus, zmq_node: ZmqNode):
    """Run a single node's main loop"""
    logger.info(f"Starting Node {node_id}")
    
    # Define message handler
    def msg_handler(msg, sender):
        try:
            # logger.info(f"{node_id} received from {sender}: {msg.keys()}")
            if "message_type" in msg:
                # It's a BFT message
                consensus.handle_message(msg)
            elif msg.get("type") == "client_request":
                logger.info(f"{node_id} received client request")
                consensus.request(msg["operation"])
        except Exception as e:
            logger.error(f"Error handling message in {node_id}: {e}")

    zmq_node.set_handler(msg_handler)
    await zmq_node.start()
    
    # Keep running
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
    logger.info("Monitoring consensus state...")
    start_time = asyncio.get_running_loop().time()
    success = False

    while asyncio.get_running_loop().time() - start_time < timeout_seconds:
        committed_count = 0
        for nid, cons in consensus_map.items():
            status = cons.get_consensus_status()
            if status["state"] == "committed":
                committed_count += 1

        if committed_count >= 3:
            logger.info("SUCCESS: Supermajority reached consensus!")
            success = True
            break

        await asyncio.sleep(0.5)

    if not success:
        logger.error("FAILED to reach consensus in time.")


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
