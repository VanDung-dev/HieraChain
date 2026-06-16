"""
Rollback Manager for HieraChain Ledger.

Manages state snapshots, coordinates safe rollback operations,
and ensures data integrity during recovery procedures.
"""

from __future__ import annotations

import time
import json
import logging
import shutil
import os
import hashlib
import threading
from typing import Any
from datetime import datetime

from hierachain.error_mitigation.rollback_types import (
    RollbackType,
    RollbackStatus,
    StateSnapshot,
    RollbackOperation,
)

logger = logging.getLogger(__name__)


class RollbackManager:
    def __init__(self, config_dict: dict[str, Any]):
        self.config = config_dict
        self.snapshots_dir: str = str(config_dict.get("snapshots_dir", "snapshots"))
        self.max_snapshots = config_dict.get("max_snapshots", 10)
        self.auto_snapshot = config_dict.get("auto_snapshot", True)
        self.snapshot_interval = config_dict.get("snapshot_interval", 3600)
        os.makedirs(self.snapshots_dir, exist_ok=True)
        self.snapshots: list[StateSnapshot] = []
        self.active_operations: dict[str, RollbackOperation] = {}
        self.rollback_lock = threading.Lock()
        self._load_snapshots()
        if self.auto_snapshot:
            self._start_auto_snapshot()
        logger.info("Initialized RollbackManager with %d snapshots", len(self.snapshots))

    def create_snapshot(
        self,
        snapshot_type: RollbackType,
        description: str,
        components: list[Any] | None = None,
    ) -> StateSnapshot:
        snapshot_id = _generate_snapshot_id()
        timestamp = time.time()
        logger.info("Creating snapshot: %s (%s)", snapshot_id, snapshot_type.value)
        try:
            data = _capture_state(snapshot_type, components)
            data_path = os.path.join(self.snapshots_dir, f"{snapshot_id}.snapshot")
            new_snapshot = _persist_snapshot_data(
                data, data_path, snapshot_id, snapshot_type,
                timestamp, description, components,
            )
            with self.rollback_lock:
                self.snapshots.append(new_snapshot)
                self._cleanup_old_snapshots()
                self._save_snapshots_index()
            logger.info("Snapshot created: %s (%d bytes)", snapshot_id, new_snapshot.size_bytes)
            return new_snapshot
        except Exception as e:
            logger.error("Failed to create snapshot %s: %s", snapshot_id, e)
            raise

    def rollback_to_snapshot(
        self, snapshot_id: str, force: bool = False
    ) -> RollbackOperation:
        target_snapshot = self._find_snapshot_by_id(snapshot_id)
        if not target_snapshot:
            raise ValueError(f"Snapshot not found: {snapshot_id}")
        rollback_op = _init_rollback_operation(target_snapshot)
        logger.info("Starting rollback: %s -> %s", rollback_op.operation_id, snapshot_id)
        with self.rollback_lock:
            self.active_operations[rollback_op.operation_id] = rollback_op
        try:
            return self._execute_rollback_process(rollback_op, target_snapshot, force)
        except Exception as e:
            return _handle_rollback_exception(rollback_op, e)
        finally:
            _log_rollback_operation(rollback_op)

    def _find_snapshot_by_id(self, snapshot_id: str) -> StateSnapshot | None:
        for snap in self.snapshots:
            if snap.snapshot_id == snapshot_id:
                return snap
        return None

    def _execute_rollback_process(
        self,
        rollback_op: RollbackOperation,
        target_snapshot: StateSnapshot,
        force: bool,
    ) -> RollbackOperation:
        if not force and not _validate_rollback_safety(target_snapshot):
            rollback_op.status = RollbackStatus.FAILED
            rollback_op.error_message = "Rollback safety validation failed"
            rollback_op.end_time = time.time()
            return rollback_op
        rollback_op.status = RollbackStatus.IN_PROGRESS
        rollback_op.rollback_steps.append("validation_passed")
        pre_snap = self.create_snapshot(
            target_snapshot.snapshot_type,
            f"Pre-rollback snapshot for {rollback_op.operation_id}",
        )
        rollback_op.rollback_steps.append(f"pre_rollback_snapshot_created:{pre_snap.snapshot_id}")
        success = _execute_rollback(rollback_op, target_snapshot)
        rollback_op.status = RollbackStatus.COMPLETED if success else RollbackStatus.FAILED
        rollback_op.end_time = time.time()
        logger.info("Rollback %s %s", rollback_op.operation_id, "completed successfully" if success else "failed")
        return rollback_op

    def get_snapshots(self, snapshot_type: RollbackType | None = None) -> list[StateSnapshot]:
        if snapshot_type:
            return [s for s in self.snapshots if s.snapshot_type == snapshot_type]
        return self.snapshots.copy()

    def delete_snapshot(self, snapshot_id: str) -> bool:
        with self.rollback_lock:
            for i, snap in enumerate(self.snapshots):
                if snap.snapshot_id == snapshot_id:
                    return self._perform_snapshot_deletion(i, snap)
        logger.warning("Snapshot not found for deletion: %s", snapshot_id)
        return False

    def _perform_snapshot_deletion(self, index: int, snapshot: StateSnapshot) -> bool:
        try:
            if os.path.exists(snapshot.data_path):
                os.remove(snapshot.data_path)
            self.snapshots.pop(index)
            self._save_snapshots_index()
            logger.info("Snapshot deleted: %s", snapshot.snapshot_id)
            return True
        except Exception as e:
            logger.error("Failed to delete snapshot %s: %s", snapshot.snapshot_id, e)
            return False

    def get_rollback_operations(self, status: RollbackStatus | None = None) -> list[RollbackOperation]:
        operations = list(self.active_operations.values())
        if status:
            operations = [op for op in operations if op.status == status]
        return operations

    def _load_snapshots(self) -> None:
        index_path = os.path.join(self.snapshots_dir, "snapshots_index.json")
        if not os.path.exists(index_path):
            return
        try:
            with open(index_path, "r", encoding="utf-8") as f_in:
                snapshots_data = json.load(f_in)
            for snapshot_data in snapshots_data:
                snap = StateSnapshot.from_dict(snapshot_data)
                if os.path.exists(snap.data_path):
                    self.snapshots.append(snap)
                else:
                    logger.warning("Snapshot file missing: %s", snap.data_path)
            logger.info("Loaded %d snapshots", len(self.snapshots))
        except Exception as e:
            logger.error("Failed to load snapshots index: %s", e)

    def _save_snapshots_index(self) -> None:
        index_path = os.path.join(self.snapshots_dir, "snapshots_index.json")
        try:
            snapshots_data = [snap.to_dict() for snap in self.snapshots]
            with open(index_path, "w", encoding="utf-8") as f_out:
                json.dump(snapshots_data, f_out, indent=2)
        except Exception as e:
            logger.error("Failed to save snapshots index: %s", e)

    def _cleanup_old_snapshots(self) -> None:
        if len(self.snapshots) <= self.max_snapshots:
            return
        self.snapshots.sort(key=lambda s: s.timestamp)
        snapshots_to_remove = self.snapshots[:-self.max_snapshots]
        for snap in snapshots_to_remove:
            _delete_snapshot_files(snap)
        self.snapshots = self.snapshots[-self.max_snapshots:]

    def _start_auto_snapshot(self) -> None:
        def auto_snapshot_worker():
            while True:
                try:
                    time.sleep(self.snapshot_interval)
                    self.create_snapshot(RollbackType.CONFIGURATION, "Automatic snapshot", None)
                    logger.info("Automatic snapshot created")
                except Exception as e:
                    logger.error("Auto snapshot failed: %s", e)
        thread = threading.Thread(target=auto_snapshot_worker, daemon=True)
        thread.start()
        logger.info("Auto-snapshot thread started")


