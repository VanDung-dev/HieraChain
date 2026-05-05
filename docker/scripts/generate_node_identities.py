"""
Script to generate cryptographic node identities for HieraChain test deployments.
"""

import os
import json
import zmq
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

def generate_node_identity(node_id, msp_id):
    # 1. Generate Ed25519 Signing Keypair
    signing_key = ed25519.Ed25519PrivateKey.generate()
    signing_public_key = signing_key.public_key()
    
    # Export keys to hex
    signing_secret_hex = signing_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    ).hex()
    
    signing_public_hex = signing_public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    ).hex()
    
    # 2. Generate Curve25519 Transport Keypair for ZMQ
    transport_public, transport_secret = zmq.curve_keypair()
    
    return {
        "node_id": node_id,
        "msp_id": msp_id,
        "signing_key": signing_secret_hex,
        "signing_public_key": signing_public_hex,
        "transport_secret_key": transport_secret.decode('utf-8'),
        "transport_public_key": transport_public.decode('utf-8')
    }

def main():
    nodes = ["node1", "node2", "node3", "node4"]
    base_dir = "docker/nodes"
    
    os.makedirs(base_dir, exist_ok=True)
    
    all_identities = {}
    
    for i, node_id in enumerate(nodes, 1):
        node_dir = os.path.join(base_dir, node_id)
        os.makedirs(node_dir, exist_ok=True)
        
        msp_id = f"Org{i}-MSP"
        identity = generate_node_identity(node_id, msp_id)
        
        # Save individual identity
        identity_path = os.path.join(node_dir, "identity.json")
        with open(identity_path, "w") as f:
            json.dump(identity, f, indent=4)
        
        all_identities[node_id] = identity
        print(f"Generated identity for {node_id} at {identity_path}")
        print(f"  Public Key: {identity['signing_public_key'][:16]}...")

    # Generate peers.env for each node
    # Format: node_id@ip:port:transport_public_key
    ips = {
        "node1": "172.28.0.10",
        "node2": "172.28.0.11",
        "node3": "172.28.0.12",
        "node4": "172.28.0.13"
    }
    ports = {
        "node1": 5001,
        "node2": 5002,
        "node3": 5003,
        "node4": 5004
    }

    for node_id in nodes:
        other_peers = []
        for peer_id in nodes:
            if peer_id == node_id:
                continue
            
            peer_info = all_identities[peer_id]
            peer_str = f"{peer_id}@{ips[peer_id]}:{ports[peer_id]}:{peer_info['transport_public_key']}"
            other_peers.append(peer_str)
        
        peers_env_path = os.path.join(base_dir, node_id, "peers.env")
        with open(peers_env_path, "w") as f:
            # Escape '$' as '$$' for Docker Compose env_file compatibility
            peers_list_str = ",".join(other_peers).replace("$", "$$")
            f.write(f"HRC_PEERS={peers_list_str}\n")
        print(f"Generated peers.env for {node_id} at {peers_env_path}")

    # Save a global peer list for convenience
    peer_list_path = os.path.join(base_dir, "peers.json")
    with open(peer_list_path, "w") as f:
        json.dump(all_identities, f, indent=4)
    print(f"\nSaved all peer identities to {peer_list_path}")

if __name__ == "__main__":
    main()
