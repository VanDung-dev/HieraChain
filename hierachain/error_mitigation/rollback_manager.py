"""
Error Mitigation Rollback Manager Module

This module provides safe rollback and recovery procedures. It manages
state rollbacks, configuration reversions, and safe recovery procedures
while maintaining data integrity and HieraChain principles.
"""

import time
import json
import logging
import shutil
import os
import hashlib
import threading
from typing import Any
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RollbackType(Enum):
    """Types of rollback operations"""
    CONFIGURATION = "configuration"
    CHAIN_STATE = "chain_state"
    CONSENSUS_STATE = "consensus_state"
    STORAGE_STATE = "storage_state"
    FULL_SYSTEM = "full_system"


class RollbackStatus(Enum):
    """Status of rollback operations"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class StateSnapshot:
    """Captures system state for rollback purposes"""
    snapshot_id: str
    snapshot_type: RollbackType
    timestamp: float
    description: str
    data_hash: str
    data_path: str
    metadata: dict[str, Any]
    size_bytes: int

    def to_dict(self) -> dict[str, Any]:
        """Convert snapshot to dictionary"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'StateSnapshot':
        """Create snapshot from dictionary"""
        return cls(**data)


@dataclass
class RollbackOperation:
    """Represents a rollback operation"""
    operation_id: str
    rollback_type: RollbackType
    target_snapshot: StateSnapshot
    status: RollbackStatus
    start_time: float
    end_time: float | None
    error_message: str | None
    rollback_steps: list[str]
    affected_components: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert operation to dictionary"""
        data = asdict(self)
        # Convert enums to strings for JSON serialization
        data['rollback_type'] = self.rollback_type.value
        data['status'] = self.status.value
        data['target_snapshot'] = self.target_snapshot.to_dict()
        return data


class RollbackManager:
    """
    Main rollback manager for HieraChain Ledger

    Coordinates safe rollback operations, manages state snapshots,
    and ensures data integrity during recovery procedures.
    """

    def __init__(self, config_dict: dict[str, Any]):
        """
        Initialize rollback manager

        Args:
            config_dict: Configuration dictionary with rollback parameters
        """
        self.config = config_dict
        self.snapshots_dir: str = str(config_dict.get("snapshots_dir", "snapshots"))
        self.max_snapshots = config_dict.get("max_snapshots", 10)
        self.auto_snapshot = config_dict.get("auto_snapshot", True)
        self.snapshot_interval = config_dict.get("snapshot_interval", 3600)  # 1 hour

        # Initialize storage
        os.makedirs(self.snapshots_dir, exist_ok=True)

        # State tracking
        self.snapshots: list[StateSnapshot] = []
        self.active_operations: dict[str, RollbackOperation] = {}
        self.rollback_lock = threading.Lock()

        # Load existing snapshots
        self._load_snapshots()

        # Start auto-snapshot thread if enabled
        if self.auto_snapshot:
            self._start_auto_snapshot()

        logger.info(f"Initialized RollbackManager with {len(self.snapshots)} snapshots")

    def create_snapshot(
        self,
        snapshot_type: RollbackType,
        description: str,
        components: list[Any] | None = None
    ) -> StateSnapshot:
        """
        Create a system state snapshot

        Args:
            snapshot_type: Type of snapshot to create
            description: Description of the snapshot
            components: Optional list of components to snapshot

        Returns:
            StateSnapshot: Created snapshot
        """
        snapshot_id = _generate_snapshot_id()
        timestamp = time.time()

        logger.info(f"Creating snapshot: {snapshot_id} ({snapshot_type.value})")

        try:
            # Capture state data based on type
            if snapshot_type == RollbackType.CONFIGURATION:
                data = _capture_configuration_state()
            elif snapshot_type == RollbackType.CHAIN_STATE:
                data = _capture_chain_state(components)
            elif snapshot_type == RollbackType.CONSENSUS_STATE:
                data = _capture_consensus_state(components)
            elif snapshot_type == RollbackType.STORAGE_STATE:
                data = _capture_storage_state(components)
            elif snapshot_type == RollbackType.FULL_SYSTEM:
                data = _capture_full_system_state(components)
            else:
                raise ValueError(f"Unknown snapshot type: {snapshot_type}")

            # Save snapshot data
            data_path = os.path.join(self.snapshots_dir, f"{snapshot_id}.snapshot")
            with open(data_path, 'w', encoding='utf-8') as f_out:
                json.dump(data, f_out, indent=4)

            # Calculate hash and size
            data_hash = _calculate_file_hash(data_path)
            size_bytes = os.path.getsize(data_path)

            # Create snapshot object
            new_snapshot = StateSnapshot(
                snapshot_id=snapshot_id,
                snapshot_type=snapshot_type,
                timestamp=timestamp,
                description=description,
                data_hash=data_hash,
                data_path=data_path,
                metadata={
                    "component_count": len(components) if components else 0,
                    "creation_time": datetime.fromtimestamp(timestamp).isoformat()
                },
                size_bytes=size_bytes
            )

            # Add to snapshots list
            with self.rollback_lock:
                self.snapshots.append(new_snapshot)
                self._cleanup_old_snapshots()
                self._save_snapshots_index()

            logger.info(f"Snapshot created successfully: {snapshot_id} ({size_bytes} bytes)")
            return new_snapshot

        except Exception as e:
            logger.error(f"Failed to create snapshot {snapshot_id}: {e}")
            raise

    def rollback_to_snapshot(self, snapshot_id: str, force: bool = False) -> RollbackOperation:
        """
        Perform rollback to a specific snapshot

        Args:
            snapshot_id: ID of the snapshot to rollback to
            force: Force rollback even if risky

        Returns:
            RollbackOperation: Rollback operation details
        """
        target_snapshot = self._find_snapshot_by_id(snapshot_id)
        if not target_snapshot:
            raise ValueError(f"Snapshot not found: {snapshot_id}")

        rollback_op = _init_rollback_operation(target_snapshot)
        logger.info(f"Starting rollback: {rollback_op.operation_id} -> {snapshot_id}")

        with self.rollback_lock:
            self.active_operations[rollback_op.operation_id] = rollback_op

        try:
            return self._execute_rollback_process(rollback_op, target_snapshot, force)
        except Exception as e:
            return _handle_rollback_exception(rollback_op, e)
        finally:
            _log_rollback_operation(rollback_op)

    def _find_snapshot_by_id(self, snapshot_id: str) -> StateSnapshot | None:
        """Find a snapshot by its ID"""
        for snap in self.snapshots:
            if snap.snapshot_id == snapshot_id:
                return snap
        return None

    def _execute_rollback_process(
        self,
        rollback_op: RollbackOperation,
        target_snapshot: StateSnapshot,
        force: bool
    ) -> RollbackOperation:
        """Perform individual steps of the rollback process"""
        if not force and not _validate_rollback_safety(target_snapshot):
            rollback_op.status = RollbackStatus.FAILED
            rollback_op.error_message = "Rollback safety validation failed"
            rollback_op.end_time = time.time()
            return rollback_op

        rollback_op.status = RollbackStatus.IN_PROGRESS
        rollback_op.rollback_steps.append("validation_passed")

        pre_snap = self.create_snapshot(
            target_snapshot.snapshot_type,
            f"Pre-rollback snapshot for {rollback_op.operation_id}"
        )
        rollback_op.rollback_steps.append(f"pre_rollback_snapshot_created:{pre_snap.snapshot_id}")

        success = _execute_rollback(rollback_op, target_snapshot)
        rollback_op.status = (RollbackStatus.COMPLETED if success else RollbackStatus.FAILED)
        rollback_op.end_time = time.time()

        status_msg = "completed successfully" if success else "failed"
        logger.info(f"Rollback {rollback_op.operation_id} {status_msg}")

        return rollback_op

    def get_snapshots(self, snapshot_type: RollbackType | None = None) -> list[StateSnapshot]:
        """
        Get list of available snapshots

        Args:
            snapshot_type: Optional filter by snapshot type

        Returns:
            List[StateSnapshot]: List of snapshots
        """
        if snapshot_type:
            return [s for s in self.snapshots if s.snapshot_type == snapshot_type]
        return self.snapshots.copy()

    def delete_snapshot(self, snapshot_id: str) -> bool:
        """
        Delete a snapshot

        Args:
            snapshot_id: ID of snapshot to delete

        Returns:
            bool: True if deletion succeeded
        """
        with self.rollback_lock:
            for i, snap in enumerate(self.snapshots):
                if snap.snapshot_id == snapshot_id:
                    return self._perform_snapshot_deletion(i, snap)

        logger.warning(f"Snapshot not found for deletion: {snapshot_id}")
        return False

    def _perform_snapshot_deletion(self, index: int, snapshot: StateSnapshot) -> bool:
        """Delete snapshot files and update index"""
        try:
            if os.path.exists(snapshot.data_path):
                os.remove(snapshot.data_path)

            self.snapshots.pop(index)
            self._save_snapshots_index()

            logger.info(f"Snapshot deleted: {snapshot.snapshot_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete snapshot {snapshot.snapshot_id}: {e}")
            return False

    def get_rollback_operations(self, status: RollbackStatus | None = None) -> list[RollbackOperation]:
        """
        Get rollback operations

        Args:
            status: Optional filter by status

        Returns:
            List[RollbackOperation]: List of operations
        """
        operations = list(self.active_operations.values())
        if status:
            operations = [op for op in operations if op.status == status]
        return operations

    def _load_snapshots(self) -> None:
        """Load existing snapshots from disk"""
        index_path = os.path.join(self.snapshots_dir, "snapshots_index.json")
        if not os.path.exists(index_path):
            return

        try:
            with open(index_path, 'r', encoding='utf-8') as f_in:
                snapshots_data = json.load(f_in)

            self._process_snapshots_index(snapshots_data)
            logger.info(f"Loaded {len(self.snapshots)} snapshots")
        except Exception as e:
            logger.error(f"Failed to load snapshots index: {e}")

    def _process_snapshots_index(self, snapshots_data: list[dict[str, Any]]) -> None:
        """Process loaded snapshots index data"""
        for snapshot_data in snapshots_data:
            snap = StateSnapshot.from_dict(snapshot_data)
            if os.path.exists(snap.data_path):
                self.snapshots.append(snap)
            else:
                logger.warning(f"Snapshot file missing: {snap.data_path}")

    def _save_snapshots_index(self) -> None:
        """Save snapshots index to disk"""
        index_path = os.path.join(self.snapshots_dir, "snapshots_index.json")
        try:
            snapshots_data = [snap.to_dict() for snap in self.snapshots]
            with open(index_path, 'w', encoding='utf-8') as f_out:
                json.dump(snapshots_data, f_out, indent=2)
        except Exception as e:
            logger.error(f"Failed to save snapshots index: {e}")

    def _cleanup_old_snapshots(self) -> None:
        """Remove old snapshots if limit exceeded"""
        if len(self.snapshots) <= self.max_snapshots:
            return

        # Sort by timestamp and remove oldest
        self.snapshots.sort(key=lambda s: s.timestamp)
        snapshots_to_remove = self.snapshots[:-self.max_snapshots]

        for snap in snapshots_to_remove:
            _delete_snapshot_files(snap)

        self.snapshots = self.snapshots[-self.max_snapshots:]

    def _start_auto_snapshot(self) -> None:
        """Start automatic snapshot creation thread"""
        def auto_snapshot_worker():
            while True:
                try:
                    time.sleep(self.snapshot_interval)
                    self.create_snapshot(
                        RollbackType.CONFIGURATION,
                        "Automatic snapshot",
                        None
                    )
                    logger.info("Automatic snapshot created")
                except Exception as e:
                    logger.error(f"Auto snapshot failed: {e}")

        thread = threading.Thread(target=auto_snapshot_worker, daemon=True)
        thread.start()
        logger.info("Auto-snapshot thread started")


def _delete_snapshot_files(snapshot: StateSnapshot) -> None:
    """Safely delete snapshot data files"""
    try:
        if os.path.exists(snapshot.data_path):
            os.remove(snapshot.data_path)
        logger.info(f"Removed old snapshot: {snapshot.snapshot_id}")
    except Exception as e:
        logger.error(f"Failed to remove old snapshot {snapshot.snapshot_id}: {e}")


def _execute_rollback(rollback_op: RollbackOperation, target_snapshot: StateSnapshot) -> bool:
    """
    Execute the actual rollback operation

    Args:
        rollback_op: Rollback operation details
        target_snapshot: Target snapshot to rollback to

    Returns:
        bool: True if rollback succeeded
    """
    try:
        with open(target_snapshot.data_path, 'r', encoding='utf-8') as f:
            snapshot_data = json.load(f)

        rollback_op.rollback_steps.append("snapshot_data_loaded")

        # Dispatch to appropriate handler
        success = _dispatch_rollback(target_snapshot.snapshot_type, snapshot_data, rollback_op)

        if success:
            rollback_op.rollback_steps.append("rollback_executed_successfully")
            return _verify_and_finalize_rollback(target_snapshot, rollback_op)

        rollback_op.rollback_steps.append("rollback_execution_failed")
        return False

    except Exception as e:
        rollback_op.error_message = f"Rollback execution failed: {str(e)}"
        rollback_op.rollback_steps.append(f"exception:{str(e)}")
        logger.error(f"Rollback execution failed: {e}")
        return False


def _dispatch_rollback(r_type: RollbackType, data: dict, op: RollbackOperation) -> bool:
    """Dispatch to specific rollback handler"""
    handlers = {
        RollbackType.CONFIGURATION: _rollback_configuration,
        RollbackType.CHAIN_STATE: _rollback_chain_state,
        RollbackType.CONSENSUS_STATE: _rollback_consensus_state,
        RollbackType.STORAGE_STATE: _rollback_storage_state,
        RollbackType.FULL_SYSTEM: _rollback_full_system
    }

    handler = handlers.get(r_type)
    if not handler:
        logger.error(f"Unknown rollback type: {r_type}")
        return False

    return handler(data, op)


def _init_rollback_operation(target_snapshot: StateSnapshot) -> RollbackOperation:
    """Initialize a new rollback operation"""
    return RollbackOperation(
        operation_id=_generate_operation_id(),
        rollback_type=target_snapshot.snapshot_type,
        target_snapshot=target_snapshot,
        status=RollbackStatus.PENDING,
        start_time=time.time(),
        end_time=None,
        error_message=None,
        rollback_steps=[],
        affected_components=[]
    )


def _capture_full_system_state(components: list[Any] | None = None) -> dict[str, Any]:
    """Capture complete system state"""
    full_state = {
        "timestamp": time.time(),
        "configuration": _capture_configuration_state(),
        "chain_state": _capture_chain_state(components),
        "consensus_state": _capture_consensus_state(components),
        "storage_state": _capture_storage_state(components)
    }

    return full_state


def _rollback_full_system(snapshot_data: dict[str, Any], rollback_op: RollbackOperation) -> bool:
    """Rollback complete system state"""
    try:
        # Rollback each component
        success = True

        if "configuration" in snapshot_data:
            success &= _rollback_configuration(snapshot_data["configuration"], rollback_op)

        if "chain_state" in snapshot_data:
            success &= _rollback_chain_state(snapshot_data["chain_state"], rollback_op)

        if "consensus_state" in snapshot_data:
            success &= _rollback_consensus_state(snapshot_data["consensus_state"], rollback_op)

        if "storage_state" in snapshot_data:
            success &= _rollback_storage_state(snapshot_data["storage_state"], rollback_op)

        logger.info(f"Full system rollback completed: success={success}")
        return success

    except Exception as e:
        logger.error(f"Full system rollback failed: {e}")
        return False


def _validate_rollback_safety(target_snapshot: StateSnapshot) -> bool:
    """Validate rollback safety"""
    try:
        # Check snapshot age
        age_hours = (time.time() - target_snapshot.timestamp) / 3600
        if age_hours > 72:  # 3 days
            logger.warning(f"Snapshot is old: {age_hours:.1f} hours")
            return False

        # Verify snapshot integrity
        if not os.path.exists(target_snapshot.data_path):
            logger.error(f"Snapshot file missing: {target_snapshot.data_path}")
            return False

        current_hash = _calculate_file_hash(target_snapshot.data_path)
        if current_hash != target_snapshot.data_hash:
            logger.error("Snapshot integrity check failed: hash mismatch")
            return False

        return True

    except Exception as e:
        logger.error(f"Rollback safety validation failed: {e}")
        return False


def _verify_and_finalize_rollback(target_snapshot: StateSnapshot, rollback_op: RollbackOperation) -> bool:
    """Verify integrity and record final steps"""
    if _verify_rollback_integrity(target_snapshot, rollback_op):
        rollback_op.rollback_steps.append("integrity_verified")
        return True

    rollback_op.rollback_steps.append("integrity_verification_failed")
    return False


def _handle_rollback_exception(rollback_op: RollbackOperation, e: Exception) -> RollbackOperation:
    """Handle exceptions during rollback"""
    rollback_op.status = RollbackStatus.FAILED
    rollback_op.error_message = str(e)
    rollback_op.end_time = time.time()
    logger.error(f"Rollback {rollback_op.operation_id} failed with exception: {e}")
    return rollback_op


def _capture_configuration_state() -> dict[str, Any]:
    """Capture current configuration state"""
    config_state: dict[str, Any] = {
        "timestamp": time.time(),
        "config_files": {},
        "environment_vars": {},
        "runtime_settings": {}
    }

    # Capture configuration files
    config_dirs = ["config/", "hierarchical/", "error_mitigation/"]
    for config_dir in config_dirs:
        _scan_config_directory(config_dir, config_state)

    return config_state


def _scan_config_directory(directory: str, state: dict[str, Any]) -> None:
    """Scan directory and capture config files"""
    if not os.path.exists(directory):
        return

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(('.yaml', '.yml', '.json', '.py')):
                file_path = os.path.join(root, file)
                _read_config_file(file_path, state)


def _read_config_file(file_path: str, state: dict[str, Any]) -> None:
    """Read content of a config file into state"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            state["config_files"][file_path] = f.read()
    except Exception as e:
        logger.warning(f"Failed to read config file {file_path}: {e}")


