"""
Demo script for HieraChain API.

This script demonstrates how to use the various API endpoints provided by the
HieraChain framework, showcasing functionality from all three API versions.
"""

import asyncio
import logging
import os
import sys
import time
from typing import Dict, Any

import httpx

# Add the project root to the path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from hierachain.security.key_manager import KeyManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Base URL for the API server
BASE_URL = "http://localhost:2661"

# API endpoints
V1_BASE = f"{BASE_URL}/api/v1"
V2_BASE = f"{BASE_URL}/api/v2"


class APIDemo:
    """Class to demonstrate API functionality."""

    def __init__(self):
        self.client = httpx.AsyncClient()
        self.api_key = None
        self.key_manager = KeyManager()

    async def setup_api_key(self):
        """Setup an API key for V3 endpoints."""
        # In a real scenario, you would have a proper key management system
        # For this demo, we'll generate a key and register it
        self.api_key = "demo-api-key-" + str(int(time.time()))
        logger.info(f"Generated demo API key: {self.api_key}")
        return self.api_key

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def _make_request(self, method: str, url: str, log_message: str, **kwargs) -> Dict[Any, Any]:
        """Helper method to make HTTP requests with standardized error handling."""
        logger.info(log_message)
        try:
            response = await self.client.request(method, url, **kwargs)
            result = response.json()
            logger.info(f"{log_message.split(':')[1].strip()} result: {result}")
            return result
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {log_message.lower()}: {e.response.status_code} - {e.response.text}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Error {log_message.lower()}: {e}")
            return {"error": str(e)}

    async def _make_simple_get_request(self, url: str, log_message: str) -> Dict[Any, Any]:
        """Helper method for simple GET requests."""
        return await self._make_request("GET", url, log_message)

    async def _make_simple_post_request(self, url: str, log_message: str, **kwargs) -> Dict[Any, Any]:
        """Helper method for simple POST requests."""
        return await self._make_request("POST", url, log_message, **kwargs)

    # API v1 Methods
    async def demo_health_check_v1(self) -> Dict[Any, Any]:
        """Demo the v1 health check endpoint."""
        return await self._make_simple_get_request(f"{V1_BASE}/health", "=== Demo: API v1 Health Check ===")

    async def demo_create_sub_chain(self, chain_name: str) -> Dict[Any, Any]:
        """Demo creating a sub-chain."""
        result = await self._make_simple_post_request(
            f"{V1_BASE}/chains/{chain_name}/create",
            f"=== Demo: Create Sub-chain '{chain_name}' ===",
            params={"chain_type": "generic"}
        )
        # Wait a bit to ensure chain is properly initialized
        await asyncio.sleep(0.5)
        return result

    async def demo_add_event(self, chain_name: str, event_data: Dict) -> Dict[Any, Any]:
        """Demo adding an event to a sub-chain."""
        return await self._make_simple_post_request(
            f"{V1_BASE}/chains/{chain_name}/events",
            f"=== Demo: Add Event to '{chain_name}' ===",
            json=event_data
        )

    async def demo_submit_proof(self, chain_name: str) -> Dict[Any, Any]:
        """Demo submitting proof from sub-chain to main chain."""
        logger.info(f"=== Demo: Submit Proof from '{chain_name}' ===")
        try:
            # First check if the chain exists
            list_response = await self.client.get(f"{V1_BASE}/chains")
            chains = list_response.json()
            chain_names = [chain['name'] for chain in chains]
            
            if chain_name not in chain_names:
                logger.warning(f"Chain '{chain_name}' not found. Available chains: {chain_names}")
                return {"error": f"Chain '{chain_name}' not found"}
            
            response = await self.client.post(
                f"{V1_BASE}/chains/{chain_name}/submit-proof"
            )
            result = response.json()
            logger.info(f"Submit proof result: {result}")
            return result
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error submitting proof: {e.response.status_code} - {e.response.text}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Error submitting proof: {e}")
            return {"error": str(e)}

    async def demo_list_chains(self) -> Dict[Any, Any]:
        """Demo listing all chains."""
        return await self._make_simple_get_request(f"{V1_BASE}/chains", "=== Demo: List Chains ===")

    async def demo_trace_entity(self, entity_id: str) -> Dict[Any, Any]:
        """Demo tracing an entity across chains."""
        return await self._make_simple_get_request(
            f"{V1_BASE}/entities/{entity_id}/trace",
            f"=== Demo: Trace Entity '{entity_id}' ==="
        )

    async def demo_get_chain_stats(self, chain_name: str) -> Dict[Any, Any]:
        """Demo getting chain statistics."""
        return await self._make_simple_get_request(
            f"{V1_BASE}/chains/{chain_name}/stats",
            f"=== Demo: Get Stats for '{chain_name}' ==="
        )

    # API v2 Methods
    async def demo_health_check_v2(self) -> Dict[Any, Any]:
        """Demo the v2 health check endpoint."""
        return await self._make_simple_get_request(f"{V2_BASE}/health", "=== Demo: API v2 Health Check ===")

    async def demo_create_channel(self, channel_data: Dict) -> Dict[Any, Any]:
        """Demo creating a channel."""
        return await self._make_simple_post_request(
            f"{V2_BASE}/channels",
            "=== Demo: Create Channel ===",
            json=channel_data
        )

    async def demo_create_private_collection(self, channel_id: str, collection_data: Dict) -> Dict[Any, Any]:
        """Demo creating a private data collection."""
        logger.info(f"=== Demo: Create Private Collection in '{channel_id}' ===")
        try:
            # First check if channel exists
            try:
                channel_response = await self.client.get(f"{V2_BASE}/channels/{channel_id}")
                if channel_response.status_code == 404:
                    logger.warning(f"Channel '{channel_id}' not found")
                    return {"error": f"Channel '{channel_id}' not found"}
            except (httpx.RequestError, httpx.TimeoutException, Exception):
                pass  # Continue anyway, might be a mock implementation
                
            response = await self.client.post(
                f"{V2_BASE}/channels/{channel_id}/private-collections",
                json=collection_data
            )
            result = response.json()
            logger.info(f"Create private collection result: {result}")
            return result
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error creating private collection: {e.response.status_code} - {e.response.text}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Error creating private collection: {e}")
            return {"error": str(e)}

    async def demo_add_private_data(self, data: Dict) -> Dict[Any, Any]:
        """Demo adding private data."""
        return await self._make_simple_post_request(
            f"{V2_BASE}/private-data",
            "=== Demo: Add Private Data ===",
            json=data
        )

    async def demo_create_contract(self, contract_data: Dict) -> Dict[Any, Any]:
        """Demo creating a domain contract."""
        return await self._make_simple_post_request(
            f"{V2_BASE}/contracts",
            "=== Demo: Create Contract ===",
            json=contract_data
        )

    async def demo_execute_contract(self, execution_data: Dict) -> Dict[Any, Any]:
        """Demo executing a domain contract."""
        return await self._make_simple_post_request(
            f"{V2_BASE}/contracts/execute",
            "=== Demo: Execute Contract ===",
            json=execution_data
        )

    async def demo_register_organization(self, org_data: Dict) -> Dict[Any, Any]:
        """Demo registering an organization."""
        return await self._make_simple_post_request(
            f"{V2_BASE}/organizations",
            "=== Demo: Register Organization ===",
            json=org_data
        )

    # API v3 Methods (simulated)
    async def demo_api_v3_features(self):
        """Demo API v3 features (simulated)."""
        logger.info("=== Demo: API v3 Features (Key Verification) ===")
        logger.info("API v3 provides key verification and access control mechanisms.")
        logger.info("In a real implementation, endpoints would be protected by API keys.")
        logger.info("Example usage:")
        logger.info("  - Protected endpoints require a valid 'x-api-key' header")
        logger.info("  - Keys can be checked for permissions and revocation status")
        logger.info("  - Resource-based access control is supported")

        # Simulate using an API key
        await self.setup_api_key()
        logger.info(f"Using API key for protected endpoints: {self.api_key}")


