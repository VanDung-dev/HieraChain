"""
Authentication Bypass Probe

Tests various methods to bypass API authentication:
- Missing API key
- Empty/null API key
- Oversized API key (buffer overflow attempt)
- Header name variations (case sensitivity)
- Key in query string instead of header
- Invalid/malformed keys
"""

import asyncio
import time
import httpx
from .base_probe import BaseProbe, ProbeResult, parse_args


# Protected endpoints to test (both Ledger and business)
PROTECTED_ENDPOINTS = [
    # API Ledger
    ("GET", "/api/ledger/chains"),
    ("GET", "/api/ledger/health"),
    ("POST", "/api/ledger/chains/test/events"),
    # API business
    ("GET", "/api/business/health"),
    ("GET", "/api/business/channels/test-channel"),
    ("POST", "/api/business/channels"),
    ("POST", "/api/business/organizations"),
]

# Bypass techniques to try
BYPASS_TECHNIQUES = [
    {
        "name": "no_key",
        "description": "Request without API key",
        "headers": {},
    },
    {
        "name": "empty_key",
        "description": "Empty API key value",
        "headers": {"X-API-Key": ""},
    },
    {
        "name": "null_key",
        "description": "Null string as API key",
        "headers": {"X-API-Key": "null"},
    },
    {
        "name": "whitespace_key",
        "description": "Whitespace only API key",
        "headers": {"X-API-Key": "   "},
    },
    {
        "name": "oversized_key",
        "description": "Very long API key (10KB)",
        "headers": {"X-API-Key": "A" * 10240},
    },
    {
        "name": "lowercase_header",
        "description": "Lowercase header name",
        "headers": {"x-api-key": "test-key-123"},
    },
    {
        "name": "mixed_case_header",
        "description": "Mixed case header name",
        "headers": {"X-Api-Key": "test-key-123"},
    },
    {
        "name": "alternative_header",
        "description": "Alternative header name",
        "headers": {"Authorization": "Bearer test-token"},
    },
    {
        "name": "special_chars_key",
        "description": "API key with special characters",
        "headers": {"X-API-Key": "test<script>alert(1)</script>"},
    },
    {
        "name": "sql_injection_key",
        "description": "SQL injection in API key",
        "headers": {"X-API-Key": "test' OR '1'='1"},
    },
]


class AuthBypassProbe(BaseProbe):
    """Probe for authentication bypass vulnerabilities."""
    
    async def run(self):
        """Run all bypass attempts."""
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            follow_redirects=False
        ) as client:
            # First, check if auth is enabled
            await self._check_auth_status(client)
            
            # Then try bypass techniques
            for method, endpoint in PROTECTED_ENDPOINTS:
                for technique in BYPASS_TECHNIQUES:
                    await self._try_bypass(client, method, endpoint, technique)
    
    async def _check_auth_status(self, client: httpx.AsyncClient):
        """Check if authentication is currently enabled."""
        result = ProbeResult(
            name="auth_status_check",
            endpoint="/api/ledger/health"
        )
        
        try:
            # Try without any auth
            start = time.time()
            response = await client.get("/api/ledger/health")
            result.elapsed_ms = (time.time() - start) * 1000
            result.status_code = response.status_code
            
            if response.status_code == 200:
                result.add_finding(
                    severity="info",
                    message="Authentication appears to be DISABLED (health endpoint accessible without key)",
                    details={"recommendation": "Enable AUTH_ENABLED=true in production"}
                )
            elif response.status_code in [401, 403]:
                result.add_finding(
                    severity="info",
                    message="Authentication is ENABLED",
                    details={"status_code": response.status_code}
                )
            
        except httpx.RequestError as e:
            result.error = str(e)
        
        self.results.append(result)
    
    async def _try_bypass(
        self, 
        client: httpx.AsyncClient, 
        method: str, 
        endpoint: str, 
        technique: dict
    ):
        """Try a single bypass technique."""
        result = ProbeResult(
            name=f"bypass_{technique['name']}",
            endpoint=endpoint
        )
        
        try:
            headers = {"Accept": "application/json", **technique["headers"]}
            
            start = time.time()
            if method == "GET":
                response = await client.get(endpoint, headers=headers)
            elif method == "POST":
                response = await client.post(
                    endpoint, 
                    headers=headers,
                    json={"entity_id": "test", "event_type": "test", "data": {}}
                )
            else:
                response = await client.request(method, endpoint, headers=headers)
            
            result.elapsed_ms = (time.time() - start) * 1000
            result.status_code = response.status_code
            
            # Analyze response
            if response.status_code == 200:
                result.add_finding(
                    severity="high" if technique["name"] != "no_key" else "medium",
                    message=f"Endpoint accessible with technique: {technique['description']}",
                    details={
                        "technique": technique["name"],
                        "expected": "401 or 403",
                        "actual": response.status_code
                    }
                )
            elif response.status_code == 500:
                result.add_finding(
                    severity="medium",
                    message=f"Server error triggered by: {technique['description']}",
                    details={
                        "technique": technique["name"],
                        "response": response.text[:500] if response.text else None
                    }
                )
            elif response.status_code in [401, 403]:
                result.add_finding(
                    severity="info",
                    message=f"Correctly rejected: {technique['description']}"
                )
            
        except httpx.RequestError as e:
            result.error = str(e)
        
        self.results.append(result)


class QueryStringAuthProbe(BaseProbe):
    """Test if API key can be passed via query string."""
    
    async def run(self):
        """Test query string authentication."""
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout
        ) as client:
            result = ProbeResult(
                name="query_string_auth",
                endpoint="/api/ledger/health"
            )
            
            try:
                # Try API key in query string
                start = time.time()
                response = await client.get(
                    "/api/ledger/health",
                    params={"apikey": "test-key-123"}
                )
                result.elapsed_ms = (time.time() - start) * 1000
                result.status_code = response.status_code
                
                if response.status_code == 200:
                    result.add_finding(
                        severity="medium",
                        message="API key accepted via query string (potential logging exposure)",
                        details={"param": "apikey"}
                    )
                    
            except httpx.RequestError as e:
                result.error = str(e)
            
            self.results.append(result)


if __name__ == "__main__":
    args = parse_args("Test authentication bypass techniques")
    
    async def run_all():
        # Run main bypass probe
        probe = AuthBypassProbe(
            base_url=args.base_url,
            api_key=args.api_key,
            timeout=args.timeout
        )
        await probe.run()
        
        # Also run query string probe
        qs_probe = QueryStringAuthProbe(
            base_url=args.base_url,
            api_key=args.api_key,
            timeout=args.timeout
        )
        await qs_probe.run()
        
        # Merge results
        probe.results.extend(qs_probe.results)
        probe.print_report(args.output)
    
    asyncio.run(run_all())
