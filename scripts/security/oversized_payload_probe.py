"""
Probe script to test large payload handling (Oversized Body).
"""

import sys
import httpx
import asyncio
from .base_probe import BaseProbe, parse_args, run_probe, ProbeResult


class OversizedPayloadProbe(BaseProbe):
    async def run(self):
        print(f"[*] Starting Oversized Payload Probe against {self.base_url}...", file=sys.stderr)
        async with httpx.AsyncClient(timeout=30.0) as client: # Longer timeout for upload
            await self.check_large_body(client, size_mb=10)

    async def check_large_body(self, client, size_mb: int):
        """Send a large dummy body."""
        endpoint = "/api/business/channels"
        result = ProbeResult(f"Oversized Payload ({size_mb}MB)", endpoint)
        
        # Generator for streaming upload if needed, but httpx handles bytes easily
        # Creating a large string in memory might be costly but fine for 10MB
        payload = b"A" * (size_mb * 1024 * 1024)
        
        try:
            # We use content-type application/json but send garbage bytes to test size limit check *before* parsing
            headers = self.get_headers()
            
            response = await client.post(
                f"{self.base_url}{endpoint}",
                headers=headers,
                content=payload
            )
            result.status_code = response.status_code
            
            if response.status_code == 413:
                result.add_finding("info", "Server correctly returned 413 Payload Too Large")
            elif response.status_code == 200:
                result.add_finding("high", "Server ACCEPTED 10MB payload (Lack of size limit configuration?)")
            elif response.status_code == 422:
                result.add_finding("medium", "Server tried to parse 10MB payload (422), meaning it accepted the body size first.")
            else:
                result.add_finding("info", f"Server responded with {response.status_code}")

        except httpx.WriteTimeout:
            result.add_finding("info", "Write timeout sending data (Server might be slow reading or dropping connection)")
        except Exception as e:
            result.error = str(e)
            result.add_finding("info", f"Error during transmission: {e}")

        self.results.append(result)

if __name__ == "__main__":
    args = parse_args("Verify request body size limits")
    asyncio.run(run_probe(OversizedPayloadProbe, args))
