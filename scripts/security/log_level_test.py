"""
LOG_LEVEL Configuration Test - Verifies behavior differences between DEBUG and INFO modes.

This script tests:
1. Error disclosure differences between LOG_LEVEL=DEBUG and LOG_LEVEL=INFO
2. Ensures DEBUG mode doesn't expose sensitive internal details in responses
3. Checks stack trace handling in different log levels
"""

import asyncio
import sys
import re
import httpx
from .base_probe import BaseProbe, parse_args, run_probe, ProbeResult


def _check_critical_patterns(
        result: ProbeResult, body: str, context: str
) -> None:
    critical_patterns = [
        (r"Traceback \(most recent call last\):", "Python traceback exposed"),
        (r'File ".*\.py", line \d+', "Source file path and line exposed"),
        (r"(/home/|/var/|/usr/|C:\\Users\\)", "System path exposed"),
        (
            r"password|secret|token|private.*key",
            "Sensitive keyword in response",
        ),
    ]
    for pattern, message in critical_patterns:
        if re.search(pattern, body, re.IGNORECASE):
            result.add_finding("critical", f"[{context}] {message}")


def _check_high_patterns(
        result: ProbeResult, body: str, context: str
) -> None:
    high_patterns = [
        (r"DEBUG|debug.*mode", "DEBUG mode indicator exposed"),
        (
            r"ConnectionError|DatabaseError|Redis",
            "Backend technology exposed",
        ),
        (
            r"__init__|__call__|__new__",
            "Python dunder method names exposed",
        ),
    ]
    for pattern, message in high_patterns:
        if re.search(pattern, body, re.IGNORECASE):
            result.add_finding("high", f"[{context}] {message}")


def _check_medium_patterns(
        result: ProbeResult, body: str, context: str
) -> None:
    medium_patterns = [
        (r"starlette|fastapi|uvicorn", "Ledger name exposed"),
        (r"version.*\d+\.\d+\.\d+", "Version number exposed"),
        (
            r"internal.*error|unexpected.*error",
            "Generic internal error message",
        ),
    ]
    for pattern, message in medium_patterns:
        if re.search(pattern, body, re.IGNORECASE):
            result.add_finding("medium", f"[{context}] {message}")


def _check_response_length(
        result: ProbeResult, body: str, context: str
) -> None:
    if len(body) > 2000:
        result.add_finding(
            "medium",
            f"[{context}] Error response unusually long ({len(body)} chars)",
        )


def _check_error_content_type(
        result: ProbeResult, response: httpx.Response, context: str
) -> None:
    if response.status_code < 400:
        return
    content_type = response.headers.get("content-type", "")
    if "application/json" not in content_type:
        result.add_finding(
            "low",
            f"[{context}] Non-JSON error response: {content_type}",
        )


def _add_info_if_no_findings(
        result: ProbeResult, context: str
) -> None:
    if not result.findings:
        result.add_finding(
            "info",
            f"[{context}] Error response appears properly sanitized",
        )


def _analyze_disclosure(
        result: ProbeResult, response: httpx.Response, context: str
):
    """Analyze response for information disclosure issues."""
    body = response.text
    _check_critical_patterns(result, body, context)
    _check_high_patterns(result, body, context)
    _check_medium_patterns(result, body, context)
    _check_response_length(result, body, context)
    _check_error_content_type(result, response, context)
    _add_info_if_no_findings(result, context)


