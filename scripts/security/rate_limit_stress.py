"""
Stress test script to verify Rate Limiting (DoS protection).
Sends a high volume of requests to trigger 429 Too Many Requests.
"""

import asyncio
import argparse
import sys
import time
import httpx
from collections import Counter
from .base_probe import BaseProbe, ProbeResult


class RateLimitStressProbe(BaseProbe):
    def __init__(self, base_url, api_key=None, timeout=10.0, total_requests=100, concurrency=10):
        super().__init__(base_url, api_key, timeout)
        self.total_requests = total_requests
        self.concurrency = concurrency

    async def run(self):
        print(f"[*] Starting Rate Limit Stress Test against {self.base_url}...", file=sys.stderr)
        print(f"[*] Configuration: {self.total_requests} requests, concurrency={self.concurrency}", file=sys.stderr)
        
        # Test endpoint
        endpoint = "/api/v2/health" # Lightweight endpoint
        result = ProbeResult("Rate Limit Check", endpoint)
        
        status_counter = Counter()
        start_time = time.time()
        
        async with httpx.AsyncClient(timeout=self.timeout, limits=httpx.Limits(max_keepalive_connections=self.concurrency, max_connections=self.concurrency)) as client:

            
            # Execute in batches if total is very large, but for now gather all with limit
            # To strictly control concurrency, we use a semaphore
            sem = asyncio.Semaphore(self.concurrency)
            
            async def bound_fetch(t_client, t_endpoint):
                async with sem:
                    return await self.send_request(t_client, t_endpoint)

            tasks = [bound_fetch(client, endpoint) for _ in range(self.total_requests)]
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            for code in responses:
                status_counter[code] += 1
        
        duration = time.time() - start_time
        result.elapsed_ms = duration * 1000
        
        # Analyze results
        success_count = status_counter.get(200, 0)
        throttle_count = status_counter.get(429, 0)
        error_count = sum(count for code, count in status_counter.items() if code not in [200, 429])
        
        result.add_finding("info", f"Sent {self.total_requests} requests in {duration:.2f}s (~{self.total_requests/duration:.1f} RPS)")
        result.add_finding("info", f"Status Codes: {dict(status_counter)}")
        
        if throttle_count > 0:
            result.add_finding("info", f"Rate Limit Triggered! {throttle_count} requests were blocked (429).")
            result.status_code = 429
        else:
            result.add_finding("medium", "Rate Limit NOT triggered. Server might be vulnerable to DoS if thresholds are low.", 
                               {"rps_achieved": self.total_requests/duration})
            result.status_code = 200 # Representative code

        self.results.append(result)

    async def send_request(self, client, endpoint):
        try:
            resp = await client.get(f"{self.base_url}{endpoint}", headers=self.get_headers())
            return resp.status_code
        except Exception as e:
            return 0 # Connection error

def custom_parse_args():
    # Extend the base argument parser
    parser = argparse.ArgumentParser(description="Rate Limit Stress Test")
    parser.add_argument("--base-url", default="http://127.0.0.1:2661", help="Base URL")
    parser.add_argument("--api-key", help="API Key")
    parser.add_argument("--output", help="Output file")
    parser.add_argument("--timeout", type=float, default=10.0)
    
    # Custom args
    parser.add_argument("--count", type=int, default=200, help="Total requests to send")
    parser.add_argument("--concurrency", type=int, default=20, help="Concurrent requests")
    
    return parser.parse_args()

async def run_custom_probe():
    args = custom_parse_args()
    probe = RateLimitStressProbe(
        base_url=args.base_url, 
        api_key=args.api_key, 
        timeout=args.timeout,
        total_requests=args.count,
        concurrency=args.concurrency
    )
    await probe.run()
    probe.print_report(args.output)

if __name__ == "__main__":
    asyncio.run(run_custom_probe())
