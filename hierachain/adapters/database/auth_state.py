"""Persistent shared state for API key revocation and Redis lockouts."""

import hashlib
import math
import os
import sqlite3
import time
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
        expiry = self.client.get(self._key(ip))
        return float(expiry) if expiry is not None else None

    def set(self, ip: str, expiry: float) -> None:
        ttl = math.ceil(expiry - time.time())
        if ttl > 0:
            self.client.setex(self._key(ip), ttl, str(expiry))
        else:
            self.delete(ip)

    def delete(self, ip: str) -> None:
        self.client.delete(self._key(ip))