async def main():
    """Main demo function."""
    # Check if server is running
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_URL}/docs")
            if response.status_code != 200:
                logger.error(f"Server is not running at {BASE_URL}. Please start the server first.")
                return
        except Exception as e:
            logger.error(f"Cannot connect to server at {BASE_URL}. Error: {e}")
            logger.error("Please make sure the server is running.")
            return
    
    demo = APIDemo()
    
    # Small delay to ensure server is ready
    await asyncio.sleep(0.5)
    
    try:
        # Demo API v3 features first (as they provide security for other APIs)
        await demo.demo_api_v3_features()
        
        # Demo API v1 Health Check
        await demo.demo_health_check_v1()
        
        # Demo API v2 Health Check
        await demo.demo_health_check_v2()
        
        # Demo creating a sub-chain
        chain_name = "supply_chain_demo"
        await demo.demo_create_sub_chain(chain_name)
        
        # Wait a bit to ensure chain is created
        await asyncio.sleep(1)
        
        # Demo adding events to the sub-chain
        event1 = {
            "entity_id": "product_12345",
            "event_type": "creation",
            "details": {
                "product_name": "Demo Product",
                "manufacturer": "Demo Corp"
            }
        }
        await demo.demo_add_event(chain_name, event1)
        
        await asyncio.sleep(1)  # Small delay to ensure timestamp difference
        
        event2 = {
            "entity_id": "product_12345",
            "event_type": "quality_check",
            "details": {
                "checker": "QA Team",
                "result": "passed"
            }
        }
        await demo.demo_add_event(chain_name, event2)
        
        # Demo submitting proof
        await asyncio.sleep(1)
        await demo.demo_submit_proof(chain_name)
        
        # Demo listing chains
        await asyncio.sleep(0.5)
        await demo.demo_list_chains()
        
        # Demo listing chains
        await demo.demo_list_chains()
        
        # Demo tracing entity
        await demo.demo_trace_entity("product_12345")
        
        # Demo getting chain stats
        await demo.demo_get_chain_stats(chain_name)
        await demo.demo_get_chain_stats("main_chain")
        
        # Demo API v2 features
        # Create a channel
        channel_data = {
            "channel_id": "demo_channel",
            "organizations": ["org1", "org2"],
            "policy": {
                "read": "ANY",
                "write": "MAJORITY",
                "endorsement": "MAJORITY"
            }
        }
        await demo.demo_create_channel(channel_data)
        
        # Create a private collection
        collection_data = {
            "name": "private_data_demo",
            "members": ["org1", "org2"],
            "config": {
                "block_to_purge": 1000,
                "endorsement_policy": "MAJORITY"
            }
        }
        await demo.demo_create_private_collection("demo_channel", collection_data)
        
        # Add private data
        private_data = {
            "collection": "private_data_demo",
            "key": "secret_key_001",
            "value": {
                "sensitive_info": "confidential_data"
            },
            "event_metadata": {
                "entity_id": "data_entity_001",
                "event": "private_data_add",
                "timestamp": time.time()
            }
        }
        await demo.demo_add_private_data(private_data)
        
        # Create a contract
        contract_data = {
            "contract_id": "demo_contract_001",
            "version": "1.0",
            "implementation": "class DemoContract: pass",
            "metadata": {
                "description": "A demo contract"
            }
        }
        await demo.demo_create_contract(contract_data)
        
        # Execute a contract
        execution_data = {
            "contract_id": "demo_contract_001",
            "event": {
                "event": "contract_execution",
                "entity_id": "contract_exec_001",
                "timestamp": time.time()
            },
            "context": {
                "executor": "demo_user",
                "chain": "demo_chain"
            }
        }
        await demo.demo_execute_contract(execution_data)
        
        # Register an organization
        org_data = {
            "org_id": "demo_org",
            "ca_config": {
                "ca_url": "https://ca.example.com",
                "tls_cert": "cert_data_here"
            }
        }
        await demo.demo_register_organization(org_data)
        
        logger.info("\n=== Demo Completed Successfully ===")
        
    except Exception as e:
        logger.error(f"Error in demo: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        await demo.close()


if __name__ == "__main__":
    asyncio.run(main())