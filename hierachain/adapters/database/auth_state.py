"""Persistent shared state for API key revocation and Redis lockouts."""

import hashlib
import math
import os
import sqlite3
import time
import uuid
from contextlib import closing
from pathlib import Path


def _key_digest(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()


class SQLiteRevocationStore:
    """Keep revocations across workers sharing one local database file."""

    def __init__(self, path: str) -> None:
        db_path = Path(path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.path = str(db_path)
        with closing(sqlite3.connect(self.path, timeout=5)) as connection:
            with connection:
                connection.execute("CREATE TABLE IF NOT EXISTS revoked_keys (key_digest TEXT PRIMARY KEY)")
        os.chmod(self.path, 0o600)

    def revoke(self, api_key: str) -> None:
        with closing(sqlite3.connect(self.path, timeout=5)) as connection:
            with connection:
                connection.execute(
                    "INSERT OR IGNORE INTO revoked_keys (key_digest) VALUES (?)",
                    (_key_digest(api_key),),
                )

    def is_revoked(self, api_key: str) -> bool:
        with closing(sqlite3.connect(self.path, timeout=5)) as connection:
            row = connection.execute(
                "SELECT 1 FROM revoked_keys WHERE key_digest = ?",
                (_key_digest(api_key),),
            ).fetchone()
        return row is not None


class SQLiteLockoutStore:
    """Keep per-IP lockouts visible to workers sharing one database file."""

    def __init__(self, path: str) -> None:
        db_path = Path(path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.path = str(db_path)
        with closing(sqlite3.connect(self.path, timeout=5)) as connection:
            with connection:
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS lockouts (ip TEXT PRIMARY KEY, expiry REAL NOT NULL)"
                )
                connection.execute("CREATE INDEX IF NOT EXISTS lockouts_expiry ON lockouts (expiry)")
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS auth_failures (ip TEXT NOT NULL, failed_at REAL NOT NULL)"
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS auth_failures_ip_time ON auth_failures (ip, failed_at)"
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS auth_failures_time ON auth_failures (failed_at)"
                )
        os.chmod(self.path, 0o600)

    def get(self, ip: str) -> float | None:
        with closing(sqlite3.connect(self.path, timeout=5)) as connection:
            row = connection.execute("SELECT expiry FROM lockouts WHERE ip = ?", (ip,)).fetchone()
        return float(row[0]) if row is not None else None

    def set(self, ip: str, expiry: float) -> None:
        with closing(sqlite3.connect(self.path, timeout=5)) as connection:
            with connection:
                connection.execute(
                    "DELETE FROM lockouts WHERE ip IN "
                    "(SELECT ip FROM lockouts WHERE expiry <= ? LIMIT 100)",
                    (time.time(),),
                )
                connection.execute(
                    "INSERT OR REPLACE INTO lockouts (ip, expiry) VALUES (?, ?)",
                    (ip, expiry),
                )

    def delete(self, ip: str) -> None:
        with closing(sqlite3.connect(self.path, timeout=5)) as connection:
            with connection:
                connection.execute("DELETE FROM lockouts WHERE ip = ?", (ip,))
                connection.execute("DELETE FROM auth_failures WHERE ip = ?", (ip,))

    def record_failure(
        self,
        ip: str,
        now: float,
        tracking_window: int,
        max_failures: int,
        lockout_duration: int,
    ) -> tuple[int, bool]:
        """Atomically count a failure and create a lockout at the threshold."""
        cutoff = now - tracking_window
        with closing(sqlite3.connect(self.path, timeout=5)) as connection:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute("DELETE FROM auth_failures WHERE failed_at <= ?", (cutoff,))
                row = connection.execute("SELECT expiry FROM lockouts WHERE ip = ?", (ip,)).fetchone()
                if row is not None and float(row[0]) > now:
                    return 0, True
                if row is not None:
                    connection.execute("DELETE FROM lockouts WHERE ip = ?", (ip,))

                connection.execute(
                    "INSERT INTO auth_failures (ip, failed_at) VALUES (?, ?)",
                    (ip, now),
                )
                count_row = connection.execute(
                    "SELECT COUNT(*) FROM auth_failures WHERE ip = ? AND failed_at > ?",
                    (ip, cutoff),
                ).fetchone()
                failure_count = int(count_row[0])
                locked = failure_count >= max_failures
                if locked:
                    connection.execute(
                        "INSERT OR REPLACE INTO lockouts (ip, expiry) VALUES (?, ?)",
                        (ip, now + lockout_duration),
                    )
                    connection.execute("DELETE FROM auth_failures WHERE ip = ?", (ip,))
                return failure_count, locked

    def get_failure_count(self, ip: str, now: float, tracking_window: int) -> int:
        """Return the shared count of failures within the configured window."""
        cutoff = now - tracking_window
        with closing(sqlite3.connect(self.path, timeout=5)) as connection:
            row = connection.execute(
                "SELECT COUNT(*) FROM auth_failures WHERE ip = ? AND failed_at > ?",
                (ip, cutoff),
            ).fetchone()
        return int(row[0])


class RedisRevocationStore:
    """Keep revocations across hosts sharing one Redis instance."""

    def __init__(self, url: str) -> None:
        import redis

        self.client = redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)

    def _key(self, api_key: str) -> str:
        return f"hrc:api_key:revoked:{_key_digest(api_key)}"

    def revoke(self, api_key: str) -> None:
        self.client.set(self._key(api_key), "1")

    def is_revoked(self, api_key: str) -> bool:
        return bool(self.client.exists(self._key(api_key)))