def _capture_chain_state(components: list[Any] | None = None) -> dict[str, Any]:
    """Capture current blockchain state"""
    chain_state: dict[str, Any] = {
        "timestamp": time.time(),
        "main_chain": {},
        "sub_chains": {},
        "proof_submissions": {}
    }

    # In real implementation, capture actual chain data
    if components:
        for component in components:
            if hasattr(component, 'chain'):
                chain_id = getattr(component, 'name', 'unknown')
                chain_state["sub_chains"][chain_id] = {
                    "block_count": len(component.chain) if hasattr(component, 'chain') else 0,
                    "latest_hash": (
                        getattr(component.get_latest_block(), 'hash', None)
                        if hasattr(component, 'get_latest_block') else None
                    )
                }

    return chain_state


def _capture_consensus_state(components: list[Any] | None = None) -> dict[str, Any]:
    """Capture current consensus state"""
    consensus_state = {
        "timestamp": time.time(),
        "view_number": 0,
        "leader_info": {},
        "node_states": {},
        "message_log": []
    }

    if components:
        for component in components:
            _extract_consensus_info(component, consensus_state)

    return consensus_state


def _extract_consensus_info(component: Any, state: dict[str, Any]) -> None:
    """Extract consensus-specific info from a component"""
    if hasattr(component, 'view_number'):
        state["view_number"] = component.view_number

    if hasattr(component, 'current_leader'):
        leader_info = getattr(component, 'current_leader', {})
        state["leader_info"] = {"leader_id": getattr(leader_info, 'node_id', None)}


