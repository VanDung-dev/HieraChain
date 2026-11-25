import os
import re
import secrets
import socket
import subprocess
import time
from urllib.parse import urlsplit, urlunsplit


def _can_connect(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout):
            return True
    except OSError:
        return False


def _postgres_reachable(url: str) -> bool:
    try:
        import psycopg

        with psycopg.connect(url, connect_timeout=2):
            return True
    except Exception:
        return False


def resolve_postgres_base_url() -> str | None:
    for key in ("HRC_TEST_POSTGRES_URL", "HRC_P2_TEST_POSTGRES_URL"):
        value = os.getenv(key)
        if value and _postgres_reachable(value):
            parsed = urlsplit(value)
            return urlunsplit(parsed._replace(path="/postgres"))
    candidates = [
        "postgresql://hiera:hiera_password@localhost:5432/postgres",
        "postgresql://postgres:postgres@localhost:5432/postgres",
    ]
    for url in candidates:
        if _postgres_reachable(url):
            return url
    return None


def create_temp_postgres_db(base_url: str) -> tuple[str, str]:
    import psycopg
    from psycopg import sql

    db_name = f"hrc_t_{secrets.token_hex(6)}"
    parsed = urlsplit(base_url)
    admin_url = urlunsplit(parsed._replace(path="/postgres"))
    db_url = urlunsplit(parsed._replace(path=f"/{db_name}"))
    with psycopg.connect(admin_url, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
    return db_url, db_name


def drop_postgres_db(base_url: str, db_name: str) -> None:
    try:
        import psycopg
        from psycopg import sql

        parsed = urlsplit(base_url)
        admin_url = urlunsplit(parsed._replace(path="/postgres"))
        with psycopg.connect(admin_url, autocommit=True) as connection:
            connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(db_name))
            )
    except Exception:
        pass


def _docker_available() -> bool:
    try:
        result = subprocess.run(
            ["docker", "info"], capture_output=True, timeout=10, check=False
        )
        return result.returncode == 0
    except Exception:
        return False


def _run(cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)


def _find_free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_redis(port: int, timeout: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            import redis as redis_lib

            redis_lib.Redis(host="127.0.0.1", port=port, socket_connect_timeout=1).ping()
            return True
        except Exception:
            time.sleep(0.2)
    return False


_DURABLE_REDIS_ARGS = [
    "redis-server",
    "--appendonly", "yes",
    "--appendfsync", "always",
    "--no-appendfsync-on-rewrite", "no",
    "--maxmemory-policy", "noeviction",
    "--aof-load-truncated", "no",
    "--save", "",
]


def ensure_durable_redis(name: str, port: int | None = None) -> tuple[str, int, str] | None:
    if not _docker_available():
        return None
    inspect = _run(["docker", "inspect", "-f", "{{.State.Running}}", name])
    if inspect.returncode == 0:
        if inspect.stdout.strip() != "true":
            _run(["docker", "start", name])
        port_out = _run(["docker", "port", name, "6379/tcp"])
        match = re.search(r":(\d+)", port_out.stdout)
        if match and _wait_for_redis(int(match.group(1))):
            resolved = int(match.group(1))
            return f"redis://127.0.0.1:{resolved}/0", resolved, name
        _run(["docker", "rm", "-f", name])

    host_port = port or _find_free_port()
    create = _run(
        [
            "docker", "run", "-d",
            "--name", name,
            "-p", f"127.0.0.1:{host_port}:6379",
            "redis:7-alpine",
            *_DURABLE_REDIS_ARGS,
        ]
    )
    if create.returncode != 0:
        return None
    if not _wait_for_redis(host_port):
        _run(["docker", "rm", "-f", name])
        return None
    return f"redis://127.0.0.1:{host_port}/0", host_port, name


def cleanup_container(name: str) -> None:
    _run(["docker", "rm", "-f", name])
