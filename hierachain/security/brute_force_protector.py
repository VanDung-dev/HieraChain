"""
Brute Force Protection for API key verification.

This module provides tracking of failed authentication attempts
by IP address and API key prefix, with automatic lockout when thresholds
are exceeded. Designed to integrate with APIKeyVerifier.

Supports in-memory and persistent storage (SQLite, Redis, or file-based).
"""

import os
import threading
import time
from pathlib import Path

import orjson

from hierachain.adapters.database.auth_state import RedisLockoutStore, SQLiteLockoutStore
from hierachain.security.secure_logging import get_security_logger

logger = get_security_logger()


class _LockoutStorage:
    """Handles persistence of lockout data."""
    
    def __init__(self, backend: str, path: str, redis_url: str | None) -> None:
        self._backend = backend
        self._path = path
        self._redis_url = redis_url
        self._shared_store: RedisLockoutStore | SQLiteLockoutStore | None = None
        self._init_backend()
    
    def _init_backend(self) -> None:
        """Initialize storage backend."""
        if self._backend == "file":
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        elif self._backend == "redis":
            self._init_redis()
        elif self._backend == "sqlite":
            self._shared_store = SQLiteLockoutStore(self._path)
    
    def _init_redis(self) -> None:
        """Initialize Redis client."""
        self._shared_store = RedisLockoutStore(self._redis_url or "redis://localhost:6379/0")

    @property
    def is_shared(self) -> bool:
        return self._shared_store is not None

    def get_lockout(self, ip: str) -> float | None:
        if self._shared_store is None:
            return None
        return self._shared_store.get(ip)

    def set_lockout(self, ip: str, expiry: float) -> None:
        if self._shared_store is not None:
            self._shared_store.set(ip, expiry)

    def delete_lockout(self, ip: str) -> None:
        if self._shared_store is not None:
            self._shared_store.delete(ip)
    
    def load_lockouts(self) -> dict[str, float]:
        """Load persisted lockouts from storage."""
        if self._backend == "file":
            return self._load_from_file()
        return {}
    
    def _load_from_file(self) -> dict[str, float]:
        """Load data from file storage."""
        lockout_file = f"{self._path}_lockouts.json"
        if not os.path.exists(lockout_file):
            return {}
        
        try:
            with open(lockout_file, 'rb') as f:
                data = orjson.loads(f.read())
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
    
    def save_lockouts(self, lockouts: dict[str, float]) -> None:
        """Persist current lockouts to storage."""
        if self._backend == "file":
            self._save_to_file(lockouts)
    
    def _save_to_file(self, lockouts: dict[str, float]) -> None:
        """Save lockouts to file storage."""
        lockout_file = f"{self._path}_lockouts.json"
        try:
            with open(lockout_file, 'wb') as f:
                f.write(orjson.dumps(lockouts))
        except Exception as e:
            logger.error("Failed to persist lockouts: %s", e)


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

    def __init__(self, config: dict | None = None) -> None:
        """
        Initialize BruteForceProtector with configuration.

        Args:
            config: Optional configuration dictionary containing:
                - max_failures: Max failed attempts before lockout (default: 5)
                - lockout_duration: Seconds to lock out (default: 900 = 15 min)
                - tracking_window: Seconds window for counting failures
                                   (default: 300 = 5 min)
                - storage_backend: Storage type - "memory", "file", "sqlite", or "redis" (default: "file")
                - storage_path: Path for file-based storage (default: "data/brute_force")
                - redis_url: Redis connection URL (if using redis)
        """
        cfg = config or {}
        self.max_failures = cfg.get("max_failures", 5)
        self.lockout_duration = cfg.get("lockout_duration", 900)
        self.tracking_window = cfg.get("tracking_window", 300)

        # Initialize storage and failure tracking
        storage_backend = cfg.get("storage_backend", "file")
        storage_path = cfg.get("storage_path", "data/brute_force")
        redis_url = cfg.get("redis_url", None)
        
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
            expiry = now + self.lockout_duration
            if self._storage.is_shared:
                self._storage.set_lockout(ip, expiry)
            else:
                self._lockouts[ip] = expiry
                self._storage.save_lockouts(self._lockouts)
            self._tracker.clear_failures(ip)
        
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

        if self._storage.is_shared:
            expiry = self._storage.get_lockout(ip)
            return expiry is not None and now < expiry
        
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

        if self._storage.is_shared:
            expiry = self._storage.get_lockout(ip)
            return max(0.0, expiry - now) if expiry is not None else 0.0
        
        with self._lockout_lock:
            expiry = self._lockouts.get(ip)
            if expiry is None or now >= expiry:
                return 0.0
            return expiry - now

    def reset(self, ip: str) -> None:
        """
        Manually reset lockout and failure tracking for an IP.

        Args:
            ip: Client IP address to reset
        """
        if self._storage.is_shared:
            self._storage.delete_lockout(ip)
        else:
            with self._lockout_lock:
                self._lockouts.pop(ip, None)
                self._storage.save_lockouts(self._lockouts)
        
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
