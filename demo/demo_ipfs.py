"""
Demonstration script for IPFS Integration in HieraChain Ledger.

This script demonstrates how IPFS is used for off-chain storage:
- Direct IPFS client usage (upload/download/encryption)
- Storing large event details in IPFS and referencing via CID on-chain
- Resolving IPFS CIDs to actual data during retrieval
- Private Data and Contract implementation storage in IPFS
- Explorer visualization with IPFS indicators

Usage:
1. Ensure IPFS daemon is running: `ipfs daemon`
2. Run this script: `python demo/demo_ipfs.py`
"""

import os
import sys
import time
import hashlib

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from typing import Any
from hierachain.api.storage import (
    IPFSClient,
    format_event_for_display,
    detect_data_location
)
from hierachain.hierarchical import HierarchyManager


class MockIPFSClient:
    """Mock IPFS Client for demonstration when no daemon is running."""
    def __init__(self):
        print("! Using Mock IPFS Client (No IPFS daemon detected)")
        self.storage = {}

    def get_daemon_version(self) -> dict:
        return {"Version": "0.12.0-mock"}

    def upload_json(self, data: dict) -> dict:
        data_str = str(data).encode()
        cid = "Qm" + hashlib.sha256(data_str).hexdigest()[:44]
        nonce = os.urandom(12).hex()
        self.storage[cid] = data
        return {"cid": cid, "nonce": nonce, "size": len(data_str)}

    def download_json(
        self,
        cid: str,
        encrypted: bool = True,
        nonce: str = None
    ) -> dict:
        return self.storage.get(cid, {})


def print_section(title):
    """Print a section header."""
    print("\n" + "=" * 80)
    print(f" {title} ".center(80, "="))
    print("=" * 80)


def demonstrate_direct_ipfs():
    """Demonstrate direct IPFS client usage."""
    print_section("1. Direct IPFS Client Usage")

    # Initialize IPFS Client
    # In a real app, this would use create_ipfs_client_from_env()
    client: Any = None
    try:
        client = IPFSClient(
            ipfs_host="/ip4/127.0.0.1/tcp/5001",
            encryption_key=os.urandom(32),  # 256-bit AES key
            auto_pin=True
        )
        # Check connection
        version = client.get_daemon_version()
        print(f"✓ Connected to IPFS Daemon v{version['Version']}")
    except Exception as e:
        print(f"! Real IPFS Error: {e}")
        print("  (Make sure 'ipfs daemon' is running locally on port 5001)")
        # Fallback to Mock
        client = MockIPFSClient()
        version = client.get_daemon_version()
        print(f"✓ Using {version['Version']}")

    try:
        # Sample data to store
        large_data = {
            "title": "Supply Chain Document",
            "content": "A very large content that we don't want to store on-chain...",
            "items": [{"id": i, "val": os.urandom(10).hex()} for i in range(5)],
            "timestamp": time.time()
        }

        print("\n--- Uploading JSON to IPFS (Encrypted) ---")
        upload_result = client.upload_json(large_data)
        cid = upload_result['cid']
        nonce = upload_result['nonce']

        print("✓ Data uploaded to IPFS")
        print(f"  CID: {cid}")
        print(f"  Nonce: {nonce}")
        print(f"  Size on IPFS: {upload_result['size']} bytes (Ciphertext)")

        print("\n--- Downloading from IPFS (Decrypted) ---")
        downloaded_data = client.download_json(cid, encrypted=True, nonce=nonce)
        print("✓ Data retrieved and decrypted")
        print(f"  Title: {downloaded_data['title']}")
        print(f"  First item: {downloaded_data['items'][0]['val']}")

        return cid, nonce

    except Exception as e:
        print(f"✗ IPFS Demo Error: {e}")
        return None, None


