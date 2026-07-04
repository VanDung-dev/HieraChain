"""
Probe script to test JSON parsing vulnerabilities (Nested JSON / Billion Laughs).
"""

import sys
import httpx
import asyncio
from .base_probe import BaseProbe, parse_args, run_probe, ProbeResult


class JsonBombProbe(BaseProbe):
    async def run(self):
        print(f"[*] Starting JSON Bomb Probe against {self.base_url}...", file=sys.stderr)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            await self.check_deeply_nested_json(client)
            await self.check_large_array_json(client)

    async def check_deeply_nested_json(self, client):
        """Send deeply nested JSON to check for RecursionError or stack overflow."""
        endpoint = "/api/business/channels" # A generic POST endpoint
        result = ProbeResult("Deeply Nested JSON", endpoint)
        
        depth = 2000 # Python default recursion limit is usually 1000
        nested_data = {}
        current = nested_data
        for _ in range(depth):
            current["a"] = {}
            current = current["a"]
            
        try:
            response = await client.post(
                f"{self.base_url}{endpoint}",
                headers=self.get_headers(),
                json=nested_data
            )
            result.status_code = response.status_code
            
            if response.status_code == 500:
                result.add_finding("high", "Server returned 500 for nested JSON (Possible RecursionError/Crash)")
            elif response.status_code in [422, 400, 413]:
                result.add_finding("info", f"Server handled nested JSON gracefully with {response.status_code}")
            else:
                result.add_finding("info", f"Server responded with {response.status_code}")
                
        except Exception as e:
            result.error = str(e)
            result.add_finding("info", f"Client side error (potentially expected): {e}")

        self.results.append(result)

    async def check_large_array_json(self, client):
        """Send JSON with a massive array."""
        endpoint = "/api/business/channels"
        result = ProbeResult("Large JSON Array", endpoint)
        
        # Create a large list
        large_list = [i for i in range(100000)] # 100k items
        payload = {"data": large_list}
        
        try:
            response = await client.post(
                f"{self.base_url}{endpoint}",
                headers=self.get_headers(),
                json=payload
            )
            result.status_code = response.status_code
            
            if response.status_code == 500:
                result.add_finding("medium", "Server returned 500 for large array (Possible DoS/Memory issue)")
            elif response.status_code == 413:
                result.add_finding("info", "Server correctly returned 413 Payload Too Large")
            else:
                result.add_finding("info", f"Server responded with {response.status_code}")

        except Exception as e:
            result.error = str(e)

        self.results.append(result)

if __name__ == "__main__":
    args = parse_args("Verify JSON parsing robustness")
    asyncio.run(run_probe(JsonBombProbe, args))
