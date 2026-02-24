"""
Brute Force Protection for API key verification.

This module provides in-memory tracking of failed authentication attempts
by IP address and API key prefix, with automatic lockout when thresholds
are exceeded. Designed to integrate with APIKeyVerifier.
"""

import time
import threading

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
    """

    def __init__(self, config: dict | None = None):
        """
        Initialize BruteForceProtector with configuration.

        Args:
            config: Optional configuration dictionary containing:
                - max_failures: Max failed attempts before lockout (default: 5)
                - lockout_duration: Seconds to lock out (default: 900 = 15 min)
                - tracking_window: Seconds window for counting failures (default: 300 = 5 min)
        """
        config = config or {}
        self.max_failures = config.get("max_failures", 5)
        self.lockout_duration = config.get("lockout_duration", 900)
        self.tracking_window = config.get("tracking_window", 300)

        # Thread-safe storage for failure tracking
        self._lock = threading.Lock()

        # Structure: {ip: [timestamp1, timestamp2, ...]}
        self._failures: dict[str, list[float]] = {}

        # Structure: {ip: lockout_expiry_timestamp}
        self._lockouts: dict[str, float] = {}

        # Track last cleanup time to avoid frequent cleanup runs
        self._last_cleanup = time.time()
        self._cleanup_interval = 60  # Run cleanup at most every 60 seconds

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

                # Log security event
                self._log_brute_force_detected(ip, key_prefix, failure_count)
                return True

            # Log individual failure (at debug level to avoid log spam)
            logger.debug(
                f"Auth failure recorded for IP {ip} "
                f"(attempt {failure_count}/{self.max_failures})",
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
            f"Brute-force lockout reset for IP {ip}",
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
            f"Brute-force attack detected from IP {ip}: "
            f"{failure_count} failed attempts",
            extra={
                "event_type": "brute_force_detected",
                "ip": ip,
                "key_prefix": key_prefix,
                "failure_count": failure_count,
                "source": "BruteForceProtector",
            }
        )
