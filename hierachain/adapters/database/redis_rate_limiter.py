"""Redis-backed API rate-limit state."""

import logging
import time

logger = logging.getLogger(__name__)


class RateLimiterBackendError(RuntimeError):
    """The shared rate-limit backend could not be checked."""


class RedisRateLimiter:
    def __init__(self, requests_per_minute: int, host: str, port: int, db: int) -> None:
        import redis

        self._redis = redis.Redis(
            host=host, port=port, db=db,
            socket_connect_timeout=2, socket_timeout=2, decode_responses=True,
        )
        self.limit = requests_per_minute

    @staticmethod
    def _key(ip: str) -> str:
        window = int(time.time()) // 60
        return f"hrc:rl:{ip}:{window}"

    def check(self, ip: str) -> tuple[bool, int]:
        """Count a request and return the decision and remaining quota."""
        try:
            pipe = self._redis.pipeline()
            key = self._key(ip)
            pipe.incr(key)
            pipe.expire(key, 60)
            count, _ = pipe.execute()
            count = int(count)
            return count <= self.limit, max(0, self.limit - count)
        except Exception as exc:
            logger.error("Redis rate limiter unavailable: %s", exc)
            raise RateLimiterBackendError("Redis rate limiter unavailable") from exc

    def is_allowed(self, ip: str) -> bool:
        return self.check(ip)[0]

    def remaining(self, ip: str) -> int:
        try:
            count = int(self._redis.get(self._key(ip)) or 0)
            return max(0, self.limit - count)
        except Exception as exc:
            logger.error("Redis rate limiter unavailable: %s", exc)
            raise RateLimiterBackendError("Redis rate limiter unavailable") from exc
