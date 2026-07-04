"""
Probe script to verify Business Logic Consistency.
Simulates a full workflow: Create Channel -> Create Private Collection -> (Future: Proof Submission).
Checks for logical errors, state inconsistencies, or order-dependent vulnerabilities.
"""

import sys
import httpx
import asyncio
import time
from .base_probe import BaseProbe, parse_args, run_probe, ProbeResult


class BusinessLogicProbe(BaseProbe):
    async def run(self):
        print(f"[*] Starting Business Logic Probe against {self.base_url}...", file=sys.stderr)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            await self.check_channel_collection_workflow(client)
            # Add more workflows as features are implemented

    async def check_channel_collection_workflow(self, client):
        """
        Workflow:
        1. Create Channel (Org A <-> Org B)
        2. Create Private Collection in that channel
        3. Try to access collection from outside (simulated logic check)
        """
        ts = int(time.time())
        channel_id = f"test-channel-{ts}"
        flow_name = "Channel -> Collection Flow"
        result = ProbeResult(flow_name, "/api/business/channels")
        
        try:
            # Step 1: Create Channel
            headers = self.get_headers()
            channel_data = {
                "channel_id": channel_id,
                "organizations": ["OrgA", "OrgB"],
                "policy": {
                    "read": "ANY",
                    "write": "ANY",
                    "endorsement": "MAJORITY"
                }
            }
            resp1 = await client.post(f"{self.base_url}/api/business/channels", json=channel_data, headers=headers)
            
            if resp1.status_code not in [200, 201]:
                result.add_finding("high", f"Step 1 Failed: Create Channel returned {resp1.status_code}")
                self.results.append(result)
                return

            # Step 2: Create Private Collection
            collection_name = f"collection-{ts}"
            collection_data = {
                "name": collection_name,
                "members": ["OrgA"],
                "config": {"encryption": "AES"}
            }
            resp2 = await client.post(
                f"{self.base_url}/api/business/channels/{channel_id}/private-collections",
                json=collection_data,
                headers=headers
            )
            
            if resp2.status_code not in [200, 201]:
                result.add_finding("high", f"Step 2 Failed: Create Private Collection returned {resp2.status_code}")
            
            # Step 3: Verify Integrity (Simulated)
            resp3 = await client.post(
                f"{self.base_url}/api/business/channels/NON_EXISTENT_CHANNEL/private-collections",
                json=collection_data,
                headers=headers
            )
            if resp3.status_code != 404:
                result.add_finding("medium", f"Step 3 Failed: API should return 404 for non-existent channel, got {resp3.status_code}")
            else:
                result.add_finding("info", "Step 3 Passed: Correctly blocked creation in orphaned channel.")
                
            if not result.findings:
                result.add_finding("info", "Full workflow completed successfully.")

        except Exception as e:
            result.error = str(e)
            result.add_finding("high", f"Workflow exception: {e}")

        self.results.append(result)

if __name__ == "__main__":
    args = parse_args("Verify Business Logic and Workflows")
    asyncio.run(run_probe(BusinessLogicProbe, args))