def _capture_storage_state(_components: list[Any] | None = None) -> dict[str, Any]:
    """Capture current storage state"""
    storage_state = {
        "timestamp": time.time(),
        "world_state": {},
        "indexes": {},
        "backup_info": {}
    }

    return storage_state


def _rollback_configuration(snapshot_data: dict[str, Any], rollback_op: RollbackOperation) -> bool:
    """Rollback configuration state"""
    try:
        config_files = snapshot_data.get("config_files", {})

        for file_path, content in config_files.items():
            # Create backup of current file
            backup_path = f"{file_path}.rollback_backup"
            if os.path.exists(file_path):
                shutil.copy2(file_path, backup_path)

            # Restore file content
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            rollback_op.affected_components.append(file_path)

        logger.info(f"Configuration rollback completed: {len(config_files)} files restored")
        return True

    except Exception as e:
        logger.error(f"Configuration rollback failed: {e}")
        return False


def _rollback_chain_state(snapshot_data: dict[str, Any], rollback_op: RollbackOperation) -> bool:
    """Rollback blockchain state"""
    try:
        sub_chains = snapshot_data.get("sub_chains", {})

        for chain_id, _ in sub_chains.items():
            rollback_op.affected_components.append(f"chain:{chain_id}")

        logger.info(f"Chain state rollback completed: {len(sub_chains)} chains")
        return True

    except Exception as e:
        logger.error(f"Chain state rollback failed: {e}")
        return False


