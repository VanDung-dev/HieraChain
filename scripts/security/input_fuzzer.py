"""
Input Fuzzer Probe

Fuzzes API endpoints with potentially dangerous inputs:
- SQL injection patterns
- Path traversal sequences
- XSS payloads
- JSON bombs (nested/oversized)
- Unicode/null bytes
- Type confusion
"""

import asyncio
import time
import httpx
from typing import Any
from .base_probe import BaseProbe, ProbeResult, parse_args, run_probe


# Fuzz payloads by category
FUZZ_PAYLOADS = {
    "sql_injection": [
        "' OR '1'='1",
        "'; DROP TABLE chains; --",
        "1; SELECT * FROM users",
        "' UNION SELECT NULL--",
        "admin'--",
    ],
    "nosql_injection": [
        '{"$gt": ""}',
        '{"$ne": null}',
        '{"$where": "1==1"}',
    ],
    "path_traversal": [
        "../../../etc/passwd",
        "..\\..\\..\\windows\\system32\\config\\sam",
        "....//....//....//etc/passwd",
        "%2e%2e%2f%2e%2e%2f",
        "..%252f..%252f",
    ],
    "xss": [
        "<script>alert(1)</script>",
        "javascript:alert(1)",
        "<img src=x onerror=alert(1)>",
        "'-alert(1)-'",
    ],
    "command_injection": [
        "; ls -la",
        "| cat /etc/passwd",
        "$(whoami)",
        "`id`",
    ],
    "special_chars": [
        "\x00",           # Null byte
        "\u202e",         # Right-to-left override
        "\r\n\r\n",       # CRLF injection
        "{{7*7}}",        # SSTI
        "${7*7}",         # Template injection
    ],
    "type_confusion": [
        True,
        False,
        None,
        12345,
        -1,
        0,
        [],
        {},
    ],
}

# Endpoints to fuzz (both v1 and v2)
FUZZ_TARGETS = [
    # API v1
    {
        "method": "GET",
        "endpoint": "/api/ledger/chains/{param}",
        "param_location": "path",
    },
    {
        "method": "GET",
        "endpoint": "/api/ledger/trace/{param}",
        "param_location": "path",
    },
    {
        "method": "POST",
        "endpoint": "/api/ledger/chains/test/events",
        "param_location": "body",
        "body_template": {
            "entity_id": "{param}",
            "event_type": "test",
            "data": {}
        }
    },
    # API v2
    {
        "method": "GET",
        "endpoint": "/api/business/channels/{param}",
        "param_location": "path",
    },
    {
        "method": "GET",
        "endpoint": "/api/business/organizations/{param}",
        "param_location": "path",
    },
    {
        "method": "POST",
        "endpoint": "/api/business/channels",
        "param_location": "body",
        "body_template": {
            "channel_id": "{param}",
            "channel_name": "test",
            "members": []
        }
    },
]


def _analyze_response(
        result: ProbeResult,
    response: httpx.Response,
    category: str,
    payload: str
):
    """Analyze response for signs of vulnerability."""
    status = response.status_code
    body = response.text[:1000] if response.text else ""

    # Server error could indicate injection success
    if status == 500:
        result.add_finding(
            severity="medium",
            message=f"Server error triggered by {category} payload",
            details={"payload": payload[:100], "response": body[:200]}
        )

    # Check for reflection (potential XSS)
    if category == "xss" and payload in body:
        result.add_finding(
            severity="high",
            message="Input reflected in response (potential XSS)",
            details={"payload": payload}
        )

    # Check for SQL error messages
    sql_errors = ["syntax error", "mysql", "postgresql", "sqlite", "ora-"]
    if any(err in body.lower() for err in sql_errors):
        result.add_finding(
            severity="high",
            message="SQL error message in response (potential SQL injection)",
            details={"payload": payload, "response": body[:300]}
        )

    # Check for path disclosure
    path_indicators = ["/etc/", "C:\\", "\\windows\\", "/var/", "/home/"]
    if any(ind in body for ind in path_indicators):
        result.add_finding(
            severity="medium",
            message="File path disclosed in response",
            details={"response": body[:300]}
        )

    # If 4xx/200, likely handled properly
    if status in [400, 401, 403, 404, 422] or (status == 200 and not result.findings):
        result.add_finding(
            severity="info",
            message=f"Input handled with status {status}"
        )


