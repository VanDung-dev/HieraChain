"""
Error Mitigation Validator Module

This module provides comprehensive validation mechanisms. It includes
validators for consensus, encryption, resources, and other critical system
components.
"""

import time
import json
import logging
import hashlib
import os
from typing import Any
from datetime import datetime
import pyarrow as pa
import pyarrow.compute as pc

LOCALIZED_MESSAGES = {
    "default": "Unknown error occurred",
    "invalid_input": "Invalid input provided",
    "security_violation": "Security policy violation detected",
    "insufficient_nodes": "Insufficient nodes for BFT consensus"
}

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when validation fails with localized messages"""
    def __init__(self, msg_code):
        self.message = LOCALIZED_MESSAGES.get(msg_code, 'Unknown error')
        super().__init__(self.message)


class ConfigurationError(Exception):
    """Raised when configuration is invalid"""
    pass


class SecurityError(Exception):
    """Raised when security validation fails"""
    def __init__(self, message):
        super().__init__(message)
        self.message = message


def _log_scaling_event(event: dict[str, Any]) -> None:
    """
    Log scaling events for audit trail

    Args:
        event: Scaling event details
    """
    try:
        log_entry = json.dumps(event, indent=2)
        logger.info(f"Scaling event logged: {log_entry}")

        # Write to audit log file
        os.makedirs("log/error_mitigation", exist_ok=True)
        with open("log/error_mitigation/consensus_scaling.log", "a") as f:
            f.write(f"{datetime.now().isoformat()}: {log_entry}\n")
    except (IOError, OSError, ValueError) as ex:
        logger.error(f"Failed to log scaling event: {ex}")


def _is_string_type(type_: pa.DataType) -> bool:
    """Check for string or large string types."""
    return pa.types.is_string(type_) or pa.types.is_large_string(type_)


def _is_list_type(type_: pa.DataType) -> bool:
    """Check for list or large list types."""
    return pa.types.is_list(type_) or pa.types.is_large_list(type_)


class ConsensusValidator:
    """
    Automated validator for BFT consensus requirements

    Validates that the consensus mechanism meets Byzantine Fault Tolerance
    requirements, including proper node count (n >= 3f + 1) and node health.
    """

    def __init__(self, consensus_config: dict[str, Any]):
        """
        Initialize consensus validator

        Args:
            consensus_config: Configuration dictionary with consensus parameters
        """
        self.config = consensus_config
        self.f = self.config.get("f", 1)  # Number of faulty nodes to tolerate
        self.auto_scale_threshold = self.config.get("auto_scale_threshold", 0.8)
        self.health_check_interval = self.config.get("health_check_interval", 30)

        logger.info(f"Initialized ConsensusValidator with f={self.f}")

    def validate_node_count(self, current_nodes: list[Any]) -> bool:
        """
        Check if node count meets BFT requirement: n >= 3f + 1

        Args:
            current_nodes: List of current consensus nodes

        Returns:
            bool: True if node count is sufficient

        Raises:
            ValidationError: If insufficient nodes for BFT
        """
        required_nodes = 3 * self.f + 1
        actual_nodes = len(current_nodes)

        if actual_nodes < required_nodes:
            error_msg = (
                f"Insufficient nodes for BFT consensus: {actual_nodes} < "
                f"{required_nodes}. For f={self.f} faulty nodes tolerance, "
                f"need at least {required_nodes} nodes. Auto-scaling initiated."
            )
            logger.error(error_msg)
            raise ValidationError("insufficient_nodes")

        logger.info(f"Node count validation passed: {actual_nodes} >= {required_nodes}")
        return True

    def monitor_and_scale(self, current_nodes: list[Any]) -> list[Any]:
        """
        Monitor node health and trigger auto-scaling if needed

        Args:
            current_nodes: List of current consensus nodes

        Returns:
            List[Any]: List of healthy nodes
        """
        healthy_nodes = [node for node in current_nodes if self._is_healthy(node)]
        health_ratio = len(healthy_nodes) / len(current_nodes) if current_nodes else 0

        logger.info(f"Node health check: {len(healthy_nodes)}/{len(current_nodes)} healthy")

        if health_ratio < self.auto_scale_threshold:
            logger.warning(
                f"Health ratio {health_ratio:.2f} below threshold {self.auto_scale_threshold}"
            )
            self._trigger_scaling(healthy_nodes)

        return healthy_nodes

    def _is_healthy(self, node: Any) -> bool:
        """
        Check if a node is healthy via heartbeat and status

        Args:
            node: Node object to check

        Returns:
            bool: True if node is healthy
        """
        try:
            # Check if node has required attributes
            if not hasattr(node, 'health_status') or not hasattr(node, 'last_heartbeat'):
                node_id = getattr(node, "node_id", "unknown")
                logger.warning(f"Node {node_id} missing health attributes")
                return False

            # Check status and heartbeat timing
            is_active = node.health_status == "active"
            time_diff = time.time() - node.last_heartbeat
            heartbeat_fresh = time_diff < self.health_check_interval

            return is_active and heartbeat_fresh
        except (AttributeError, TypeError, ValueError) as ex:
            logger.error(f"Error checking node health: {ex}")
            return False

    def _trigger_scaling(self, healthy_nodes: list[Any]) -> None:
        """
        Trigger auto-scaling to add more nodes

        Args:
            healthy_nodes: List of currently healthy nodes
        """
        logger.info(f"Triggering auto-scaling with {len(healthy_nodes)} healthy nodes")

        # In a real implementation, this would call an orchestrator like Kubernetes
        # For now, we log the scaling event
        scaling_event = {
            "event": "auto_scaling_triggered",
            "timestamp": time.time(),
            "healthy_nodes_count": len(healthy_nodes),
            "required_nodes": 3 * self.f + 1,
            "threshold": self.auto_scale_threshold
        }

        _log_scaling_event(scaling_event)


class EncryptionValidator:
    """
    Validates encryption configurations and algorithms

    Ensures only approved encryption algorithms are used and
    validates key rotation policies according to HieraChain security requirements.
    """

    def __init__(self, config: dict[str, Any]):
        """
        Initialize encryption validator

        Args:
            config: Encryption configuration dictionary
        """
        self.config = config
        self.allowed_algorithms = ["AES-256-GCM"]
        self.min_key_rotation_interval = 2592000  # 30 days in seconds

        logger.info("Initialized EncryptionValidator")

    def validate_config(self) -> bool:
        """
        Validate encryption configuration

        Returns:
            bool: True if configuration is valid

        Raises:
            SecurityError: If configuration is invalid
        """
        algorithm = self.config.get("algorithm")

        # Validate algorithm
        if algorithm not in self.allowed_algorithms:
            error_msg = (
                f"Weak encryption algorithm: {algorithm}. "
                f"Only allowed: {', '.join(self.allowed_algorithms)}"
            )
            logger.error(error_msg)
            raise SecurityError(error_msg)

        # Validate key rotation interval
        key_rotation_interval = self.config.get("key_rotation_interval", 0)
        if key_rotation_interval < self.min_key_rotation_interval:
            logger.warning(
                f"Key rotation interval {key_rotation_interval}s below recommended {self.min_key_rotation_interval}s"
            )
            self._schedule_key_rotation()

        logger.info("Encryption configuration validation passed")
        return True

    def encrypt_data(self, data: str) -> dict[str, Any]:
        """
        Encrypt data with validated algorithm

        Args:
            data: Data to encrypt

        Returns:
            Dict: Encrypted data with metadata

        Raises:
            SecurityError: If encryption fails
        """
        self.validate_config()

        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.backends import default_backend

            key = os.urandom(32)  # 256-bit key for AES-256
            iv = os.urandom(12)   # 96-bit IV for GCM mode

            encryptor = Cipher(
                algorithms.AES(key),
                modes.GCM(iv),
                backend=default_backend()
            ).encryptor()

            ciphertext = encryptor.update(data.encode()) + encryptor.finalize()

            result = {
                "ciphertext": ciphertext,
                "tag": encryptor.tag,
                "iv": iv,
                "algorithm": "AES-256-GCM",
                "timestamp": time.time()
            }

            logger.info("Data encrypted successfully")
            return result

        except Exception as ex:
            error_msg = f"Encryption failed: {str(ex)}"
            logger.error(error_msg)
            raise SecurityError(error_msg)

    def _schedule_key_rotation(self) -> None:
        """
        Schedule automatic key rotation
        """
        rotation_event = {
            "event": "key_rotation_scheduled",
            "timestamp": time.time(),
            "next_rotation": time.time() + self.min_key_rotation_interval
        }

        logger.info(f"Key rotation scheduled: {json.dumps(rotation_event)}")

        # In real implementation, this would integrate with a job scheduler


class ResourceValidator:
    """
    Validates system resource usage and thresholds

    Monitors CPU, memory, disk usage and triggers alerts or
    scaling when thresholds are exceeded.
    """
    
    def __init__(self, config: dict[str, Any]):
        """
        Initialize resource validator

        Args:
            config: Resource configuration dictionary
        """
        self.config = config
        self.cpu_threshold = config.get("cpu_threshold", 70)
        self.memory_threshold = config.get("memory_threshold", 80)
        self.disk_threshold = config.get("disk_threshold", 85)
        self.auto_scale = config.get("auto_scale", False)

        logger.info("Initialized ResourceValidator")

    def validate_resources(self) -> dict[str, Any]:
        """
        Validate current resource usage

        Returns:
            Dict: Resource usage status and violations
        """
        try:
            import psutil

            # Get current resource usage
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            resource_status = {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "disk_percent": (disk.used / disk.total) * 100,
                "timestamp": time.time(),
                "violations": []
            }

            # Check for threshold violations
            self._check_cpu_usage(cpu_percent, resource_status)
            self._check_memory_usage(memory.percent, resource_status)
            self._check_disk_usage(resource_status["disk_percent"], resource_status)

            if not resource_status["violations"]:
                logger.info("All resource thresholds within limits")

            return resource_status

        except ImportError:
            logger.error("psutil not available for resource monitoring")
            return {"error": "Resource monitoring unavailable", "violations": []}
        except Exception as ex:
            logger.error(f"Resource validation failed: {ex}")
            return {"error": str(ex), "violations": []}

    def _check_cpu_usage(self, cpu_percent: float, status: dict[str, Any]) -> None:
        """Check CPU usage against threshold"""
        if cpu_percent > self.cpu_threshold:
            violation = f"CPU usage {cpu_percent:.1f}% > {self.cpu_threshold}%"
            status["violations"].append(violation)
            logger.warning(violation)

            if self.auto_scale:
                self._trigger_scaling("cpu")

    def _check_memory_usage(self, memory_percent: float, status: dict[str, Any]) -> None:
        """Check Memory usage against threshold"""
        if memory_percent > self.memory_threshold:
            violation = f"Memory usage {memory_percent:.1f}% > {self.memory_threshold}%"
            status["violations"].append(violation)
            logger.warning(violation)

            if self.auto_scale:
                self._trigger_scaling("memory")

    def _check_disk_usage(self, disk_percent: float, status: dict[str, Any]) -> None:
        """Check Disk usage against threshold"""
        if disk_percent > self.disk_threshold:
            violation = f"Disk usage {disk_percent:.1f}% > {self.disk_threshold}%"
            status["violations"].append(violation)
            logger.warning(violation)

    def _trigger_scaling(self, resource_type: str) -> None:
        """
        Trigger auto-scaling for specific resource type

        Args:
            resource_type: Type of resource causing scaling (cpu, memory, disk)
        """
        scaling_event = {
            "event": "resource_scaling_triggered",
            "resource_type": resource_type,
            "timestamp": time.time(),
            "auto_scale_enabled": self.auto_scale
        }

        logger.info(f"Resource scaling triggered: {json.dumps(scaling_event)}")

        # Log scaling event
        os.makedirs("log/error_mitigation", exist_ok=True)
        with open("log/error_mitigation/resource_scaling.log", "a") as f:
            f.write(f"{datetime.now().isoformat()}: {json.dumps(scaling_event)}\n")


def _validate_arrow_structure(data: pa.Table | pa.RecordBatch) -> None:
    """Validate required fields in Arrow event data."""
    if "event" not in data.schema.names:
        return
    required_fields = ["entity_id", "event", "timestamp"]
    missing = [f for f in required_fields if f not in data.schema.names]
    if missing:
        logger.error(f"Missing required fields {missing} in Arrow event data")


def _check_legacy_structure(data: Any) -> None:
    """Check required fields in legacy dict event data."""
    if not isinstance(data, dict) or "event" not in data:
        return
    required_fields = ["entity_id", "event", "timestamp"]
    for field in required_fields:
        if field not in data:
            logger.error(f"Missing required field '{field}' in event data")


def _serialize_data_content(data: Any) -> str:
    """Serialize data for hashing in audit logs."""
    if hasattr(data, "to_pylist"):
        return json.dumps(data.to_pylist(), sort_keys=True)
    if hasattr(data, "ToString"):
        return str(data)
    try:
        return json.dumps(data, sort_keys=True)
    except TypeError:
        return str(data)


def _check_forbidden_terms_in_array(
    array: pa.Array,
    field_name: str,
    forbidden_terms: list[str],
) -> None:
    """Scan an Arrow string array for forbidden terms."""
    utf8_lower = getattr(pc, "utf8_lower")
    match_substring = getattr(pc, "match_substring")
    any_op = getattr(pc, "any")

    lower_data = utf8_lower(array)
    for term in forbidden_terms:
        matches = match_substring(lower_data, term)
        if any_op(matches).as_py():
            error_msg = (
                f"Forbidden crypto term '{term}' "
                f"found in column '{field_name}'"
            )
            logger.error(error_msg)
            raise ValidationError(error_msg)


def _write_audit_log(audit_entry: dict[str, Any]) -> None:
    """Persist an audit entry to disk."""
    try:
        os.makedirs("log/error_mitigation", exist_ok=True)
        with open(
            "log/error_mitigation/api_audit.log",
            "a", encoding="utf-8"
        ) as f:
            f.write(
                f"{datetime.now().isoformat()}: "
                f"{json.dumps(audit_entry)}\n"
            )
    except (IOError, OSError) as ex:
        logger.error(f"Failed to write audit log: {ex}")


class APIValidator:
    """
    Validates API endpoints and configurations

    Ensures API endpoints are properly configured and
    validates request/response formats according to HieraChain principles.
    """

    def __init__(self, config: dict[str, Any]):
        """
        Initialize API validator

        Args:
            config: API configuration dictionary
        """
        self.config = config
        self.endpoint_validation = config.get("endpoint_validation", "pre_call")
        self.command_audit = config.get("command_audit", True)

        # Forbidden cryptocurrency terms for validation
        self.forbidden_terms = [
            "transaction", "mining", "coin", "token", "wallet", "address",
            "sender", "receiver", "amount", "fee", "reward", "coinbase"
        ]

        logger.info("Initialized APIValidator")

    def _validate_arrow_recursive(self, data: pa.Array | pa.ChunkedArray, field_name: str) -> None:
        """
        Recursively validate Arrow arrays for forbidden terms.
        Handles nested types: Map, List, Struct.
        """
        try:
            if isinstance(data, pa.ChunkedArray):
                self._handle_arrow_chunked(data, field_name)
            else:
                self._dispatch_type_validation(data, field_name, data.type)
        except ValidationError:
            raise
        except (AttributeError, TypeError, pa.ArrowInvalid) as e:
            logger.warning(f"Recursive validation error on {field_name}: {e}")

    def _dispatch_type_validation(self, data: Any, field_name: str, type_: pa.DataType) -> None:
        """Dispatch validation based on Arrow DataType."""
        handlers = [
            (_is_string_type, lambda d, f, _t: self._check_string_array(d, f)),
            (pa.types.is_map, lambda d, f, t: self._handle_arrow_map(d, f, t)),
            (_is_list_type, lambda d, f, _t: self._handle_arrow_list(d, f)),
            (pa.types.is_struct, lambda d, f, t: self._handle_arrow_struct(d, f, t)),
        ]
        for predicate, handler in handlers:
            if predicate(type_):
                handler(data, field_name, type_)
                return

    def _handle_arrow_chunked(self, data: pa.ChunkedArray, field_name: str) -> None:
        """Handle ChunkedArray validation"""
        for chunk in data.chunks:
            self._validate_arrow_recursive(chunk, field_name)

    def _handle_arrow_map(self, data: pa.Array, field_name: str, type_: pa.DataType) -> None:
        """Handle Arrow Map validation"""
        if hasattr(data, "keys") and hasattr(data, "items"):
            self._validate_map_keys_values(data, field_name)
        else:
            self._fallback_map_validation(data, field_name, type_)

    def _validate_map_keys_values(self, data: pa.Array, field_name: str) -> None:
        """Validate keys and values of a Map array."""
        keys = getattr(data, "keys")
        items = getattr(data, "items")
        self._validate_arrow_recursive(keys, f"{field_name}.keys")
        self._validate_arrow_recursive(items, f"{field_name}.values")

    def _fallback_map_validation(self, data: pa.Array, field_name: str, type_: pa.DataType) -> None:
        """Fallback validation for map types without keys/values attributes."""
        if not isinstance(type_, pa.MapType):
            return

        struct_fields = [
            pa.field("key", type_.key_type, nullable=False),
            pa.field("value", type_.item_type, nullable=True)
        ]
        struct_type = pa.struct(struct_fields)
        list_type = pa.list_(struct_type)
        as_list = data.cast(list_type)

        if hasattr(as_list, "flatten"):
            # Use getattr to avoid IDE warnings on generic Array
            flattened = getattr(as_list, "flatten")()
            self._validate_arrow_recursive(flattened, f"{field_name}.entry")

    def _handle_arrow_list(self, data: pa.Array, field_name: str) -> None:
        """Handle Arrow List validation"""
        if hasattr(data, "flatten"):
            flattened = getattr(data, "flatten")()
            self._validate_arrow_recursive(flattened, f"{field_name}.nested")

    def _handle_arrow_struct(self, data: pa.StructArray, field_name: str, type_: pa.DataType) -> None:
        """Handle Arrow Struct validation"""
        for i in range(type_.num_fields):
            field = type_.field(i)
            child = data.field(i)
            self._validate_arrow_recursive(child, f"{field_name}.{field.name}")

    def _check_string_array(self, array: pa.Array, field_name: str) -> None:
        """Helper to check a specific string array using compute."""
        _check_forbidden_terms_in_array(array, field_name, self.forbidden_terms)

    def validate_endpoint_data(self, data: Any) -> bool:
        """
        Validate API endpoint data for compliance

        Args:
            data: Data to validate (Dict or PyArrow object)

        Returns:
            bool: True if data is valid

        Raises:
            ValidationError: If data contains forbidden elements
        """
        try:
            self._dispatch_data_validation(data)
        except ValidationError:
            raise
        except (AttributeError, TypeError, pa.ArrowInvalid) as e:
            logger.warning(f"Validation complexity check failed: {e}")

        logger.info("API endpoint data validation passed")
        return True

    def _dispatch_data_validation(self, data: Any) -> None:
        """Route data to Arrow or legacy validation."""
        if hasattr(data, "schema") and isinstance(data, (pa.Table, pa.RecordBatch)):
            self._validate_arrow_object(data)
        else:
            self._validate_legacy_object(data)

    def _validate_arrow_object(self, data: pa.Table | pa.RecordBatch) -> None:
        """Validate PyArrow Table or RecordBatch"""
        self._validate_arrow_schema(data)

        for col_name in data.column_names:
            self._validate_arrow_recursive(data[col_name], col_name)

        _validate_arrow_structure(data)

    def _validate_arrow_schema(self, data: pa.Table | pa.RecordBatch) -> None:
        """Check Arrow schema names for forbidden terms."""
        for name in data.schema.names:
            if any(term in name.lower() for term in self.forbidden_terms):
                error_msg = f"Forbidden cryptocurrency term '{name}' found in Arrow schema"
                logger.error(error_msg)
                raise ValidationError(error_msg)

    def _validate_legacy_object(self, data: Any) -> None:
        """Validate Dict/JSON objects"""
        data_str = json.dumps(data).lower()
        for term in self.forbidden_terms:
            if term in data_str:
                error_msg = f"Forbidden cryptocurrency term '{term}' found in API data"
                logger.error(error_msg)
                raise ValidationError(error_msg)

        _check_legacy_structure(data)

    def audit_api_call(self, endpoint: str, data: Any, user_id: str | None = None) -> None:
        """
        Audit API call for compliance and logging

        Args:
            endpoint: API endpoint being called
            data: Request data
            user_id: Optional user identifier
        """
        if not self.command_audit:
            return

        data_content = _serialize_data_content(data)
        audit_entry = {
            "event": "api_call_audit",
            "endpoint": endpoint,
            "user_id": user_id,
            "timestamp": time.time(),
            "data_hash": hashlib.sha256(data_content.encode()).hexdigest()
        }
        logger.info(f"API call audited: {endpoint}")
        _write_audit_log(audit_entry)


def validate_certificate(certificate):
    """
    Validate certificate expiration

    Args:
        certificate: Certificate to validate

    Raises:
        SecurityError: If certificate is expired
    """
    if certificate.is_expired():
        raise SecurityError('Certificate validation failed: Certificate has expired')


# Factory function for creating validators
def create_validator(validator_type: str, config: dict[str, Any]):
    """
    Factory function to create appropriate validator
    
    Args:
        validator_type: Type of validator to create
        config: Configuration for the validator
        
    Returns:
        Validator instance
        
    Raises:
        ValueError: If validator type is unknown
    """
    validators = {
        "consensus": ConsensusValidator,
        "encryption": EncryptionValidator,
        "resource": ResourceValidator,
        "api": APIValidator
    }

    if validator_type not in validators:
        raise ValueError(f"Unknown validator type: {validator_type}")

    return validators[validator_type](config)