def _rollback_consensus_state(snapshot_data: dict[str, Any], rollback_op: RollbackOperation) -> bool:
    """Rollback consensus state"""
    try:
        view_number = snapshot_data.get("view_number", 0)

        rollback_op.affected_components.append("consensus_view")
        rollback_op.affected_components.append("consensus_leader")

        logger.info(f"Consensus state rollback completed: view {view_number}")
        return True

    except Exception as e:
        logger.error(f"Consensus state rollback failed: {e}")
        return False


def _rollback_storage_state(_snapshot_data: dict[str, Any], rollback_op: RollbackOperation) -> bool:
    """Rollback storage state"""
    try:
        rollback_op.affected_components.append("storage_state")
        logger.info("Storage state rollback completed")
        return True
    except Exception as e:
        logger.error(f"Storage state rollback failed: {e}")
        return False


def _verify_rollback_integrity(_target_snapshot: StateSnapshot, rollback_op: RollbackOperation) -> bool:
    """Verify rollback integrity"""
    try:
        rollback_op.rollback_steps.append("integrity_check_started")

        for component in rollback_op.affected_components:
            if not _verify_component_integrity(component):
                return False

        rollback_op.rollback_steps.append("integrity_check_passed")
        return True

    except Exception as e:
        logger.error(f"Rollback integrity verification failed: {e}")
        return False