class InputFuzzerProbe(BaseProbe):
    """Probe for input validation vulnerabilities."""
    
    async def run(self):
        """Run all fuzzing tests."""
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            follow_redirects=False
        ) as client:
            for target in FUZZ_TARGETS:
                for category, payloads in FUZZ_PAYLOADS.items():
                    for payload in payloads:
                        await self._fuzz_endpoint(client, target, category, payload)
            
            # Also test JSON bombs
            await self._test_json_bombs(client)
    
    async def _fuzz_endpoint(
        self,
        client: httpx.AsyncClient,
        target: dict,
        category: str,
        payload: Any
    ):
        """Fuzz a single endpoint with a payload."""
        # Convert payload to string for path/query params
        payload_str = str(payload) if not isinstance(payload, str) else payload
        
        result = ProbeResult(
            name=f"fuzz_{category}_{target['endpoint'][:20]}",
            endpoint=target["endpoint"]
        )
        
        try:
            method = target["method"]
            
            if target["param_location"] == "path":
                # Insert payload into path
                endpoint = target["endpoint"].replace("{param}", payload_str)
                start = time.time()
                response = await client.request(
                    method, 
                    endpoint, 
                    headers=self.get_headers()
                )
            elif target["param_location"] == "body":
                # Insert payload into body
                endpoint = target["endpoint"]
                body = self._inject_payload(target.get("body_template", {}), payload)
                start = time.time()
                response = await client.request(
                    method,
                    endpoint,
                    headers=self.get_headers(),
                    json=body
                )
            else:
                return
            
            result.elapsed_ms = (time.time() - start) * 1000
            result.status_code = response.status_code
            
            # Analyze response for vulnerabilities
            _analyze_response(result, response, category, payload_str)
            
        except httpx.RequestError as e:
            result.error = str(e)
        except Exception as e:
            result.error = f"Unexpected: {str(e)}"
        
        self.results.append(result)
    
    def _inject_payload(self, template: dict, payload: Any) -> dict:
        """Inject payload into body template."""
        result = {}
        for key, value in template.items():
            if isinstance(value, str) and "{param}" in value:
                result[key] = value.replace("{param}", str(payload)) if isinstance(payload, str) else payload
            elif isinstance(value, dict):
                result[key] = self._inject_payload(value, payload)
            else:
                result[key] = value
        return result

    async def _test_json_bombs(self, client: httpx.AsyncClient):
        """Test with JSON bombs (deeply nested, oversized)."""
        # Deeply nested JSON
        deep_nested = {"a": {}}
        current = deep_nested["a"]
        for _ in range(50):
            current["b"] = {}
            current = current["b"]
        
        result = ProbeResult(
            name="json_bomb_nested",
            endpoint="/api/ledger/chains/test/events"
        )
        
        try:
            start = time.time()
            response = await client.post(
                "/api/ledger/chains/test/events",
                headers=self.get_headers(),
                json={
                    "entity_id": "test",
                    "event_type": "bomb",
                    "data": deep_nested
                }
            )
            result.elapsed_ms = (time.time() - start) * 1000
            result.status_code = response.status_code
            
            if response.status_code == 500:
                result.add_finding(
                    severity="medium",
                    message="Server error on deeply nested JSON",
                    details={"depth": 50}
                )
            elif result.elapsed_ms > 5000:
                result.add_finding(
                    severity="medium",
                    message="Slow response on nested JSON (potential DoS)",
                    details={"elapsed_ms": result.elapsed_ms}
                )
            else:
                result.add_finding(
                    severity="info",
                    message="Nested JSON handled properly"
                )
                
        except httpx.RequestError as e:
            result.error = str(e)
        
        self.results.append(result)
        
        # Oversized payload
        result2 = ProbeResult(
            name="json_bomb_oversized",
            endpoint="/api/ledger/chains/test/events"
        )
        
        try:
            large_data = "X" * (1024 * 1024)  # 1MB
            start = time.time()
            response = await client.post(
                "/api/ledger/chains/test/events",
                headers=self.get_headers(),
                json={
                    "entity_id": "test",
                    "event_type": "oversized",
                    "data": {"payload": large_data}
                }
            )
            result2.elapsed_ms = (time.time() - start) * 1000
            result2.status_code = response.status_code
            
            if response.status_code == 413:
                result2.add_finding(
                    severity="info",
                    message="Oversized payload correctly rejected (413)"
                )
            elif response.status_code == 200:
                result2.add_finding(
                    severity="low",
                    message="Large payload accepted (1MB) - check payload limits",
                    details={"size_bytes": len(large_data)}
                )
            else:
                result2.add_finding(
                    severity="info",
                    message=f"Oversized payload returned status {response.status_code}"
                )
                
        except httpx.RequestError as e:
            result2.error = str(e)
        
        self.results.append(result2)


if __name__ == "__main__":
    args = parse_args("Fuzz API endpoints with dangerous inputs")
    asyncio.run(run_probe(InputFuzzerProbe, args))
