"""P3 concurrency and lockdown message admission regressions."""

import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from hierachain.cluster import (
    ConflictResolutionStrategy,
    CrossLevelSyncManager,
    CrossLevelSyncStatus,
    LockdownMessage,
    LockdownMessageGuard,
    LockdownMessageType,
    SyncConflict,
)
from hierachain.cluster import cross_level_sync as sync_module


@pytest.mark.parametrize("fast_success", [True, False])
def test_terminal_status_waits_for_all_overlapping_syncs(
    monkeypatch: pytest.MonkeyPatch, fast_success: bool,
) -> None:
    entered, release = threading.Event(), threading.Event()
    tip = SimpleNamespace(index=0, merkle_root="root", hash="hash")

    def slow_submit(*_args: object, **_kwargs: object) -> bool:
        entered.set()
        assert release.wait(5)
        return True

    def child(submit: object) -> SimpleNamespace:
        return SimpleNamespace(
            chain=[tip], get_state_root=lambda: "root", get_latest_block=lambda: tip,
            submit_proof_to_main=submit,
        )

    sync = CrossLevelSyncManager("node")
    sync.connect_mainchain(SimpleNamespace(add_proof=lambda: None))
    sync.connect_subchain("slow", child(slow_submit))
    sync.connect_subchain("fast", child(lambda *_a, **_k: fast_success))
    monkeypatch.setattr(sync_module, "_verify_anchor_exists", lambda *_a: True)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(sync.sync_to_mainchain, "slow")
        try:
            assert entered.wait(5)
            assert sync.sync_to_mainchain("fast").success is fast_success
            assert sync.get_status() == CrossLevelSyncStatus.SYNCING_UP
            assert sync.get_stats()["active_operations"] == 1
            with pytest.raises(RuntimeError, match="active"):
                sync.reset()
        finally:
            release.set()
        assert future.result(timeout=5).success
    expected = CrossLevelSyncStatus.COMPLETE if fast_success else CrossLevelSyncStatus.FAILED
    assert sync.get_status() == expected
    stats = sync.get_stats()
    assert stats["syncs_initiated"] == stats["syncs_completed"] + stats["syncs_failed"] == 2
    assert stats["active_operations"] == 0
    # A subsequent independent operation starts a new status group.
    assert sync.sync_to_mainchain("slow").success
    assert sync.get_status() == CrossLevelSyncStatus.COMPLETE
    sync.reset()
    assert sync.get_status() == CrossLevelSyncStatus.IDLE


def test_completion_callback_failure_does_not_reverse_committed_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tip = SimpleNamespace(index=0, merkle_root="root", hash="hash")
    sync = CrossLevelSyncManager("node")
    sync.connect_mainchain(SimpleNamespace(add_proof=lambda: None))
    sync.connect_subchain("child", SimpleNamespace(
        chain=[tip], get_state_root=lambda: "root", get_latest_block=lambda: tip,
        submit_proof_to_main=lambda *_a, **_k: True,
    ))
    monkeypatch.setattr(sync_module, "_verify_anchor_exists", lambda *_a: True)

    def broken_callback(_result: object) -> None:
        raise RuntimeError("observer failed")

    sync.set_callbacks(on_complete=broken_callback)
    assert sync.sync_to_mainchain("child").success
    assert sync.get_stats()["syncs_failed"] == 0
    assert sync.get_stats()["syncs_completed"] == 1


def _signed(timestamp: float = 100.0, reason: str = "test") -> LockdownMessage:
    message = LockdownMessage("node", timestamp, reason, LockdownMessageType.LOCKDOWN)
    message.signature = message.compute_signature("test-secret")
    return message


@pytest.mark.parametrize("timestamp", [39.0, 106.0, float("nan"), float("inf"), "100", True])
def test_admission_rejects_stale_future_or_invalid_timestamps(timestamp: object) -> None:
    message = _signed()
    message.timestamp = timestamp
    message.signature = message.compute_signature("test-secret")
    guard = LockdownMessageGuard(clock=lambda: 100.0)
    assert not guard.accept(message, "test-secret")


def test_admission_consumes_once_across_signature_forms_and_threads() -> None:
    guard = LockdownMessageGuard(clock=lambda: 100.0)
    message = _signed()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: guard.accept(message, "test-secret"), range(16)))
    assert results.count(True) == 1
    message.signature = message.signature[:32]
    assert message.verify_signature("test-secret")
    assert not guard.accept(message, "test-secret")


def test_invalid_signature_cannot_consume_capacity_and_capacity_fails_closed() -> None:
    now = [100.0]
    guard = LockdownMessageGuard(max_entries=1, clock=lambda: now[0])
    first = _signed()
    assert not guard.accept(first, "wrong-key")
    assert guard.accept(first, "test-secret")
    assert not guard.accept(_signed(reason="another"), "test-secret")
    now[0] = 161.0
    assert guard.accept(_signed(timestamp=161.0), "test-secret")
    now[0] = 100.0
    assert not guard.accept(first, "test-secret")


@pytest.mark.parametrize("message_type", [LockdownMessageType.LOCKDOWN, LockdownMessageType.RECOVERY])
def test_admission_accepts_window_boundaries_and_rejects_tampering(
    message_type: LockdownMessageType,
) -> None:
    guard = LockdownMessageGuard(clock=lambda: 100.0)
    for timestamp in (40.0, 105.0):
        message = LockdownMessage("node", timestamp, "test", message_type)
        message.signature = message.compute_signature("test-secret")
        message.reason = "changed"
        assert not guard.accept(message, "test-secret")
        message.reason = "test"
        assert guard.accept(message, "test-secret")
        restored = LockdownMessage.from_dict(message.to_dict())
        assert not guard.accept(restored, "test-secret")


def test_conflict_resolution_keeps_status_active_and_finishes_after_callback_error() -> None:
    sync = CrossLevelSyncManager("node")
    conflict = SyncConflict("conflict", "source", "target", 1, "source-hash", "target-hash")

    def callback(_conflict: SyncConflict) -> ConflictResolutionStrategy:
        assert sync.get_status() == CrossLevelSyncStatus.RESOLVING_CONFLICT
        with pytest.raises(RuntimeError, match="active"):
            sync.reset()
        raise RuntimeError("observer failed")

    sync.set_callbacks(on_conflict=callback)
    with pytest.raises(RuntimeError, match="observer"):
        sync.resolve_sync_conflict(conflict)
    assert sync.get_status() == CrossLevelSyncStatus.FAILED
    assert sync.get_stats()["active_operations"] == 0
    sync.reset()
    sync.set_callbacks(on_conflict=lambda _c: ConflictResolutionStrategy.MAINCHAIN_WINS)
    assert sync.resolve_sync_conflict(conflict)
    assert sync.get_status() == CrossLevelSyncStatus.COMPLETE
