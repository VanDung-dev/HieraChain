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
from typing import Any

from hierachain.security.secure_logging import get_security_logger

logger = get_security_logger()


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
        
        # Storage configuration
        self._storage_backend = config.get("storage_backend", "file")
        self._storage_path = config.get("storage_path", "data/brute_force")
        self._redis_url = config.get("redis_url", None)
        
        # Initialize storage backend
        self._storage: dict[str, Any] = {}
        self._init_storage()

        # Thread-safe storage for failure tracking
        self._lock = threading.Lock()

        # Structure: {ip: [timestamp1, timestamp2, ...]}
        self._failures: dict[str, list[float]] = {}

        # Structure: {ip: lockout_expiry_timestamp}
        self._lockouts: dict[str, float] = {}

        # Track last cleanup time to avoid frequent cleanup runs
        self._last_cleanup = time.time()
        self._cleanup_interval = 60  # Run cleanup at most every 60 seconds
        
        # Load persisted data
        self._load_persisted_data()
    
    def _init_storage(self) -> None:
        """Initialize storage backend."""
        if self._storage_backend == "file":
            # Ensure directory exists
            Path(self._storage_path).parent.mkdir(parents=True, exist_ok=True)
        elif self._storage_backend == "redis":
            try:
                import redis
                self._redis_client = redis.from_url(
                    self._redis_url or "redis://localhost:6379/0",
                    decode_responses=True
                )
            except ImportError:
                logger.warning("Redis not available, falling back to file storage")
                self._storage_backend = "file"
                Path(self._storage_path).parent.mkdir(parents=True, exist_ok=True)
    
    def _load_persisted_data(self) -> None:
        """Load persisted lockout data from storage."""
        if self._storage_backend == "file":
            self._load_from_file()
        elif self._storage_backend == "redis":
            self._load_from_redis()
    
    def _load_from_file(self) -> None:
        """Load data from file storage."""
        lockout_file = f"{self._storage_path}_lockouts.json"
        if os.path.exists(lockout_file):
            try:
                with open(lockout_file, 'r') as f:
                    data = json.load(f)
                    now = time.time()
                    # Only load non-expired lockouts
                    self._lockouts = {
                        ip: expiry for ip, expiry in data.items()
                        if expiry > now
                    }
                logger.info("Loaded %d persisted lockouts", len(self._lockouts))
            except Exception as e:
                logger.error("Failed to load persisted lockouts: %s", e)
    
    def _load_from_redis(self) -> None:
        """Load data from Redis storage."""
        try:
            now = time.time()
            keys = self._redis_client.keys("brute_force:lockout:*")
            for key in keys:
                ip = key.split(":")[-1]
                expiry = self._redis_client.get(key)
                if expiry and float(expiry) > now:
                    self._lockouts[ip] = float(expiry)
            logger.info("Loaded %d persisted lockouts from Redis", len(self._lockouts))
        except Exception as e:
            logger.error("Failed to load persisted lockouts from Redis: %s", e)
    
    def _persist_lockouts(self) -> None:
        """Persist current lockouts to storage."""
        if self._storage_backend == "file":
            self._save_to_file()
        elif self._storage_backend == "redis":
            self._save_to_redis()
    
    def _save_to_file(self) -> None:
        """Save lockouts to file storage."""
        lockout_file = f"{self._storage_path}_lockouts.json"
        try:
            with open(lockout_file, 'w') as f:
                json.dump(self._lockouts, f)
        except Exception as e:
            logger.error("Failed to persist lockouts: %s", e)
    
    def _save_to_redis(self) -> None:
        """Save lockouts to Redis storage."""
        try:
            pipe = self._redis_client.pipeline()
            # Clear existing
            keys = self._redis_client.keys("brute_force:lockout:*")
            if keys:
                pipe.delete(*keys)
            # Set new lockouts
            for ip, expiry in self._lockouts.items():
                pipe.setex(f"brute_force:lockout:{ip}", int(self.lockout_duration), str(expiry))
            pipe.execute()
        except Exception as e:
            logger.error("Failed to persist lockouts to Redis: %s", e)

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

        with self._lock:
            # Run periodic cleanup
            self._maybe_cleanup(now)

            # Initialize failure list for this IP if needed
            if ip not in self._failures:
                self._failures[ip] = []

            # Remove failures outside the tracking window
            cutoff = now - self.tracking_window
            self._failures[ip] = [
                ts for ts in self._failures[ip] if ts > cutoff
            ]

            # Record this failure
            self._failures[ip].append(now)
            failure_count = len(self._failures[ip])

            # Check if threshold exceeded
            if failure_count >= self.max_failures:
                self._lockouts[ip] = now + self.lockout_duration
                self._failures[ip] = []  # Reset failures after lockout
                
                # Persist lockout to survive service restart
                self._persist_lockouts()

                # Log security event
                self._log_brute_force_detected(ip, key_prefix, failure_count)
                return True

            # Log individual failure (at debug level to avoid log spam)
            logger.debug(
                "Auth failure recorded for IP %s "
                "(attempt %d/%d)",
                ip,
                failure_count,
                self.max_failures,
                extra={
                    "event_type": "auth_failure_recorded",
                    "ip": ip,
                    "key_prefix": key_prefix,
                    "failure_count": failure_count,
                    "max_failures": self.max_failures,
                }
            )

            return False

    def is_locked_out(self, ip: str) -> bool:
        """
        Check if an IP address is currently locked out.

        Args:
            ip: Client IP address

        Returns:
            bool: True if the IP is locked out
        """
        now = time.time()

        with self._lock:
            expiry = self._lockouts.get(ip)
            if expiry is None:
                return False

            if now < expiry:
                return True

            # Lockout has expired, clean up
            del self._lockouts[ip]
            # Persist the cleanup
            self._persist_lockouts()
            return False

    def get_remaining_lockout(self, ip: str) -> float:
        """
        Get the remaining lockout duration for an IP.

        Args:
            ip: Client IP address

        Returns:
            float: Remaining seconds of lockout, or 0.0 if not locked out
        """
        now = time.time()

        with self._lock:
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
        with self._lock:
            self._failures.pop(ip, None)
            self._lockouts.pop(ip, None)

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
        now = time.time()
        cutoff = now - self.tracking_window

        with self._lock:
            failures = self._failures.get(ip, [])
            return len([ts for ts in failures if ts > cutoff])

    def _maybe_cleanup(self, now: float):
        """
        Run periodic cleanup of expired entries.

        Must be called while holding self._lock.
        """
        if now - self._last_cleanup < self._cleanup_interval:
            return

        self._last_cleanup = now
        cutoff = now - self.tracking_window

        # Clean up expired failure records
        expired_ips: list[str] = []
        for ip, failures in self._failures.items():
            active = [ts for ts in failures if ts > cutoff]
            if active:
                self._failures[ip] = active
            else:
                expired_ips.append(ip)

        for ip in expired_ips:
            del self._failures[ip]

        # Clean up expired lockouts
        expired_lockouts: list[str] = [
            ip for ip, expiry in self._lockouts.items() if now >= expiry
        ]
        for ip in expired_lockouts:
            del self._lockouts[ip]

    @staticmethod
    def _log_brute_force_detected(ip: str, key_prefix: str, failure_count: int):
        """Log a security event when brute-force pattern is detected."""
        logger.warning(
            "Brute-force attack detected from IP %s: "
            "%d failed attempts",
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