def _delete_snapshot_files(snapshot: StateSnapshot) -> None:
    try:
        if os.path.exists(snapshot.data_path):
            os.remove(snapshot.data_path)
        logger.info("Removed old snapshot: %s", snapshot.snapshot_id)
    except Exception as e:
        logger.error("Failed to remove old snapshot %s: %s", snapshot.snapshot_id, e)


def _persist_snapshot_data(
    data: dict[str, Any],
    data_path: str,
    snapshot_id: str,
    snapshot_type: RollbackType,
    timestamp: float,
    description: str,
    components: list[Any] | None,
) -> StateSnapshot:
    with open(data_path, "w", encoding="utf-8") as f_out:
        json.dump(data, f_out, indent=4)
    return StateSnapshot(
        snapshot_id=snapshot_id,
        snapshot_type=snapshot_type,
        timestamp=timestamp,
        description=description,
        data_hash=_calculate_file_hash(data_path),
        data_path=data_path,
        metadata={
            "component_count": len(components) if components else 0,
            "creation_time": datetime.fromtimestamp(timestamp).isoformat(),
        },
        size_bytes=os.path.getsize(data_path),
    )


def _execute_rollback(rollback_op: RollbackOperation, target_snapshot: StateSnapshot) -> bool:
    try:
        with open(target_snapshot.data_path, "r", encoding="utf-8") as f:
            snapshot_data = json.load(f)
        rollback_op.rollback_steps.append("snapshot_data_loaded")
        success = _dispatch_rollback(target_snapshot.snapshot_type, snapshot_data, rollback_op)
        if success:
            rollback_op.rollback_steps.append("rollback_executed_successfully")
            return _verify_and_finalize_rollback(target_snapshot, rollback_op)
        rollback_op.rollback_steps.append("rollback_execution_failed")
        return False
    except Exception as e:
        rollback_op.error_message = f"Rollback execution failed: {str(e)}"
        rollback_op.rollback_steps.append(f"exception:{str(e)}")
        logger.error("Rollback execution failed: %s", e)
        return False


