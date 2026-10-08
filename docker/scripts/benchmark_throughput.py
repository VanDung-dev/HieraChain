"""Run the shared signed-event benchmark against PostgreSQL in Docker."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.benchmark_throughput import main as benchmark_main  # noqa: E402


def main() -> None:
    database_url = os.getenv("HRC_BENCHMARK_DB_URL", "")
    if not database_url.startswith(("postgresql://", "postgres://")):
        raise RuntimeError("Docker benchmark requires HRC_BENCHMARK_DB_URL to point to PostgreSQL")
    os.environ.setdefault("HRC_BENCHMARK_JOURNAL_DIR", "/app/data/journal")
    os.environ.setdefault("HRC_BENCHMARK_LOG_FILE", "/app/log/benchmark_debug.log")
    benchmark_main()


if __name__ == "__main__":
    main()
