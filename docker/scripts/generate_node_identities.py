"""
Script to generate cryptographic node identities for HieraChain test deployments.

Enhancements:
- Optional rogue node generation controlled by INCLUDE_ROGUE_NODE env var.
- Rogue node identity and peers.env are generated separately without
  polluting legitimate nodes' peers.
"""

import os
import json
import zmq
from typing import Dict, List
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

def generate_node_identity(node_id: str, msp_id: str) -> dict:
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

def _write_identity(node_dir: str, identity: dict) -> None:
    os.makedirs(node_dir, exist_ok=True)
    identity_path = os.path.join(node_dir, "identity.json")
    with open(identity_path, "w") as f:
        json.dump(identity, f, indent=4)
    print(f"Generated identity for {identity['node_id']} at {identity_path}")
    print(f"  Public Key: {identity['signing_public_key'][:16]}...")


def _write_peers_env(node_dir: str, peers: List[str]) -> None:
    peers_env_path = os.path.join(node_dir, "peers.env")
    with open(peers_env_path, "w") as f:
        # Escape '$' as '$$' for Docker Compose env_file compatibility
        peers_list_str = ",".join(peers).replace("$", "$$")
        f.write(f"HRC_PEERS={peers_list_str}\n")
    print(f"Generated peers.env for {os.path.basename(node_dir)} at {peers_env_path}")


def main() -> None:
    nodes: List[str] = ["node1", "node2", "node3", "node4"]
    base_dir = "docker/nodes"
    os.makedirs(base_dir, exist_ok=True)

    include_rogue = os.getenv("INCLUDE_ROGUE_NODE", "false").lower() == "true"
    rogue_node_id = os.getenv("ROGUE_NODE_ID", "rogue-node")

    all_identities: Dict[str, dict] = {}

    # Generate identities for legitimate nodes
    for i, node_id in enumerate(nodes, 1):
        node_dir = os.path.join(base_dir, node_id)
        msp_id = f"Org{i}-MSP"
        identity = generate_node_identity(node_id, msp_id)
        _write_identity(node_dir, identity)
        all_identities[node_id] = identity

    # Optionally generate rogue node identity
    if include_rogue:
        rogue_dir = os.path.join(base_dir, rogue_node_id)
        rogue_identity = generate_node_identity(rogue_node_id, "RogueOrg-MSP")
        _write_identity(rogue_dir, rogue_identity)
        all_identities[rogue_node_id] = rogue_identity

    # IP/Port mapping (fixed per requirements)
    ips: Dict[str, str] = {
        "node1": "172.28.0.10",
        "node2": "172.28.0.11",
        "node3": "172.28.0.12",
        "node4": "172.28.0.13",
    }
    ports: Dict[str, int] = {
        "node1": 5001,
        "node2": 5002,
        "node3": 5003,
        "node4": 5004,
    }

    # Only add rogue mapping for its own peers.env generation
    if include_rogue:
        ips[rogue_node_id] = "172.28.0.20"
        ports[rogue_node_id] = 5005

    # Generate peers.env for legitimate nodes (exclude rogue node always)
    for node_id in nodes:
        other_peers: List[str] = []
        for peer_id in nodes:  # only legitimate peers among themselves
            if peer_id == node_id:
                continue
            peer_info = all_identities[peer_id]
            peer_str = f"{peer_id}@{ips[peer_id]}:{ports[peer_id]}:{peer_info['transport_public_key']}"
            other_peers.append(peer_str)
        _write_peers_env(os.path.join(base_dir, node_id), other_peers)

    # Generate peers.env for rogue node (if included) with knowledge of real cluster
    if include_rogue:
        rogue_peers: List[str] = []
        for peer_id in nodes:  # rogue knows about node1-4
            peer_info = all_identities[peer_id]
            peer_str = f"{peer_id}@{ips[peer_id]}:{ports[peer_id]}:{peer_info['transport_public_key']}"
            rogue_peers.append(peer_str)
        _write_peers_env(os.path.join(base_dir, rogue_node_id), rogue_peers)

    # Save a global peer list (can include rogue when enabled)
    peer_list_path = os.path.join(base_dir, "peers.json")
    with open(peer_list_path, "w") as f:
        json.dump(all_identities, f, indent=4)
    print(f"\nSaved all peer identities to {peer_list_path}")

if __name__ == "__main__":
    main()
