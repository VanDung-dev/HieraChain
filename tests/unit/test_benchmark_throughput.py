"""Benchmark workloads exercise signatures and count only committed events."""

import asyncio
import time
from pathlib import Path

import pytest

from hierachain.consensus.ordering.certifier import EventCertifier
from hierachain.consensus.ordering.processor import _extract_verification_items
from hierachain.consensus.ordering.types import EventStatus, PendingEvent
from scripts import benchmark_throughput as benchmark


def test_signed_workload_and_committed_measurement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HRC_BENCHMARK_DB_URL", "sqlite:///:memory:")
    monkeypatch.setenv("HRC_BENCHMARK_JOURNAL_DIR", str(tmp_path / "data" / "journal"))
    event = benchmark.generate_events(1)[0]
    pending = PendingEvent("signed", event, "default", "org1", time.time(), EventStatus.PENDING)
    assert len(_extract_verification_items([pending])[0]) == 1
    assert EventCertifier().validate(pending)["valid"]
    event["details"]["payload"] = "tampered"
    assert not EventCertifier().validate(pending)["valid"]

    result = asyncio.run(benchmark.run_benchmark(3, 2))
    assert result["events_committed"] == 3
    assert result["events_rejected"] == result["events_unfinished"] == 0
    assert result["committed_events_per_second"] == 3 / result["duration_seconds"]
    assert 0 <= result["latency_p95_seconds"] <= result["latency_p99_seconds"]

    def invalid_events(count: int) -> list[dict]:
        return [{"entity_id": "", "event": "created", "timestamp": time.time()} for _ in range(count)]

    monkeypatch.setattr(benchmark, "generate_events", invalid_events)
    with pytest.raises(RuntimeError, match="Benchmark incomplete"):
        asyncio.run(benchmark.run_benchmark(1, 1))