class LogLevelTestProbe(BaseProbe):
    """Probe for testing LOG_LEVEL configuration effects on error disclosure."""
    
    async def run(self):
        print(f"[*] Starting LOG_LEVEL Test Probe against {self.base_url}...", file=sys.stderr)
        print(f"[*] This test should be run twice:", file=sys.stderr)
        print(f"    1. With LOG_LEVEL=DEBUG", file=sys.stderr)
        print(f"    2. With LOG_LEVEL=INFO or WARNING", file=sys.stderr)
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            await self.test_404_error_disclosure(client)
            await self.test_validation_error_disclosure(client)
            await self.test_malformed_json_disclosure(client)
            await self.test_internal_server_error_simulation(client)
            await self.test_type_confusion_error(client)
            
    async def test_404_error_disclosure(self, client):
        """Test 404 error message for information leakage."""
        result = ProbeResult("404 Error Disclosure", "/api/v1/nonexistent_endpoint_xyz")
        
        try:
            response = await client.get(
                f"{self.base_url}/api/v1/nonexistent_endpoint_xyz",
                headers=self.get_headers()
            )
            result.status_code = response.status_code
            
            _analyze_disclosure(result, response, "404 Not Found")
            
        except Exception as e:
            result.error = str(e)
        
        self.results.append(result)
    
    async def test_validation_error_disclosure(self, client):
        """Test validation error messages for excessive detail."""
        result = ProbeResult("Validation Error Disclosure", "/api/v2/channels")
        
        try:
            # Send invalid data types
            invalid_payload = {
                "name": 12345,  # Should be string
                "description": {"nested": "object"},  # Wrong type
                "invalid_field": "test"
            }
            
            response = await client.post(
                f"{self.base_url}/api/v2/channels",
                headers=self.get_headers(),
                json=invalid_payload
            )
            result.status_code = response.status_code
            
            _analyze_disclosure(result, response, "Validation Error")
            
            # Check if too much model info is exposed
            body = response.text.lower()
            if "pydantic" in body:
                result.add_finding("medium", "Pydantic ledger name exposed in validation error")
            if "field required" in body and "loc" in body:
                result.add_finding("info", "Standard field validation format - acceptable")
                
        except Exception as e:
            result.error = str(e)
        
        self.results.append(result)
    
    async def test_malformed_json_disclosure(self, client):
        """Test malformed JSON error handling."""
        result = ProbeResult("Malformed JSON Disclosure", "/api/v2/channels")
        
        try:
            # Send invalid JSON
            response = await client.post(
                f"{self.base_url}/api/v2/channels",
                headers={**self.get_headers(), "Content-Type": "application/json"},
                content="{invalid json: 'syntax error"
            )
            result.status_code = response.status_code
            
            _analyze_disclosure(result, response, "JSON Parse Error")
            
            body = response.text.lower()
            if "line" in body and "column" in body:
                result.add_finding("low", "JSON parse error position disclosed (line/column)")
            if "expecting" in body:
                result.add_finding("info", "JSON parse error includes expected token info")
                
        except Exception as e:
            result.error = str(e)
        
        self.results.append(result)
    
    async def test_internal_server_error_simulation(self, client):
        """Try to trigger 500 errors to check error handling."""
        result = ProbeResult("500 Error Disclosure", "various")
        
        # Various payloads that might trigger internal errors
        error_triggers = [
            # Deeply nested JSON
            ("/api/v2/channels", "POST", {"a": {"b": {"c": {"d": {"e": {"f": "deep"}}}}}}, "deeply nested"),
            # Large array
            ("/api/v2/channels", "POST", {"items": list(range(10000))}, "large array"),
            # Very long string
            ("/api/v2/channels", "POST", {"name": "x" * 100000}, "very long string"),
            # Null in object
            ("/api/v2/channels", "POST", {"name": None, "description": None}, "null values"),
        ]
        
        for endpoint, method, payload, description in error_triggers:
            try:
                if method == "POST":
                    response = await client.post(
                        f"{self.base_url}{endpoint}",
                        headers=self.get_headers(),
                        json=payload,
                        timeout=10.0
                    )
                else:
                    response = await client.get(
                        f"{self.base_url}{endpoint}",
                        headers=self.get_headers()
                    )
                
                if response.status_code >= 500:
                    result.add_finding("medium", f"Got 500 error with '{description}' payload")
                    _analyze_disclosure(result, response, f"500 via {description}")
                else:
                    result.add_finding("info", f"'{description}' handled gracefully (got {response.status_code})")
                    
            except httpx.TimeoutException:
                result.add_finding("medium", f"Timeout with '{description}' - possible DoS vector")
            except Exception as e:
                result.add_finding("info", f"'{description}' caused exception: {type(e).__name__}")
        
        self.results.append(result)
    
    async def test_type_confusion_error(self, client):
        """Test type confusion scenarios for error messages."""
        result = ProbeResult("Type Confusion Disclosure", "/api/v2/channels")
        
        type_confusion_payloads = [
            # String where int expected
            {"count": "not_a_number"},
            # Int where string expected
            {"name": 99999},
            # Boolean where object expected  
            {"config": True},
            # Array where object expected
            {"settings": [1, 2, 3]},
        ]
        
        for payload in type_confusion_payloads:
            try:
                response = await client.post(
                    f"{self.base_url}/api/v2/channels",
                    headers=self.get_headers(),
                    json=payload
                )
                
                if response.status_code in [400, 422]:
                    _analyze_disclosure(result, response, f"Type confusion: {list(payload.keys())[0]}")
                elif response.status_code >= 500:
                    result.add_finding("high", f"Type confusion caused 500 error: {payload}")
                    _analyze_disclosure(result, response, "Type confusion 500")
                    
            except Exception as e:
                result.add_finding("info", f"Type confusion error: {e}")
        
        self.results.append(result)


if __name__ == "__main__":
    args = parse_args("Test LOG_LEVEL configuration effects on error disclosure")
    asyncio.run(run_probe(LogLevelTestProbe, args))
