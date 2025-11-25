"""
Error Mitigation Validator Module

This module provides comprehensive validation mechanisms. It includes
validators for consensus, encryption, resources, and other critical system
components.
"""

import time
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import hashlib
import os

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


class ConsensusValidator:
    """
    Automated validator for BFT consensus requirements
    
    Validates that the consensus mechanism meets Byzantine Fault Tolerance
    requirements, including proper node count (n >= 3f + 1) and node health.
    """
    
    def __init__(self, consensus_config: Dict[str, Any]):
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
    
    def validate_node_count(self, current_nodes: List[Any]) -> bool:
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
                f"Insufficient nodes for BFT consensus: {actual_nodes} < {required_nodes}. "
                f"For f={self.f} faulty nodes tolerance, need at least {required_nodes} nodes. "
                f"Auto-scaling initiated."
            )
            logger.error(error_msg)
            raise ValidationError("insufficient_nodes")
        
        logger.info(f"Node count validation passed: {actual_nodes} >= {required_nodes}")
        return True
    
    def monitor_and_scale(self, current_nodes: List[Any]) -> List[Any]:
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
            logger.warning(f"Health ratio {health_ratio:.2f} below threshold {self.auto_scale_threshold}")
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
                logger.warning(f"Node {getattr(node, 'node_id', 'unknown')} missing health attributes")
                return False
            
            # Check status and heartbeat timing
            is_active = node.health_status == "active"
            heartbeat_fresh = (time.time() - node.last_heartbeat) < self.health_check_interval
            
            return is_active and heartbeat_fresh
        except Exception as ex:
            logger.error(f"Error checking node health: {ex}")
            return False
    
    def _trigger_scaling(self, healthy_nodes: List[Any]) -> None:
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
        
        self._log_scaling_event(scaling_event)
    
    @staticmethod
    def _log_scaling_event(event: Dict[str, Any]) -> None:
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
        except Exception as ex:
            logger.error(f"Failed to log scaling event: {ex}")


class EncryptionValidator:
    """
    Validates encryption configurations and algorithms
    
    Ensures only approved encryption algorithms are used and
    validates key rotation policies according to dev5 requirements.
    """
    
    def __init__(self, config: Dict[str, Any]):
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
            logger.warning(f"Key rotation interval {key_rotation_interval}s below recommended {self.min_key_rotation_interval}s")
            self._schedule_key_rotation()
        
        logger.info("Encryption configuration validation passed")
        return True
    
    def encrypt_data(self, data: str) -> Dict[str, Any]:
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
    
    def __init__(self, config: Dict[str, Any]):
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
    
    def validate_resources(self) -> Dict[str, Any]:
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
            if cpu_percent > self.cpu_threshold:
                violation = f"CPU usage {cpu_percent:.1f}% > {self.cpu_threshold}%"
                resource_status["violations"].append(violation)
                logger.warning(violation)
                
                if self.auto_scale:
                    self._trigger_scaling("cpu")
            
            if memory.percent > self.memory_threshold:
                violation = f"Memory usage {memory.percent:.1f}% > {self.memory_threshold}%"
                resource_status["violations"].append(violation)
                logger.warning(violation)
                
                if self.auto_scale:
                    self._trigger_scaling("memory")
            
            if resource_status["disk_percent"] > self.disk_threshold:
                violation = f"Disk usage {resource_status['disk_percent']:.1f}% > {self.disk_threshold}%"
                resource_status["violations"].append(violation)
                logger.warning(violation)
            
            if not resource_status["violations"]:
                logger.info("All resource thresholds within limits")
            
            return resource_status
            
        except ImportError:
            logger.error("psutil not available for resource monitoring")
            return {"error": "Resource monitoring unavailable", "violations": []}
        except Exception as ex:
            logger.error(f"Resource validation failed: {ex}")
            return {"error": str(ex), "violations": []}
    
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


class APIValidator:
    """
    Validates API endpoints and configurations
    
    Ensures API endpoints are properly configured and
    validates request/response formats according to HieraChain principles.
    """
    
    def __init__(self, config: Dict[str, Any]):
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
    
    def validate_endpoint_data(self, data: Dict[str, Any]) -> bool:
        """
        Validate API endpoint data for compliance
        
        Args:
            data: Data to validate
            
        Returns:
            bool: True if data is valid
            
        Raises:
            ValidationError: If data contains forbidden elements
        """
        # Check for cryptocurrency terms
        data_str = json.dumps(data).lower()
        for term in self.forbidden_terms:
            if term in data_str:
                error_msg = f"Forbidden cryptocurrency term '{term}' found in API data"
                logger.error(error_msg)
                raise ValidationError(error_msg)
        
        # Validate required event structure
        if "event" in data:
            required_fields = ["entity_id", "event", "timestamp"]
            for field in required_fields:
                if field not in data:
                    error_msg = f"Missing required field '{field}' in event data"
                    logger.error(error_msg)
                    raise ValidationError(error_msg)
        
        logger.info("API endpoint data validation passed")
        return True
    
    def audit_api_call(self, endpoint: str, data: Dict[str, Any], user_id: Optional[str] = None) -> None:
        """
        Audit API call for compliance and logging
        
        Args:
            endpoint: API endpoint being called
            data: Request data
            user_id: Optional user identifier
        """
        if not self.command_audit:
            return
        
        audit_entry = {
            "event": "api_call_audit",
            "endpoint": endpoint,
            "user_id": user_id,
            "timestamp": time.time(),
            "data_hash": hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
        }
        
        logger.info(f"API call audited: {endpoint}")
        
        try:
            os.makedirs("log/error_mitigation", exist_ok=True)
            with open("log/error_mitigation/api_audit.log", "a") as f:
                f.write(f"{datetime.now().isoformat()}: {json.dumps(audit_entry)}\n")
        except Exception as ex:
            logger.error(f"Failed to write audit log: {ex}")

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
def create_validator(validator_type: str, config: Dict[str, Any]):
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