class RedisLockoutStore:
    """Read and update only the affected IP lockout key."""

    def __init__(self, url: str) -> None:
        import redis

        self.client = redis.from_url(url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)

    @staticmethod
    def _key(ip: str) -> str:
        return f"brute_force:lockout:{ip}"

    def get(self, ip: str) -> float | None:
        key = self._key(ip)
        remaining_ms = self.client.pttl(key)
        if remaining_ms == -2 or remaining_ms == 0:
            return None
        if remaining_ms > 0:
            return time.time() + remaining_ms / 1000
        expiry = self.client.get(key)
        if expiry is None:
            return None
        server_time = self.client.time()
        current_time = float(server_time[0]) + float(server_time[1]) / 1_000_000
        return time.time() + max(0.0, float(expiry) - current_time)

    def set(self, ip: str, expiry: float) -> None:
        ttl = math.ceil(expiry - time.time())
        if ttl > 0:
            self.client.setex(self._key(ip), ttl, str(expiry))
        else:
            self.delete(ip)

    def delete(self, ip: str) -> None:
        self.client.delete(self._key(ip), self._failure_key(ip))

    @staticmethod
    def _failure_key(ip: str) -> str:
        return f"brute_force:failures:{ip}"

    def record_failure(
        self,
        ip: str,
        now: float,
        tracking_window: int,
        max_failures: int,
        lockout_duration: int,
    ) -> tuple[int, bool]:
        """Atomically count a failure and create a lockout at the threshold."""
        script = """
        local redis_time = redis.call('TIME')
        local now = tonumber(redis_time[1]) + tonumber(redis_time[2]) / 1000000
        local current_lockout = redis.call('GET', KEYS[1])
        if current_lockout then
            local expiry = tonumber(current_lockout)
            if expiry and expiry > now then
                return {0, 1}
            end
            redis.call('DEL', KEYS[1])
        end
        redis.call('ZREMRANGEBYSCORE', KEYS[2], '-inf', now - tonumber(ARGV[1]))
        redis.call('ZADD', KEYS[2], now, ARGV[2])
        redis.call('EXPIRE', KEYS[2], ARGV[3])
        local failure_count = redis.call('ZCARD', KEYS[2])
        if failure_count >= tonumber(ARGV[4]) then
            local lockout_expiry = now + tonumber(ARGV[5])
            local lockout_ttl = math.ceil(tonumber(ARGV[5]))
            if lockout_ttl > 0 then
                redis.call('SET', KEYS[1], tostring(lockout_expiry), 'EX', lockout_ttl)
            end
            redis.call('DEL', KEYS[2])
            return {failure_count, 1}
        end
        return {failure_count, 0}
        """
        result = self.client.eval(
            script,
            2,
            self._key(ip),
            self._failure_key(ip),
            tracking_window,
            f"{now}:{uuid.uuid4().hex}",
            max(1, math.ceil(tracking_window)),
            max_failures,
            lockout_duration,
        )
        return int(result[0]), bool(result[1])

    def get_failure_count(self, ip: str, now: float, tracking_window: int) -> int:
        """Return the shared count of failures within the configured window."""
        server_time = self.client.time()
        current_time = float(server_time[0]) + float(server_time[1]) / 1_000_000
        return int(self.client.zcount(self._failure_key(ip), f"({current_time - tracking_window}", "+inf"))