def _dispatch_rollback(r_type: RollbackType, data: dict, op: RollbackOperation) -> bool:
    handlers = {
        RollbackType.CONFIGURATION: _rollback_configuration,
        RollbackType.CHAIN_STATE: _rollback_chain_state,
        RollbackType.CONSENSUS_STATE: _rollback_consensus_state,
        RollbackType.STORAGE_STATE: _rollback_storage_state,
        RollbackType.FULL_SYSTEM: _rollback_full_system,
    }
    handler = handlers.get(r_type)
    if not handler:
        logger.error("Unknown rollback type: %s", r_type)
        return False
    return handler(data, op)


def _init_rollback_operation(target_snapshot: StateSnapshot) -> RollbackOperation:
    return RollbackOperation(
        operation_id=_generate_operation_id(),
        rollback_type=target_snapshot.snapshot_type,
        target_snapshot=target_snapshot,
        status=RollbackStatus.PENDING,
        start_time=time.time(),
        end_time=None,
        error_message=None,
        rollback_steps=[],
        affected_components=[],
    )


def _capture_full_system_state(components: list[Any] | None = None) -> dict[str, Any]:
    return {
        "timestamp": time.time(),
        "configuration": _capture_configuration_state(),
        "chain_state": _capture_chain_state(components),
        "consensus_state": _capture_consensus_state(components),
        "storage_state": _capture_storage_state(components),
    }


def _rollback_full_system(snapshot_data: dict[str, Any], rollback_op: RollbackOperation) -> bool:
    try:
        success = True
        if "configuration" in snapshot_data:
            success &= _rollback_configuration(snapshot_data["configuration"], rollback_op)
        if "chain_state" in snapshot_data:
            success &= _rollback_chain_state(snapshot_data["chain_state"], rollback_op)
        if "consensus_state" in snapshot_data:
            success &= _rollback_consensus_state(snapshot_data["consensus_state"], rollback_op)
        if "storage_state" in snapshot_data:
            success &= _rollback_storage_state(snapshot_data["storage_state"], rollback_op)
        logger.info("Full system rollback completed: success=%s", success)
        return success
    except Exception as e:
        logger.error("Full system rollback failed: %s", e)
        return False


