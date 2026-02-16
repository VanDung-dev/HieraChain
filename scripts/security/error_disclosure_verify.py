"""
Probe script to verify that error messages do not disclose sensitive information.
Checks for stack traces, internal paths, and raw exception messages.
"""

import asyncio
import re
import sys
import httpx
from base_probe import BaseProbe, parse_args, run_probe, ProbeResult


def _check_stack_trace(result: ProbeResult, body: str) -> bool:
    stack_trace_patterns = [
        r'Traceback \(most recent call last\):',
        r'File ".*", line \d+, in',
        r'NameError:',
        r'TypeError:',
        r'ValueError:',
        r'ImportError:',
        r'ModuleNotFoundError:',
        r'AttributeError:',
    ]
    for pattern in stack_trace_patterns:
        if re.search(pattern, body):
            result.add_finding(
                "critical",
                f"Possible Stack Trace disclosure matching '{pattern}'",
                {"snippet": body[:200] + "..."},
            )
            return True
    return False


def _check_internal_paths(result: ProbeResult, body: str):
    path_patterns = [
        r"/usr/local/lib/python",
        r"/home/\w+/",
        r"[C-Z]:\\Users\\",
    ]
    for pattern in path_patterns:
        if re.search(pattern, body, re.IGNORECASE):
            result.add_finding(
                "high",
                "Possible Internal Path disclosure",
                {"snippet": body[:200]},
            )


def _check_error_content_type(
        result: ProbeResult,
    response: httpx.Response,
    body: str,
    found_trace: bool,
):
    if response.status_code < 400:
        return
    if response.headers.get("content-type") != "application/json":
        result.add_finding(
            "medium",
            f"Error response content-type is not JSON: {response.headers.get('content-type')}",
            {"body_preview": body[:100]},
        )
    if not found_trace and not result.findings:
        result.add_finding(
            "info",
            "Error message appears sanitized (no stack trace found).",
        )


def _analyze_error_response(
        result: ProbeResult, response: httpx.Response
):
    """Analyze response body for sensitive patterns."""
    body = response.text
    found_trace = _check_stack_trace(result, body)
    _check_internal_paths(result, body)
    if "fastapi" in body.lower() or "starlette" in body.lower():
        pass
    _check_error_content_type(result, response, body, found_trace)


class ErrorDisclosureProbe(BaseProbe):
    async def run(self):
        print(f"[*] Starting Error Disclosure Probe against {self.base_url}...", file=sys.stderr)
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            await self.check_404_handling(client)
            await self.check_422_validation(client)
            await self.check_500_method_not_allowed(client)
            # Add more specific error triggers if needed (e.g., malformed JSON)

    async def check_404_handling(self, client):
        """Check how the server handles non-existent resources."""
        endpoint = "/api/v1/non_existent_resource_xyz_123"
        result = ProbeResult("404 Error Handling", endpoint)
        
        try:
            start = asyncio.get_running_loop().time()
            response = await client.get(
                f"{self.base_url}{endpoint}", 
                headers=self.get_headers()
            )
            result.elapsed_ms = (asyncio.get_running_loop().time() - start) * 1000
            result.status_code = response.status_code
            
            _analyze_error_response(result, response)
            
        except Exception as e:
            result.error = str(e)
            result.add_finding("info", f"Connection error: {e}")
        
        self.results.append(result)

    async def check_422_validation(self, client):
        """Check 422 validation errors for sensitive info."""
        # Endpoint that expects specific data (e.g., POST /channels)
        endpoint = "/api/v2/channels"
        result = ProbeResult("422 Validation Error", endpoint)
        
        try:
            # Send empty body where JSON is expected
            start = asyncio.get_running_loop().time()
            response = await client.post(
                f"{self.base_url}{endpoint}", 
                headers=self.get_headers(),
                json={} # Missing required fields
            )
            result.elapsed_ms = (asyncio.get_running_loop().time() - start) * 1000
            result.status_code = response.status_code
            
            # 422 is expected, but check content
            _analyze_error_response(result, response)
            
        except Exception as e:
            result.error = str(e)
        
        self.results.append(result)

    async def check_500_method_not_allowed(self, client):
        """Trigger potential ledger errors (like 405) to check handling."""
        endpoint = "/api/v2/channels" # Supports POST, GET
        result = ProbeResult("Method Not Allowed Handling", endpoint)
        
        try:
            # DELETE method might not be implemented or allowed
            start = asyncio.get_running_loop().time()
            response = await client.delete(
                f"{self.base_url}{endpoint}", 
                headers=self.get_headers()
            )
            result.elapsed_ms = (asyncio.get_running_loop().time() - start) * 1000
            result.status_code = response.status_code
            
            _analyze_error_response(result, response)
            
        except Exception as e:
            result.error = str(e)
        
        self.results.append(result)


if __name__ == "__main__":
    args = parse_args("Verify error handling and information disclosure")
    asyncio.run(run_probe(ErrorDisclosureProbe, args))
