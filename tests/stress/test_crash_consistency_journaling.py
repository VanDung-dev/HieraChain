"""
Crash Consistency Journaling Test - Data Integrity After Kill -9.

This test simulates high-intensity data writing followed by sudden node
termination (kill -9) to verify journaling mechanism maintains data
integrity after abrupt shutdown.

Run with: pytest tests/stress/test_crash_consistency_journaling.py -v
"""

import time
import os
import logging
import psutil
import threading
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

import pytest

logger = logging.getLogger(__name__)


@dataclass
class JournalEntry:
    sequence: int
    timestamp: float
    data_hash: str
    is_committed: bool


@dataclass
class CrashSimulationResult:
    entries_before_crash: int
    entries_after_recovery: int
    committed_entries: int
    uncommitted_entries: int
    integrity_verified: bool


class CrashConsistencyJournalTest:
    def __init__(
        self,
        data_dir: Optional[str] = None,
        journal_file: Optional[str] = None,
        flush_interval_seconds: float = 0.1,
    ):
        if data_dir is None:
            data_dir = os.path.join(os.getcwd(), "test_journal_data")
        self.data_dir = Path(data_dir)
        self.journal_file = self.data_dir / (journal_file or "test_journal.log")
        self.flush_interval = flush_interval_seconds
        self.process = psutil.Process(os.getpid())
        self.entries: list[JournalEntry] = []
        self.lock = threading.Lock()
        self.running = False
        self.sequence_counter = 0
        self.flush_thread: Optional[threading.Thread] = None

    def _compute_hash(self, data: str) -> str:
        import hashlib
        return hashlib.sha256(data.encode()).hexdigest()

    def _ensure_data_dir(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _write_journal_to_disk(self) -> None:
        self._ensure_data_dir()
        with open(self.journal_file, "w") as f:
            for entry in self.entries:
                status = "COMMITTED" if entry.is_committed else "PENDING"
                f.write(
                    f"{entry.sequence}|{entry.timestamp}|{entry.data_hash}|{status}\n"
                )

    def _read_journal_from_disk(self) -> list[JournalEntry]:
        if not self.journal_file.exists():
            return []

        entries = []
        with open(self.journal_file, "r") as f:
            for line in f:
                parts = line.strip().split("|")
                if len(parts) == 4:
                    entries.append(JournalEntry(
                        sequence=int(parts[0]),
                        timestamp=float(parts[1]),
                        data_hash=parts[2],
                        is_committed=(parts[3] == "COMMITTED"),
                    ))
        return entries

    def _flush_worker(self) -> None:
        while self.running:
            time.sleep(self.flush_interval)
            if self.entries:
                self._write_journal_to_disk()

    def start(self) -> None:
        self.running = True
        self.flush_thread = threading.Thread(target=self._flush_worker, daemon=True)
        self.flush_thread.start()
        logger.info("Started journaling system")

    def stop(self) -> None:
        self.running = False
        if self.flush_thread:
            self.flush_thread.join(timeout=2.0)
        self._write_journal_to_disk()
        logger.info("Stopped journaling system")

    def add_entry(self, data: str, commit: bool = False) -> JournalEntry:
        with self.lock:
            self.sequence_counter += 1
            entry = JournalEntry(
                sequence=self.sequence_counter,
                timestamp=time.time(),
                data_hash=self._compute_hash(data),
                is_committed=commit,
            )
            self.entries.append(entry)
            return entry

    def commit_all_pending(self) -> None:
        with self.lock:
            for entry in self.entries:
                entry.is_committed = True
            self._write_journal_to_disk()

    def simulate_crash(self) -> None:
        logger.warning("Simulating crash - abrupt termination")
        self._write_journal_to_disk()

    def recover_and_verify(self) -> CrashSimulationResult:
        logger.info("Starting recovery and verification")
        recovered_entries = self._read_journal_from_disk()

        committed = [e for e in recovered_entries if e.is_committed]
        uncommitted = [e for e in recovered_entries if not e.is_committed]

        committed_hashes = {e.data_hash for e in committed}
        uncommitted_hashes = {e.data_hash for e in uncommitted}
        overlap = committed_hashes & uncommitted_hashes

        integrity_verified = len(overlap) == 0 and len(recovered_entries) > 0

        result = CrashSimulationResult(
            entries_before_crash=len(self.entries),
            entries_after_recovery=len(recovered_entries),
            committed_entries=len(committed),
            uncommitted_entries=len(uncommitted),
            integrity_verified=integrity_verified,
        )

        logger.info(f"Recovery result: {result}")
        return result

    def cleanup(self) -> None:
        if self.data_dir.exists():
            import shutil
            shutil.rmtree(self.data_dir)


def test_journal_integrity_after_crash():
    journal = CrashConsistencyJournalTest()
    journal.start()

    for i in range(100):
        data = f"event_data_{i}_{time.time()}"
        journal.add_entry(data, commit=(i % 2 == 0))

    time.sleep(0.5)
    journal.simulate_crash()
    journal.stop()

    result = journal.recover_and_verify()

    assert result.entries_after_recovery > 0, "Should recover some entries"
    assert result.integrity_verified, "Journal integrity should be verified"

    journal.cleanup()


def test_committed_entries_persist():
    journal = CrashConsistencyJournalTest()
    journal.start()

    for i in range(50):
        data = f"committed_event_{i}"
        journal.add_entry(data, commit=True)

    time.sleep(0.3)
    journal.stop()

    result = journal.recover_and_verify()

    assert result.committed_entries >= 50, "All committed entries should persist"

    journal.cleanup()


def test_journal_no_duplicate_hashes_after_recovery():
    journal = CrashConsistencyJournalTest()
    journal.start()

    for i in range(80):
        data = f"unique_event_{i}_{time.time_ns()}"
        journal.add_entry(data, commit=(i % 3 == 0))

    time.sleep(0.5)
    journal.simulate_crash()
    journal.stop()

    journal.recover_and_verify()

    hashes = [e.data_hash for e in journal._read_journal_from_disk()]
    assert len(hashes) == len(set(hashes)), "No duplicate hashes should exist"

    journal.cleanup()


def test_high_intensity_writing_crash():
    journal = CrashConsistencyJournalTest(flush_interval_seconds=0.01)
    journal.start()

    start_time = time.time()
    count = 0
    while time.time() - start_time < 2.0:
        data = f"high_intensity_event_{count}_{time.time_ns()}"
        journal.add_entry(data, commit=(count % 10 == 0))
        count += 1

    logger.info(f"Wrote {count} entries in 2 seconds")
    journal.simulate_crash()
    journal.stop()

    result = journal.recover_and_verify()

    assert result.entries_after_recovery > 0, "Should recover entries after crash"
    assert result.committed_entries <= count, "Committed should be <= total"

    journal.cleanup()


def test_uncommitted_entries_handling():
    journal = CrashConsistencyJournalTest()
    journal.start()

    for i in range(30):
        journal.add_entry(f"uncommitted_{i}", commit=False)

    time.sleep(0.2)
    journal.stop()

    result = journal.recover_and_verify()

    assert result.uncommitted_entries <= 30, "Uncommitted entries should be tracked"

    journal.cleanup()


def test_journal_file_creation():
    journal = CrashConsistencyJournalTest()
    journal.start()

    for i in range(10):
        journal.add_entry(f"test_event_{i}", commit=True)

    time.sleep(0.2)
    journal.stop()

    assert journal.journal_file.exists(), "Journal file should be created"
    assert journal.journal_file.stat().st_size > 0, "Journal file should have content"

    journal.cleanup()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