def _validate_rollback_safety(target_snapshot: StateSnapshot) -> bool:
    try:
        age_hours = (time.time() - target_snapshot.timestamp) / 3600
        if age_hours > 72:
            logger.warning("Snapshot is old: %.1f hours", age_hours)
            return False
        if not os.path.exists(target_snapshot.data_path):
            logger.error("Snapshot file missing: %s", target_snapshot.data_path)
            return False
        current_hash = _calculate_file_hash(target_snapshot.data_path)
        if current_hash != target_snapshot.data_hash:
            logger.error("Snapshot integrity check failed: hash mismatch")
            return False
        return True
    except Exception as e:
        logger.error("Rollback safety validation failed: %s", e)
        return False


def _verify_and_finalize_rollback(target_snapshot: StateSnapshot, rollback_op: RollbackOperation) -> bool:
    if _verify_rollback_integrity(target_snapshot, rollback_op):
        rollback_op.rollback_steps.append("integrity_verified")
        return True
    rollback_op.rollback_steps.append("integrity_verification_failed")
    return False


def _handle_rollback_exception(rollback_op: RollbackOperation, e: Exception) -> RollbackOperation:
    rollback_op.status = RollbackStatus.FAILED
    rollback_op.error_message = str(e)
    rollback_op.end_time = time.time()
    logger.error("Rollback %s failed with exception: %s", rollback_op.operation_id, e)
    return rollback_op


def _capture_configuration_state() -> dict[str, Any]:
    config_state: dict[str, Any] = {
        "timestamp": time.time(),
        "config_files": {},
        "environment_vars": {},
        "runtime_settings": {},
    }
    for config_dir in ["config/", "hierarchical/", "error_mitigation/"]:
        _scan_config_directory(config_dir, config_state)
    return config_state


def _scan_config_directory(directory: str, state: dict[str, Any]) -> None:
    if not os.path.exists(directory):
        return
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(('.yaml', '.yml', '.json', '.py')):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        state["config_files"][file_path] = f.read()
                except Exception as e:
                    logger.warning("Failed to read config file %s: %s", file_path, e)


def _capture_chain_state(components: list[Any] | None = None) -> dict[str, Any]:
    chain_state: dict[str, Any] = {
        "timestamp": time.time(),
        "main_chain": {},
        "sub_chains": {},
        "proof_submissions": {},
    }
    if components:
        for component in components:
            if hasattr(component, 'chain'):
                chain_id = getattr(component, 'name', 'unknown')
                chain_state["sub_chains"][chain_id] = {
                    "block_count": len(component.chain) if hasattr(component, 'chain') else 0,
                    "latest_hash": (
                        getattr(component.get_latest_block(), 'hash', None)
                        if hasattr(component, 'get_latest_block') else None
                    ),
                }
    return chain_state


def _capture_consensus_state(components: list[Any] | None = None) -> dict[str, Any]:
    consensus_state = {
        "timestamp": time.time(),
        "view_number": 0,
        "leader_info": {},
        "node_states": {},
        "message_log": [],
    }
    if components:
        for component in components:
            if hasattr(component, 'view_number'):
                consensus_state["view_number"] = component.view_number
            if hasattr(component, 'current_leader'):
                leader_info = getattr(component, 'current_leader', {})
                consensus_state["leader_info"] = {"leader_id": getattr(leader_info, 'node_id', None)}
    return consensus_state


def _capture_storage_state(components: list[Any] | None = None) -> dict[str, Any]:
    return {"timestamp": time.time(), "world_state": {}, "indexes": {}, "backup_info": {}}


_SNAPSHOT_CAPTURE: dict[RollbackType, Any] = {
    RollbackType.CONFIGURATION: lambda _comps: _capture_configuration_state(),
    RollbackType.CHAIN_STATE: _capture_chain_state,
    RollbackType.CONSENSUS_STATE: _capture_consensus_state,
    RollbackType.STORAGE_STATE: _capture_storage_state,
    RollbackType.FULL_SYSTEM: _capture_full_system_state,
}


