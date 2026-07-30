"""
Generate cryptographic node identities for HieraChain test deployments.
Includes Ed25519 signing keys, Curve25519 ZMQ transport keys,
and X25519 WireGuard keys for multi-region P2P mesh simulation.
"""

import os
import json
import base64
import zmq
from typing import Dict, List
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives import serialization


NODE_WG_IPS: Dict[str, str] = {
    "node1": "10.200.1.1",
    "node2": "10.200.2.1",
    "node3": "10.200.3.1",
    "node4": "10.200.4.1",
}
NODE_WG_ENDPOINTS: Dict[str, str] = {
    "node1": "172.29.0.10",
    "node2": "172.29.0.11",
    "node3": "172.29.0.12",
    "node4": "172.29.0.13",
}
NODE_P2P_PORTS: Dict[str, int] = {
    "node1": 5001,
    "node2": 5002,
    "node3": 5003,
    "node4": 5004,
}


def generate_wireguard_keypair() -> tuple[str, str]:
    private_key = X25519PrivateKey.generate()
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return base64.b64encode(private_bytes).decode(), base64.b64encode(public_bytes).decode()


def generate_node_identity(node_id: str, msp_id: str) -> dict:
    signing_key = ed25519.Ed25519PrivateKey.generate()
    signing_public_key = signing_key.public_key()

    signing_secret_hex = signing_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    ).hex()

    signing_public_hex = signing_public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()

    transport_public, transport_secret = zmq.curve_keypair()

    wg_private, wg_public = generate_wireguard_keypair()

    return {
        "node_id": node_id,
        "msp_id": msp_id,
        "signing_key": signing_secret_hex,
        "signing_public_key": signing_public_hex,
        "transport_secret_key": transport_secret.decode("utf-8"),
        "transport_public_key": transport_public.decode("utf-8"),
        "wireguard_private_key": wg_private,
        "wireguard_public_key": wg_public,
        "wireguard_ip": NODE_WG_IPS.get(node_id, ""),
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
        peers_list_str = ",".join(peers).replace("$", "$$")
        f.write(f"HRC_PEERS={peers_list_str}\n")
    print(f"Generated peers.env for {os.path.basename(node_dir)}")


def _write_wg_config(node_dir: str, node_id: str, identity: dict,
                     wg_peers: List[dict]) -> None:
    wg_conf_path = os.path.join(node_dir, "wg0.conf")
    wg_ip = identity.get("wireguard_ip") or NODE_WG_IPS.get(node_id, "10.200.0.0")
    lines = [
        "[Interface]",
        f"PrivateKey = {identity['wireguard_private_key']}",
        f"ListenPort = 51820",
        "",
    ]
    for peer in wg_peers:
        lines.extend([
            f"[Peer]",
            f"# {peer['node_id']}",
            f"PublicKey = {peer['wireguard_public_key']}",
            f"Endpoint = {peer['endpoint']}:51820",
            f"AllowedIPs = {peer['wg_ip']}/32",
            "PersistentKeepalive = 25",
            "",
        ])
    with open(wg_conf_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Generated wg0.conf for {node_id}")


def main() -> None:
    nodes: List[str] = ["node1", "node2", "node3", "node4"]
    base_dir = "docker/nodes"
    os.makedirs(base_dir, exist_ok=True)

    all_identities: Dict[str, dict] = {}

    print("=== Generating HieraChain Node Identities ===")

    for i, node_id in enumerate(nodes, 1):
        node_dir = os.path.join(base_dir, node_id)
        msp_id = f"Org{i}-MSP"
        identity = generate_node_identity(node_id, msp_id)
        _write_identity(node_dir, identity)
        all_identities[node_id] = identity

    # Build WireGuard peer info for wg0.conf generation
    wg_peer_info: Dict[str, dict] = {}
    for node_id in nodes:
        wg_peer_info[node_id] = {
            "node_id": node_id,
            "wireguard_public_key": all_identities[node_id]["wireguard_public_key"],
            "wg_ip": NODE_WG_IPS[node_id],
            "endpoint": NODE_WG_ENDPOINTS[node_id],
        }

    print("\n=== Generating WireGuard Configs ===")

    for node_id in nodes:
        node_dir = os.path.join(base_dir, node_id)
        peers = [p for pid, p in wg_peer_info.items() if pid != node_id]
        _write_wg_config(node_dir, node_id, all_identities[node_id], peers)

    print("\n=== Generating Peers.env (WireGuard IPs) ===")

    for node_id in nodes:
        other_peers: List[str] = []
        for peer_id in nodes:
            if peer_id == node_id:
                continue
            peer_info = all_identities[peer_id]
            peer_str = f"{peer_id}@{NODE_WG_IPS[peer_id]}:{NODE_P2P_PORTS[peer_id]}:{peer_info['transport_public_key']}"
            other_peers.append(peer_str)
        _write_peers_env(os.path.join(base_dir, node_id), other_peers)

    peer_list_path = os.path.join(base_dir, "peers.json")
    with open(peer_list_path, "w") as f:
        json.dump(all_identities, f, indent=4)
    print(f"\nSaved all peer identities to {peer_list_path}")
    print("=== Identity generation complete ===")


if __name__ == "__main__":
    main()
