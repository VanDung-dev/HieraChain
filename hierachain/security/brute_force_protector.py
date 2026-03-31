"""
Brute Force Protection for API key verification.

This module provides tracking of failed authentication attempts
by IP address and API key prefix, with automatic lockout when thresholds
are exceeded. Designed to integrate with APIKeyVerifier.

Supports both in-memory and persistent storage (Redis or file-based).
"""

import time
import threading
import json
import os
from pathlib import Path

from hierachain.security.secure_logging import get_security_logger

logger = get_security_logger()


class _LockoutStorage:
    """Handles persistence of lockout data."""
    
    def __init__(self, backend: str, path: str, redis_url: str | None):
        self._backend = backend
        self._path = path
        self._redis_url = redis_url
        self._redis_client = None
        self._init_backend()
    
    def _init_backend(self) -> None:
        """Initialize storage backend."""
        if self._backend == "file":
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        elif self._backend == "redis":
            self._init_redis()
    
    def _init_redis(self) -> None:
        """Initialize Redis client."""
        try:
            import redis
            self._redis_client = redis.from_url(
                self._redis_url or "redis://localhost:6379/0",
                decode_responses=True
            )
        except ImportError:
            logger.warning("Redis not available, falling back to file storage")
            self._backend = "file"
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
    
    def load_lockouts(self) -> dict[str, float]:
        """Load persisted lockouts from storage."""
        if self._backend == "file":
            return self._load_from_file()
        elif self._backend == "redis":
            return self._load_from_redis()
        return {}
    
    def _load_from_file(self) -> dict[str, float]:
        """Load data from file storage."""
        lockout_file = f"{self._path}_lockouts.json"
        if not os.path.exists(lockout_file):
            return {}
        
        try:
            with open(lockout_file, 'r') as f:
                data = json.load(f)
                now = time.time()
                # Only load non-expired lockouts
                lockouts = {
                    ip: expiry for ip, expiry in data.items()
                    if expiry > now
                }
                logger.info("Loaded %d persisted lockouts", len(lockouts))
                return lockouts
        except Exception as e:
            logger.error("Failed to load persisted lockouts: %s", e)
            return {}
    
    def _load_from_redis(self) -> dict[str, float]:
        """Load data from Redis storage."""
        if not self._redis_client:
            return {}
        
        try:
            now = time.time()
            keys = self._redis_client.keys("brute_force:lockout:*")
            lockouts: dict[str, float] = {}
            for key in keys:
                ip = key.split(":")[-1]
                expiry = self._redis_client.get(key)
                if expiry and float(expiry) > now:
                    lockouts[ip] = float(expiry)
            logger.info("Loaded %d persisted lockouts from Redis", len(lockouts))
            return lockouts
        except Exception as e:
            logger.error("Failed to load persisted lockouts from Redis: %s", e)
            return {}
    
    def save_lockouts(self, lockouts: dict[str, float]) -> None:
        """Persist current lockouts to storage."""
        if self._backend == "file":
            self._save_to_file(lockouts)
        elif self._backend == "redis":
            self._save_to_redis(lockouts)
    
    def _save_to_file(self, lockouts: dict[str, float]) -> None:
        """Save lockouts to file storage."""
        lockout_file = f"{self._path}_lockouts.json"
        try:
            with open(lockout_file, 'w') as f:
                json.dump(lockouts, f)
        except Exception as e:
            logger.error("Failed to persist lockouts: %s", e)
    
    def _save_to_redis(self, lockouts: dict[str, float]) -> None:
        """Save lockouts to Redis storage."""
        if not self._redis_client:
            return
        
        try:
            pipe = self._redis_client.pipeline()
            keys = self._redis_client.keys("brute_force:lockout:*")
            if keys:
                pipe.delete(*keys)
            for ip, expiry in lockouts.items():
                pipe.setex(f"brute_force:lockout:{ip}", 900, str(expiry))
            pipe.execute()
        except Exception as e:
            logger.error("Failed to persist lockouts to Redis: %s", e)


class _FailureTracker:
    """Manages failure tracking with cleanup."""
    
    def __init__(self, tracking_window: int, cleanup_interval: int):
        self._tracking_window = tracking_window
        self._cleanup_interval = cleanup_interval
        self._failures: dict[str, list[float]] = {}
        self._last_cleanup = time.time()
        self._lock = threading.Lock()
    
    def add_failure(self, ip: str, now: float) -> int:
        """Add failure timestamp and return count within window."""
        with self._lock:
            self._maybe_cleanup(now)
            self._failures.setdefault(ip, [])
            
            # Remove old failures
            cutoff = now - self._tracking_window
            self._failures[ip] = [ts for ts in self._failures[ip] if ts > cutoff]
            
            # Record new failure
            self._failures[ip].append(now)
            return len(self._failures[ip])
    
    def clear_failures(self, ip: str) -> None:
        """Clear failure tracking for an IP."""
        with self._lock:
            self._failures.pop(ip, None)
    
    def get_count(self, ip: str) -> int:
        """Get failure count within tracking window."""
        now = time.time()
        cutoff = now - self._tracking_window
        
        with self._lock:
            failures = self._failures.get(ip, [])
            return len([ts for ts in failures if ts > cutoff])
    
    def _maybe_cleanup(self, now: float) -> None:
        """Run periodic cleanup of expired entries. Must hold lock."""
        if now - self._last_cleanup < self._cleanup_interval:
            return
        
        self._last_cleanup = now
        cutoff = now - self._tracking_window
        
        # Clean expired failure records
        expired_ips = [
            ip for ip, failures in self._failures.items()
            if not [ts for ts in failures if ts > cutoff]
        ]
        for ip in expired_ips:
            del self._failures[ip]
    
    def cleanup_expired_lockouts(self, lockouts: dict[str, float], now: float) -> dict[str, float]:
        """Remove expired lockouts and return cleaned dict."""
        with self._lock:
            return {
                ip: expiry for ip, expiry in lockouts.items()
                if now < expiry
            }