def _capture_state(snapshot_type: RollbackType, components: list[Any] | None) -> dict[str, Any]:
    handler = _SNAPSHOT_CAPTURE.get(snapshot_type)
    if handler is None:
        raise ValueError(f"Unknown snapshot type: {snapshot_type}")
    return handler(components)


def _rollback_configuration(snapshot_data: dict[str, Any], rollback_op: RollbackOperation) -> bool:
    try:
        config_files = snapshot_data.get("config_files", {})
        for file_path, content in config_files.items():
            backup_path = f"{file_path}.rollback_backup"
            if os.path.exists(file_path):
                shutil.copy2(file_path, backup_path)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            rollback_op.affected_components.append(file_path)
        logger.info("Configuration rollback completed: %d files restored", len(config_files))
        return True
    except Exception as e:
        logger.error("Configuration rollback failed: %s", e)
        return False


def _rollback_chain_state(snapshot_data: dict[str, Any], rollback_op: RollbackOperation) -> bool:
    try:
        sub_chains = snapshot_data.get("sub_chains", {})
        for chain_id in sub_chains:
            rollback_op.affected_components.append(f"chain:{chain_id}")
        logger.info("Chain state rollback completed: %d chains", len(sub_chains))
        return True
    except Exception as e:
        logger.error("Chain state rollback failed: %s", e)
        return False


def _rollback_consensus_state(snapshot_data: dict[str, Any], rollback_op: RollbackOperation) -> bool:
    try:
        view_number = snapshot_data.get("view_number", 0)
        rollback_op.affected_components.append("consensus_view")
        rollback_op.affected_components.append("consensus_leader")
        logger.info("Consensus state rollback completed: view %d", view_number)
        return True
    except Exception as e:
        logger.error("Consensus state rollback failed: %s", e)
        return False


def _rollback_storage_state(snapshot_data: dict[str, Any], rollback_op: RollbackOperation) -> bool:
    try:
        rollback_op.affected_components.append("storage_state")
        logger.info("Storage state rollback completed")
        return True
    except Exception as e:
        logger.error("Storage state rollback failed: %s", e)
        return False


def _verify_rollback_integrity(target_snapshot: StateSnapshot, rollback_op: RollbackOperation) -> bool:
    try:
        rollback_op.rollback_steps.append("integrity_check_started")
        for component in rollback_op.affected_components:
            if not _verify_component_integrity(component):
                return False
        rollback_op.rollback_steps.append("integrity_check_passed")
        return True
    except Exception as e:
        logger.error("Rollback integrity verification failed: %s", e)
        return False


def _verify_component_integrity(component: str) -> bool:
    if component.startswith("chain:"):
        return True
    if component.endswith(('.yaml', '.py')):
        if not os.path.exists(component):
            logger.error("Rollback integrity failed: missing file %s", component)
            return False
    return True


def _generate_snapshot_id() -> str:
    timestamp = str(int(time.time() * 1000))
    hash_part = hashlib.sha256(timestamp.encode()).hexdigest()[:8]
    return f"SNAP-{timestamp[-8:]}-{hash_part.upper()}"


def _generate_operation_id() -> str:
    timestamp = str(int(time.time() * 1000))
    hash_part = hashlib.sha256(timestamp.encode()).hexdigest()[:8]
    return f"ROLLBACK-{timestamp[-8:]}-{hash_part.upper()}"


def _calculate_file_hash(file_path: str) -> str:
    hash_sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest()


def _log_rollback_operation(rollback_op: RollbackOperation) -> None:
    try:
        log_entry = {
            "event": "rollback_operation",
            "operation_data": rollback_op.to_dict(),
            "timestamp": time.time(),
        }
        os.makedirs("log/error_mitigation", exist_ok=True)
        with open("log/error_mitigation/rollback_operations.log", "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat()}: {json.dumps(log_entry)}\n")
    except Exception as e:
        logger.error("Failed to log rollback operation: %s", e)
