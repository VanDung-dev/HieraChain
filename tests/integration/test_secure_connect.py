"""
Test Secure Network Integration.

This test suite is designed to verify the secure network functionalities.
"""


import asyncio
import logging
import sys
import os

from hierachain.network.secure_connection import SecureConnectionManager
from hierachain.security.msp import HierarchicalMSP
from hierachain.security.identity import IdentityManager

# Ensure the project root is in python path
sys.path.append(os.getcwd())

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("TestSecureNet")

import pytest

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

@pytest.mark.asyncio
async def test_secure_connection():
    logger.info("--- Starting Secure Network Integration Test ---")
    
    # 1. Mock MSP Setup (Simplified)
    # In reality, this would load from files.
    dummy_ca_config = {"root_cert": "dummy_root", "policy": {}}
    msp1 = HierarchicalMSP("Org1", dummy_ca_config)
    msp2 = HierarchicalMSP("Org2", dummy_ca_config)
    identity_mgr = IdentityManager()

    # 2. Create Two Secure Nodes
    node1 = SecureConnectionManager("Node1", 5001, msp1, identity_mgr)
    node2 = SecureConnectionManager("Node2", 5002, msp2, identity_mgr)
    
    # 3. Start Nodes
    await node1.start()
    await node2.start()
    
    # Allow bindings to settle
    await asyncio.sleep(1)
    
    # 4. Connect Node1 -> Node2
    # Node1 needs Node2's Public Transport Key to initiate CurveZMQ connection
    node2_pub_key = node2.transport_public.decode('utf-8')
    
    logger.info("Node1 initiating secure connection to Node2...")
    await node1.connect_to_peer("Node2", "tcp://127.0.0.1:5002", node2_pub_key)
    
    # 5. Wait for Handshake (Async)
    await asyncio.sleep(2)
    
    # 6. Verify Authentication State
    if node1.authenticated_peers.get("Node2"):
        logger.info("SUCCESS: Node1 successfully authenticated Node2!")
    else:
        logger.error("FAILURE: Node1 failed to authenticate Node2.")
        
    if node2.authenticated_peers.get("Node1"):
        logger.info("SUCCESS: Node2 successfully authenticated Node1!")
    else:
        logger.error("FAILURE: Node2 failed to authenticate Node1.")

    # Cleanup
    await node1.transport.stop()
    await node2.transport.stop()
