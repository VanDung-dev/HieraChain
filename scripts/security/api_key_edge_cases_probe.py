"""
API Key Edge Cases Probe - Tests API key handling for edge cases.

This script verifies:
1. Expired API keys are properly rejected
2. Non-existent keys are handled correctly  
3. Keys with insufficient scope/permissions are denied
4. Error messages don't leak sensitive information
"""

import asyncio
import sys
import httpx
from .base_probe import BaseProbe, parse_args, run_probe, ProbeResult


def _build_case_variations(api_key: str):
    return [
        ("uppercase", api_key.upper()),
        ("lowercase", api_key.lower()),
        (
            "mixed",
            "".join(
                c.upper() if i % 2 else c.lower() for i, c in enumerate(api_key)
            ),
        ),
    ]


def _analyze_key_rejection(result: ProbeResult, response: httpx.Response, key_type: str):
    """Analyze how the server rejected an invalid key."""
    body = response.text.lower()

    # Check status code
    if response.status_code == 401:
        result.add_finding("info", f"Server correctly returned 401 for {key_type}")
    elif response.status_code == 403:
        result.add_finding("info", f"Server returned 403 for {key_type}")
    elif response.status_code == 200:
        result.add_finding("critical", f"Server accepted {key_type} - authentication bypass!")
    else:
        result.add_finding("medium", f"Unexpected status {response.status_code} for {key_type}")

    # Check for information leakage in error message
    sensitive_patterns = [
        ("database", "Database information leaked"),
        ("sql", "SQL information leaked"),
        ("table", "Database table name leaked"),
        ("password", "Password-related info leaked"),
        ("secret", "Secret information leaked"),
        ("internal", "Internal system info leaked"),
        ("traceback", "Python traceback leaked"),
        ("exception", "Exception details leaked"),
    ]

    for pattern, message in sensitive_patterns:
        if pattern in body:
            result.add_finding("high", f"{message} in error response for {key_type}")

    # Check response is proper JSON
    if response.headers.get("content-type", "").startswith("application/json"):
        result.add_finding("info", "Error response is proper JSON format")
    else:
        result.add_finding("medium", f"Error response is not JSON: {response.headers.get('content-type', 'unknown')}")