class BruteForceProtector:
    """
    Tracks failed API key authentication attempts and enforces temporary lockouts.

    Features:
    - Per-IP failure counting within a configurable time window
    - Automatic lockout after exceeding failure threshold
    - Security event logging when brute-force pattern detected
    - Thread-safe operations
    - Auto-cleanup of expired tracking entries to prevent memory growth
    - Persistent storage (survives service restarts)
    """

    def __init__(self, config: dict | None = None):
        """
        Initialize BruteForceProtector with configuration.

        Args:
            config: Optional configuration dictionary containing:
                - max_failures: Max failed attempts before lockout (default: 5)
                - lockout_duration: Seconds to lock out (default: 900 = 15 min)
                - tracking_window: Seconds window for counting failures
                                   (default: 300 = 5 min)
                - storage_backend: Storage type - "memory", "redis", or "file" (default: "file")
                - storage_path: Path for file-based storage (default: "data/brute_force")
                - redis_url: Redis connection URL (if using redis)
        """
        config = config or {}
        self.max_failures = config.get("max_failures", 5)
        self.lockout_duration = config.get("lockout_duration", 900)
        self.tracking_window = config.get("tracking_window", 300)
        
        # Initialize storage and failure tracking
        storage_backend = config.get("storage_backend", "file")
        storage_path = config.get("storage_path", "data/brute_force")
        redis_url = config.get("redis_url", None)
        
        self._storage = _LockoutStorage(storage_backend, storage_path, redis_url)
        self._tracker = _FailureTracker(self.tracking_window, 60)
        
        # Lock for lockout operations
        self._lockout_lock = threading.Lock()
        
        # Load persisted data
        self._lockouts = self._storage.load_lockouts()

    def record_failure(self, ip: str, key_prefix: str = "unknown") -> bool:
        """
        Record a failed authentication attempt.

        Args:
            ip: Client IP address
            key_prefix: First 8 chars of the API key (for logging)

        Returns:
            bool: True if the IP is now locked out after this failure
        """
        now = time.time()
        
        # Add failure and get count
        failure_count = self._tracker.add_failure(ip, now)
        
        # Check if threshold exceeded
        if failure_count >= self.max_failures:
            self._trigger_lockout(ip, now, key_prefix, failure_count)
            return True
        
        # Log individual failure
        self._log_failure(ip, key_prefix, failure_count)
        return False

    def _trigger_lockout(self, ip: str, now: float, key_prefix: str, count: int) -> None:
        """Trigger lockout for an IP after threshold exceeded."""
        with self._lockout_lock:
            self._lockouts[ip] = now + self.lockout_duration
            self._tracker.clear_failures(ip)
            self._storage.save_lockouts(self._lockouts)
        
        self._log_brute_force_detected(ip, key_prefix, count)

    def _log_failure(self, ip: str, key_prefix: str, count: int) -> None:
        """Log individual failure at debug level."""
        logger.debug(
            "Auth failure recorded for IP %s (attempt %d/%d)",
            ip, count, self.max_failures,
            extra={
                "event_type": "auth_failure_recorded",
                "ip": ip,
                "key_prefix": key_prefix,
                "failure_count": count,
                "max_failures": self.max_failures,
            }
        )

    def is_locked_out(self, ip: str) -> bool:
        """
        Check if an IP address is currently locked out.

        Args:
            ip: Client IP address

        Returns:
            bool: True if the IP is locked out
        """
        now = time.time()
        
        with self._lockout_lock:
            expiry = self._lockouts.get(ip)
            if expiry is None or now >= expiry:
                # Clean up expired lockout
                if expiry is not None:
                    del self._lockouts[ip]
                    self._storage.save_lockouts(self._lockouts)
                return False
            
            return True

    def get_remaining_lockout(self, ip: str) -> float:
        """
        Get the remaining lockout duration for an IP.

        Args:
            ip: Client IP address

        Returns:
            float: Remaining seconds of lockout, or 0.0 if not locked out
        """
        now = time.time()
        
        with self._lockout_lock:
            expiry = self._lockouts.get(ip)
            if expiry is None or now >= expiry:
                return 0.0
            return expiry - now

    def reset(self, ip: str):
        """
        Manually reset lockout and failure tracking for an IP.

        Args:
            ip: Client IP address to reset
        """
        with self._lockout_lock:
            self._lockouts.pop(ip, None)
        
        self._tracker.clear_failures(ip)
        
        logger.info(
            "Brute-force lockout reset for IP %s",
            ip,
            extra={
                "event_type": "brute_force_reset",
                "ip": ip,
                "source": "BruteForceProtector",
            }
        )

    def get_failure_count(self, ip: str) -> int:
        """
        Get the current failure count for an IP within the tracking window.

        Args:
            ip: Client IP address

        Returns:
            int: Number of recent failures
        """
        return self._tracker.get_count(ip)

    @staticmethod
    def _log_brute_force_detected(ip: str, key_prefix: str, failure_count: int):
        """Log a security event when brute-force pattern is detected."""
        logger.warning(
            "Brute-force attack detected from IP %s: %d failed attempts",
            ip,
            failure_count,
            extra={
                "event_type": "brute_force_detected",
                "ip": ip,
                "key_prefix": key_prefix,
                "failure_count": failure_count,
                "source": "BruteForceProtector",
            }
        )