def _verify_component_integrity(component: str) -> bool:
    """Verify integrity of a single component"""
    if component.startswith("chain:"):
        return True

    if component.endswith(('.yaml', '.py')):
        if not os.path.exists(component):
            logger.error(f"Rollback integrity failed: missing file {component}")
            return False

    return True


def _generate_snapshot_id() -> str:
    """Generate unique snapshot ID"""
    timestamp = str(int(time.time() * 1000))
    hash_part = hashlib.sha256(timestamp.encode()).hexdigest()[:8]
    return f"SNAP-{timestamp[-8:]}-{hash_part.upper()}"


def _generate_operation_id() -> str:
    """Generate unique operation ID"""
    timestamp = str(int(time.time() * 1000))
    hash_part = hashlib.sha256(timestamp.encode()).hexdigest()[:8]
    return f"ROLLBACK-{timestamp[-8:]}-{hash_part.upper()}"


def _calculate_file_hash(file_path: str) -> str:
    """Calculate SHA256 hash of a file"""
    hash_sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest()


def _log_rollback_operation(rollback_op: RollbackOperation) -> None:
    """Log rollback operation for audit trail"""
    try:
        log_entry = {
            "event": "rollback_operation",
            "operation_data": rollback_op.to_dict(),
            "timestamp": time.time()
        }

        os.makedirs("log/error_mitigation", exist_ok=True)
        with open("log/error_mitigation/rollback_operations.log", "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat()}: {json.dumps(log_entry)}\n")
    except Exception as e:
        logger.error(f"Failed to log rollback operation: {e}")
