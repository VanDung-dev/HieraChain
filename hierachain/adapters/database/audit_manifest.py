"""PostgreSQL manifest kept outside the mutable audit archive."""

from __future__ import annotations

import re

import psycopg


class PostgresAuditManifest:
    """Write and read trusted audit digests using a dedicated PostgreSQL database."""

    def __init__(self, database_url: str) -> None:
        if not database_url.strip():
            raise ValueError("Audit manifest database URL is required")
        self.database_url = database_url
        with psycopg.connect(self.database_url, connect_timeout=3) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT to_regclass('public.audit_event_digests')")
                if cursor.fetchone()[0] is None:
                    raise RuntimeError("Audit manifest table is not initialized")

    def write_digest(self, event_id: str, digest: str) -> None:
        if not event_id or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ValueError("Invalid audit event ID or digest")
        with psycopg.connect(self.database_url, connect_timeout=3) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO public.audit_event_digests (event_id, digest) VALUES (%s, %s)",
                    (event_id, digest),
                )

    def load_hashes(self) -> dict[str, str]:
        with psycopg.connect(self.database_url, connect_timeout=3) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT event_id, digest FROM public.audit_event_digests")
                return {event_id: digest for event_id, digest in cursor.fetchall()}
