"""
Demonstration script for ZeroMQ-based BFT Consensus.

This script sets up a local network of nodes using AsyncIO and ZeroMQ to demonstrate
the Byzantine Fault Tolerance (BFT) consensus mechanism in the HieraChain framework.
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

async def main():
    logger.info("Initializing Ed25519 + ZeroMQ Consensus Demo (AsyncIO)")
    
    # 1. Configuration
    nodes = ["node1", "node2", "node3", "node4"]
    base_port = 5555
    ports = {nid: base_port + i for i, nid in enumerate(nodes)}
    
    # 2. Key Generation
    logger.info("Generating keys...")
    keypairs = {nid: KeyPair() for nid in nodes}
    public_keys = {nid: kp.public_key for nid, kp in keypairs.items()}
    
    # 3. Create Network & Consensus Instances
    zmq_nodes = {}
    consensus_map = {}
    
    for nid in nodes:
        # Create ZmqNode
        znode = ZmqNode(nid, ports[nid])
        zmq_nodes[nid] = znode
        
        # Create Consensus
        consensus = BFTConsensus(
            node_id=nid,
            all_nodes=nodes,
            f=1,
            keypair=keypairs[nid],
            node_public_keys=public_keys,
            zmq_node=znode
        )
        consensus_map[nid] = consensus
    
    # 4. Connect Peers (Full Mesh)
    logger.info("Connecting peers...")
    for nid in nodes:
        for peer in nodes:
            if nid != peer:
                # address = f"tcp://localhost:{ports[peer]}" 
                # Note: localhost sometimes resolves to ipv6 ::1, better use 127.0.0.1 for zmq
                address = f"tcp://127.0.0.1:{ports[peer]}"
                zmq_nodes[nid].register_peer(peer, address)
    
    # 5. Start Node Tasks
    tasks = []
    for nid in nodes:
        task = asyncio.create_task(run_node(nid, consensus_map[nid], zmq_nodes[nid]))
        tasks.append(task)
        
    await asyncio.sleep(2) # Wait for connections
    
    # 6. Submit a Request
    logger.info("Submitting client request to Node1 (Primary)...")
    client_request = {
        "client_id": "client_001",
        "operation": {
            "type": "transfer",
            "amount": 100,
            "to": "bob"
        }
    }
    
    # Inject request directly into Node1
    consensus_map["node1"].request(client_request)
    
    # 7. Monitor Consensus
    logger.info("Monitoring consensus state...")
    start_time = asyncio.get_running_loop().time()
    success = False
    
    while asyncio.get_running_loop().time() - start_time < 15:
        committed_count = 0
        for nid, cons in consensus_map.items():
            status = cons.get_consensus_status()
            if status["state"] == "committed":
                committed_count += 1
                # logger.info(f"{nid} COMMITTED sequence {status['sequence_number']}")
        
        if committed_count >= 3:
            logger.info("SUCCESS: Supermajority reached consensus!")
            success = True
            break
            
        await asyncio.sleep(0.5)
        
    if not success:
        logger.error("FAILED to reach consensus in time.")
    
    # Cleanup
    logger.info("Demo finished. Cleaning up...")
    for task in tasks:
        task.cancel()
    
    await asyncio.gather(*tasks, return_exceptions=True)

if __name__ == "__main__":
    try:
        # Windows selector event loop policy fix might be needed but python 3.12 usually handles it.
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