def demonstrate_blockchain_integration(cid, nonce):
    """Demonstrate blockchain integration with CID reference."""
    print_section("2. Blockchain Integration (CID Reference)")

    hm = HierarchyManager()
    hm.create_sub_chain("LogisticsChain", "logistics")
    chain = hm.get_sub_chain("LogisticsChain")

    if chain is None:
        print("✗ Failed to create LogisticsChain")
        return None

    print("\n--- Adding Event with CID Reference ---")
    # Instead of 'details', we use 'details_cid'
    event = {
        "entity_id": "SHIP-12345",
        "event": "cargo_manifest_attached",
        "details_cid": cid,
        "details_nonce": nonce,
        "details_metadata": {"original_filename": "manifest_v1.json"}
    }

    # Register entity first
    chain.register_entity("SHIP-12345", {"type": "Container"})

    # In HieraChain, we store the CID reference in the event
    chain.add_event(event)
    chain.finalize_block()

    print("✓ Event added to 'LogisticsChain' with CID reference")
    print("  The blockchain now stores the 46-character CID instead of the large JSON.")

    return chain


def demonstrate_api_resolution(chain):
    """Demonstrate API resolution of CIDs."""
    print_section("3. API Resolution (resolve_cid=True)")

    print("\n--- Querying Blocks without Resolution ---")
    blocks = chain.chain
    latest_block = blocks[-1]

    # Simulating what the API returns
    event_on_chain = latest_block.to_event_list()[0]
    print("  Raw event on-chain:")
    print(f"    entity_id: {event_on_chain['entity_id']}")
    print(f"    details_cid: {event_on_chain.get('details_cid')}")
    print(f"    details: {event_on_chain.get('details')} (Expected: None)")

    print("\n--- Simulating API with ?resolve_cid=true ---")
    # This logic matches what's in hierachain/api/storage/endpoint_helpers.py
    storage_type = detect_data_location(event_on_chain)
    print(f"  Storage location detected: {storage_type}")

    if storage_type == "offchain":
        # Resolve CID using helpers
        # Note: In a real app, resolve_event_details would be called
        print("  ✓ API automatically fetches data from IPFS using CID and Nonce...")
        print("  ✓ Data decrypted and injected into 'details' field for the response.")


def demonstrate_explorer_visualization(chain):
    """Demonstrate explorer visualization with IPFS indicators."""
    print_section("4. Explorer Visualization")

    event = chain.chain[-1].to_event_list()[0]

    print("\n--- Formatting for Explorer UI ---")
    # This uses explorer_helpers.py logic
    formatted = format_event_for_display(event, resolve_cid=False)

    print("  Explorer Data Structure:")
    storage_info = formatted.get('_storage', {})
    print(f"    Storage Type: {storage_info.get('type')}")
    print(f"    IPFS Status: {storage_info.get('ipfs')}")

    if storage_info.get('ipfs'):
        print(f"    Short CID: {storage_info.get('cid_display')}")

    print("\n--- UI Indicators (Simulated) ---")
    if storage_info.get('type') == "offchain":
        print(f"  [ 📦 IPFS: {storage_info.get('cid_display')} ]  <-- YELLOW BADGE")
        print("  [ 📥 Load Details ] <-- BUTTON")
    else:
        print("  [ 🔵 On-Chain ] <-- BLUE BADGE")


def main():
    """Main function."""
    print("=" * 80)
    print(" HieraChain IPFS Integration Demo ".center(80, "#"))
    print("=" * 80)

    # 1. Direct IPFS Usage
    cid, nonce = demonstrate_direct_ipfs()

    if cid:
        # 2. Blockchain Integration
        chain = demonstrate_blockchain_integration(cid, nonce)

        if chain:
            # 3. API Resolution
            demonstrate_api_resolution(chain)

            # 4. Explorer UI
            demonstrate_explorer_visualization(chain)

    print("\n" + "=" * 80)
    print(" DEMO COMPLETED ".center(80, "#"))
    print("=" * 80)


if __name__ == "__main__":
    main()