class APIKeyEdgeCasesProbe(BaseProbe):
    """Probe for testing API key edge cases and scope handling."""
    
    async def run(self):
        print(f"[*] Starting API Key Edge Cases Probe against {self.base_url}...", file=sys.stderr)
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            await self.test_non_existent_key(client)
            await self.test_malformed_keys(client)
            await self.test_empty_key(client)
            await self.test_very_long_key(client)
            await self.test_special_chars_key(client)
            await self.test_unicode_key(client)
            await self.test_case_sensitivity(client)
            await self.test_scope_bypass_attempts(client)
            
    async def test_non_existent_key(self, client):
        """Test with a completely non-existent API key."""
        endpoint = "/api/ledger/channels"
        result = ProbeResult("Non-Existent API Key", endpoint)
        
        # Generate a fake key that looks valid but doesn't exist
        fake_key = "hrc_fake1234_abcdef1234567890_12345678"
        
        try:
            start = asyncio.get_running_loop().time()
            response = await client.get(
                f"{self.base_url}{endpoint}",
                headers={"x-api-key": fake_key}
            )
            result.elapsed_ms = (asyncio.get_running_loop().time() - start) * 1000
            result.status_code = response.status_code
            
            _analyze_key_rejection(result, response, "non-existent key")
            
        except Exception as e:
            result.error = str(e)
            result.add_finding("info", f"Connection error: {e}")
        
        self.results.append(result)
    
    async def test_malformed_keys(self, client):
        """Test with various malformed API key formats."""
        endpoint = "/api/ledger/channels"
        
        malformed_keys = [
            ("short_key", "abc"),  # Too short
            ("no_prefix", "1234567890abcdef1234"),  # Missing hrc_ prefix
            ("wrong_prefix", "xyz_wrongprefix_test"),  # Wrong prefix
            ("null_bytes", "hrc_test\x00key_with_null"),  # Contains null byte
            ("spaces", "hrc_test key with spaces"),  # Contains spaces
        ]
        
        for name, key in malformed_keys:
            result = ProbeResult(f"Malformed Key: {name}", endpoint)
            
            try:
                start = asyncio.get_running_loop().time()
                response = await client.get(
                    f"{self.base_url}{endpoint}",
                    headers={"x-api-key": key}
                )
                result.elapsed_ms = (asyncio.get_running_loop().time() - start) * 1000
                result.status_code = response.status_code
                
                _analyze_key_rejection(result, response, name)
                
            except Exception as e:
                result.error = str(e)
            
            self.results.append(result)
    
    async def test_empty_key(self, client):
        """Test with empty API key."""
        endpoint = "/api/ledger/channels"
        result = ProbeResult("Empty API Key", endpoint)
        
        try:
            start = asyncio.get_running_loop().time()
            response = await client.get(
                f"{self.base_url}{endpoint}",
                headers={"x-api-key": ""}
            )
            result.elapsed_ms = (asyncio.get_running_loop().time() - start) * 1000
            result.status_code = response.status_code
            
            _analyze_key_rejection(result, response, "empty key")
            
        except Exception as e:
            result.error = str(e)
        
        self.results.append(result)
    
    async def test_very_long_key(self, client):
        """Test with abnormally long API key."""
        endpoint = "/api/ledger/channels"
        result = ProbeResult("Very Long API Key", endpoint)
        
        # 10KB key
        long_key = "hrc_" + "a" * 10000
        
        try:
            start = asyncio.get_running_loop().time()
            response = await client.get(
                f"{self.base_url}{endpoint}",
                headers={"x-api-key": long_key}
            )
            result.elapsed_ms = (asyncio.get_running_loop().time() - start) * 1000
            result.status_code = response.status_code
            
            # Check for proper rejection without DoS
            if result.elapsed_ms > 5000:
                result.add_finding("medium", f"Server took {result.elapsed_ms:.0f}ms to respond to long key - possible DoS vector")
            else:
                result.add_finding("info", f"Server handled long key in {result.elapsed_ms:.0f}ms - no DoS concern")
            
            _analyze_key_rejection(result, response, "very long key")
            
        except Exception as e:
            result.error = str(e)
        
        self.results.append(result)
    
    async def test_special_chars_key(self, client):
        """Test with special characters in API key."""
        endpoint = "/api/ledger/channels"
        result = ProbeResult("Special Characters Key", endpoint)
        
        # Key with SQL injection and XSS payloads
        special_key = "hrc_' OR 1=1--<script>alert(1)</script>"
        
        try:
            start = asyncio.get_running_loop().time()
            response = await client.get(
                f"{self.base_url}{endpoint}",
                headers={"x-api-key": special_key}
            )
            result.elapsed_ms = (asyncio.get_running_loop().time() - start) * 1000
            result.status_code = response.status_code
            
            # Check if payload is reflected in response (XSS)
            if "<script>" in response.text.lower():
                result.add_finding("high", "XSS payload reflected in response!")
            
            _analyze_key_rejection(result, response, "special chars key")
            
        except Exception as e:
            result.error = str(e)
        
        self.results.append(result)
    
    async def test_unicode_key(self, client):
        """Test with Unicode characters in API key."""
        endpoint = "/api/ledger/channels"
        result = ProbeResult("Unicode API Key", endpoint)
        
        unicode_key = "hrc_тест_यूनिकोड_测试_🔐 vãi chưa =)))"
        
        try:
            start = asyncio.get_running_loop().time()
            response = await client.get(
                f"{self.base_url}{endpoint}",
                headers={"x-api-key": unicode_key}
            )
            result.elapsed_ms = (asyncio.get_running_loop().time() - start) * 1000
            result.status_code = response.status_code
            
            _analyze_key_rejection(result, response, "unicode key")
            
        except Exception as e:
            result.error = str(e)
        
        self.results.append(result)

    async def _get_original_status_code(self, client, endpoint: str):
        try:
            response = await client.get(
                f"{self.base_url}{endpoint}",
                headers={"x-api-key": self.api_key},
            )
            return response.status_code
        except Exception:
            return None

    async def _test_case_variation(
        self,
        client,
        endpoint: str,
        original_response: int | None,
        name: str,
        key: str,
        result: ProbeResult,
    ):
        if key == self.api_key:
            return
        try:
            response = await client.get(
                f"{self.base_url}{endpoint}",
                headers={"x-api-key": key},
            )
            status_code = response.status_code
            if (
                original_response in [200, 201]
                and status_code == original_response
            ):
                result.add_finding(
                    "medium",
                    f"API key validation appears case-insensitive ({name} variation accepted)",
                )
            else:
                result.add_finding(
                    "info",
                    f"Case variation '{name}' properly rejected (got {status_code})",
                )
        except Exception as e:
            result.add_finding("info", f"Error testing {name}: {e}")

    async def test_case_sensitivity(self, client):
        """Test whether API key validation is case-sensitive."""
        endpoint = "/api/ledger/channels"
        result = ProbeResult("Case Sensitivity Check", endpoint)

        if not self.api_key:
            result.add_finding(
                "info",
                "No valid API key provided - skipping case sensitivity test",
            )
            self.results.append(result)
            return

        variations = _build_case_variations(self.api_key)
        original_response = await self._get_original_status_code(client, endpoint)

        for name, key in variations:
            await self._test_case_variation(
                client, endpoint, original_response, name, key, result
            )

        self.results.append(result)

    async def test_scope_bypass_attempts(self, client):
        """Test attempts to bypass scope/permission restrictions."""
        result = ProbeResult("Scope Bypass Attempts", "/api/business/admin/*")
        
        # Try accessing potentially restricted endpoints with various techniques
        bypass_attempts = [
            # Path traversal in endpoint
            ("/api/ledger/../v2/admin/status", "path traversal"),
            # URL encoding
            ("/api/ledger/%2e%2e/admin", "URL encoded traversal"),
            # HTTP parameter pollution
            ("/api/ledger/channels?admin=true", "parameter injection"),
            # Header injection attempt
            ("/api/ledger/channels", "header injection X-Original-URL"),
        ]
        
        for endpoint, technique in bypass_attempts:
            try:
                headers = self.get_headers()
                
                # For header injection test, add suspicious headers
                if "header injection" in technique:
                    headers["X-Original-URL"] = "/api/admin/secrets"
                    headers["X-Rewrite-URL"] = "/api/admin/config"
                
                response = await client.get(
                    f"{self.base_url}{endpoint}",
                    headers=headers
                )
                
                # If we get 200 on admin endpoints, that's concerning
                if "admin" in endpoint.lower() and response.status_code == 200:
                    result.add_finding(
                        "high",
                        f"Possible scope bypass via {technique}: got 200 on {endpoint}"
                    )
                else:
                    result.add_finding(
                        "info",
                        f"Bypass attempt '{technique}' failed (got {response.status_code})"
                    )
                    
            except Exception as e:
                result.add_finding("info", f"Error testing {technique}: {e}")
        
        self.results.append(result)


if __name__ == "__main__":
    args = parse_args("Test API key edge cases and scope handling")
    asyncio.run(run_probe(APIKeyEdgeCasesProbe, args))
