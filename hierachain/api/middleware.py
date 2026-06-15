"""
Middleware for HieraChain API server.

Provides rate limiting, security headers, payload size limiting,
and request logging.
"""

import uuid
import time
import logging
import threading
from typing import Any, cast

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


logger = logging.getLogger(__name__)


class PayloadLimitMiddleware(BaseHTTPMiddleware):
    MAX_PAYLOAD_SIZE = 1 * 1024 * 1024

    async def dispatch(self, request: Request, call_next):
        if request.method in ("POST", "PUT", "PATCH"):
            content_length = request.headers.get("Content-Length")
            if content_length:
                try:
                    if int(content_length) > self.MAX_PAYLOAD_SIZE:
                        return JSONResponse(
                            status_code=413,
                            content={"error": "Payload too large. Maximum size is 1MB."}
                        )
                except ValueError:
                    pass
        return await call_next(request)


def _get_csp_for_docs(is_dev: bool) -> str:
    if is_dev:
        return (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: https://fastapi.tiangolo.com"
        )
    return "default-src 'self'; script-src 'self'; style-src 'self'"


def _get_csp_for_api() -> str:
    return "default-src 'none'; frame-ancestors 'none'"


def _is_docs_path(path: str) -> bool:
    return path in ("/docs", "/redoc", "/openapi.json")


def add_security_headers(fast_app: FastAPI, is_dev: bool):
    @fast_app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, private"
        )
        response.headers["Pragma"] = "no-cache"

        if "server" in response.headers:
            del response.headers["server"]

        path = request.url.path
        if _is_docs_path(path):
            response.headers["Content-Security-Policy"] = _get_csp_for_docs(is_dev)
        else:
            response.headers["Content-Security-Policy"] = _get_csp_for_api()

        return response


def add_payload_limit(fast_app: FastAPI):
    @fast_app.middleware("http")
    async def limit_upload_size(request: Request, call_next):
        max_size = 1 * 1024 * 1024

        content_length_header = request.headers.get("content-length")
        if (
            request.method in ("POST", "PUT", "PATCH")
            and content_length_header
        ):
            try:
                content_length = int(content_length_header)
                if content_length > max_size:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": "Payload Too Large",
                            "message": f"Request body too large. Limit is {max_size} bytes",
                            "status_code": 413
                        }
                    )
            except ValueError:
                pass

        return await call_next(request)


class RateLimiter:
    def __init__(self, requests_per_minute: int):
        self.store: dict = {}
        self.limit = requests_per_minute
        self._lock = threading.Lock()

    def is_allowed(self, ip: str) -> bool:
        now = int(time.time())
        with self._lock:
            if now % 60 == 0:
                self.store = {k: v for k, v in self.store.items() if v[0] > now - 60}

            start, count = self.store.get(ip, (now, 0))

            if now - start > 60:
                self.store[ip] = (now, 1)
                return True

            if count >= self.limit:
                return False

            self.store[ip] = (start, count + 1)
            return True

    def remaining(self, ip: str) -> int:
        now = int(time.time())
        with self._lock:
            start, count = self.store.get(ip, (now, 0))
            if now - start > 60:
                return self.limit
            return max(0, self.limit - count)


class RedisRateLimiter:
    def __init__(self, requests_per_minute: int, host: str, port: int, db: int):
        import redis
        self._redis = redis.Redis(
            host=host, port=port, db=db,
            socket_connect_timeout=2, socket_timeout=2, decode_responses=True
        )
        self.limit = requests_per_minute

    @staticmethod
    def _key(ip: str) -> str:
        window = int(time.time()) // 60
        return f"hrc:rl:{ip}:{window}"

    def is_allowed(self, ip: str) -> bool:
        key = self._key(ip)
        try:
            pipe = self._redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, 60)
            count, _ = pipe.execute()
            return int(count) <= self.limit
        except Exception as exc:
            logger.warning("Redis rate-limiter error, allowing request: %s", exc)
            return True

    def remaining(self, ip: str) -> int:
        key = self._key(ip)
        try:
            count = int(cast(Any, self._redis.get(key)) or 0)
            return max(0, self.limit - count)
        except (TypeError, AttributeError):
            return self.limit


def add_rate_limit(fast_app: FastAPI, settings, exempt_paths: set[str]) -> None:
    if not settings.RATE_LIMIT_ENABLED:
        return

    rpm = settings.RATE_LIMIT_REQUESTS_PER_MINUTE
    backend = getattr(settings, "RATE_LIMIT_BACKEND", "memory")

    if backend == "redis":
        limiter: RateLimiter | RedisRateLimiter = RedisRateLimiter(
            rpm,
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
        )
        logger.info("Rate limiter: Redis backend (%d rpm)", rpm)
    else:
        limiter = RateLimiter(rpm)
        logger.info("Rate limiter: in-memory backend (%d rpm)", rpm)

    @fast_app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        if request.url.path in exempt_paths:
            return await call_next(request)

        client = request.client
        client_ip = "unknown"
        if client is not None:
            client_ip = client.host

        if not limiter.is_allowed(client_ip):
            remaining = limiter.remaining(client_ip)
            return JSONResponse(
                status_code=429,
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Limit": str(rpm),
                    "X-RateLimit-Remaining": str(remaining),
                },
                content={
                    "error": "Too Many Requests",
                    "message": "Rate limit exceeded. Please try again later.",
                    "status_code": 429,
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(rpm)
        response.headers["X-RateLimit-Remaining"] = str(limiter.remaining(client_ip))
        return response


def add_request_logging(fast_app: FastAPI) -> None:
    @fast_app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        request_id = uuid.uuid4().hex
        start = time.perf_counter()

        response = await call_next(request)

        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Request-ID"] = request_id

        logger.info(
            "%s %s -> %s (%.2f ms) [%s]",
            request.method,
            request.url.path,
            response.status_code,
            latency_ms,
            request_id,
            extra={"request_id": request_id},
        )
        return response
