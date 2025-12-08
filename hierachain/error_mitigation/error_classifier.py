"""
Error Mitigation Error Classifier Module

This module provides error classification and risk prioritization. It categorizes
errors by priority level, impact, and recovery strategy to enable targeted
mitigation approaches.
"""

import os
import time
import json
import logging
from typing import Dict, Any, List
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PriorityLevel(Enum):
    """Error priority levels based on risk assessment"""
    CRITICAL = 1    # System-breaking errors requiring immediate action
    HIGH = 2        # Significant impact errors requiring prompt action
    MEDIUM = 3      # Moderate impact errors requiring scheduled action
    LOW = 4         # Minor impact errors requiring monitoring


class ErrorCategory(Enum):
    """Error categories for HieraChain framework"""
    CONSENSUS = "consensus"
    SECURITY = "security"
    PERFORMANCE = "performance"
    STORAGE = "storage"
    NETWORK = "network"
    API = "api"
    OPERATIONAL = "operational"


class ImpactLevel(Enum):
    """Impact levels for risk assessment"""
    CATASTROPHIC = 5    # Complete system failure
    MAJOR = 4          # Significant functionality loss
    MODERATE = 3       # Partial functionality loss
    MINOR = 2          # Degraded performance
    NEGLIGIBLE = 1     # Minimal impact


class LikelihoodLevel(Enum):
    """Likelihood levels for risk assessment"""
    VERY_HIGH = 5      # Almost certain to occur
    HIGH = 4           # Likely to occur
    MEDIUM = 3         # Possible to occur
    LOW = 2            # Unlikely to occur
    VERY_LOW = 1       # Very unlikely to occur


@dataclass
class ErrorInfo:
    """Information about a classified error"""
    error_id: str
    error_type: str
    category: ErrorCategory
    priority: PriorityLevel
    impact: ImpactLevel
    likelihood: LikelihoodLevel
    description: str
    mitigation_strategy: str
    timestamp: float
    metadata: Dict[str, Any]


class RiskPriorityMatrix:
    """
    Risk priority matrix for assessing error severity
    
    Uses impact vs likelihood matrix to determine priority levels
    following dev5 risk assessment methodology.
    """
    
    def __init__(self):
        """Initialize the risk priority matrix"""
        # Priority matrix: [impact][likelihood] -> priority
        self.matrix = {
            ImpactLevel.CATASTROPHIC: {
                LikelihoodLevel.VERY_HIGH: PriorityLevel.CRITICAL,
                LikelihoodLevel.HIGH: PriorityLevel.CRITICAL,
                LikelihoodLevel.MEDIUM: PriorityLevel.CRITICAL,
                LikelihoodLevel.LOW: PriorityLevel.HIGH,
                LikelihoodLevel.VERY_LOW: PriorityLevel.HIGH
            },
            ImpactLevel.MAJOR: {
                LikelihoodLevel.VERY_HIGH: PriorityLevel.CRITICAL,
                LikelihoodLevel.HIGH: PriorityLevel.CRITICAL,
                LikelihoodLevel.MEDIUM: PriorityLevel.HIGH,
                LikelihoodLevel.LOW: PriorityLevel.HIGH,
                LikelihoodLevel.VERY_LOW: PriorityLevel.MEDIUM
            },
            ImpactLevel.MODERATE: {
                LikelihoodLevel.VERY_HIGH: PriorityLevel.HIGH,
                LikelihoodLevel.HIGH: PriorityLevel.HIGH,
                LikelihoodLevel.MEDIUM: PriorityLevel.MEDIUM,
                LikelihoodLevel.LOW: PriorityLevel.MEDIUM,
                LikelihoodLevel.VERY_LOW: PriorityLevel.LOW
            },
            ImpactLevel.MINOR: {
                LikelihoodLevel.VERY_HIGH: PriorityLevel.MEDIUM,
                LikelihoodLevel.HIGH: PriorityLevel.MEDIUM,
                LikelihoodLevel.MEDIUM: PriorityLevel.LOW,
                LikelihoodLevel.LOW: PriorityLevel.LOW,
                LikelihoodLevel.VERY_LOW: PriorityLevel.LOW
            },
            ImpactLevel.NEGLIGIBLE: {
                LikelihoodLevel.VERY_HIGH: PriorityLevel.LOW,
                LikelihoodLevel.HIGH: PriorityLevel.LOW,
                LikelihoodLevel.MEDIUM: PriorityLevel.LOW,
                LikelihoodLevel.LOW: PriorityLevel.LOW,
                LikelihoodLevel.VERY_LOW: PriorityLevel.LOW
            }
        }
        
        logger.info("Initialized RiskPriorityMatrix")
    
    def calculate_priority(self, impact: ImpactLevel, likelihood: LikelihoodLevel) -> PriorityLevel:
        """
        Calculate priority level based on impact and likelihood
        
        Args:
            impact: Impact level of the error
            likelihood: Likelihood level of the error
            
        Returns:
            PriorityLevel: Calculated priority level
        """
        priority = self.matrix[impact][likelihood]
        logger.debug(f"Priority calculated: {impact.name} + {likelihood.name} = {priority.name}")
        return priority
    
    @staticmethod
    def get_priority_score(priority: PriorityLevel) -> int:
        """
        Get numeric score for priority level
        
        Args:
            priority: Priority level
            
        Returns:
            int: Numeric score (1-4, lower is higher priority)
        """
        return priority.value


class ErrorClassifier:
    """
    Main error classifier for HieraChain framework
    
    Classifies errors by type, category, and priority using the risk
    priority matrix and predefined error patterns.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize error classifier
        
        Args:
            config: Configuration dictionary with classification parameters
        """
        self.config = config
        self.risk_matrix = RiskPriorityMatrix()
        self.error_patterns = self._load_error_patterns()
        self.classification_history = []
        self.mitigation_strategies = self._load_mitigation_strategies()
        
        logger.info("Initialized ErrorClassifier")
    
    def classify_error(self, error_data: Dict[str, Any]) -> ErrorInfo:
        """
        Classify an error and determine its priority and mitigation strategy
        
        Args:
            error_data: Dictionary containing error information
            
        Returns:
            ErrorInfo: Classified error information
        """
        error_type = error_data.get("error_type", "unknown")
        error_message = error_data.get("message", "")
        
        # Determine category based on error type and message
        category = self._determine_category(error_type, error_message)
        
        # Assess impact and likelihood
        impact = self._assess_impact(error_data, category)
        likelihood = self._assess_likelihood(error_data, category)
        
        # Calculate priority using risk matrix
        priority = self.risk_matrix.calculate_priority(impact, likelihood)
        
        # Determine mitigation strategy
        mitigation_strategy = self._determine_mitigation_strategy(category, priority)
        
        # Create error ID
        error_id = self._generate_error_id(error_data)
        
        # Create ErrorInfo object
        error_info = ErrorInfo(
            error_id=error_id,
            error_type=error_type,
            category=category,
            priority=priority,
            impact=impact,
            likelihood=likelihood,
            description=error_message,
            mitigation_strategy=mitigation_strategy,
            timestamp=time.time(),
            metadata=self._sanitize_metadata(error_data.get("metadata", {}))
        )
        
        # Log classification
        self._log_classification(error_info)
        
        # Add to history
        self.classification_history.append(error_info)
        
        logger.info(f"Error classified: {error_id} -> {category.value} ({priority.name})")
        return error_info
    
    @staticmethod
    def _sanitize_metadata(data: Any) -> Any:
        """Recursively sanitize metadata for serialization, handling Arrow objects"""
        if hasattr(data, "to_pylist"):
            return data.to_pylist()
        if isinstance(data, dict):
            return {k: ErrorClassifier._sanitize_metadata(v) for k, v in data.items()}
        if isinstance(data, list):
            return [ErrorClassifier._sanitize_metadata(v) for v in data]
        return data

    def get_priority_errors(self, priority: PriorityLevel) -> List[ErrorInfo]:
        """
        Get all errors of a specific priority level
        
        Args:
            priority: Priority level to filter by
            
        Returns:
            List[ErrorInfo]: List of errors with specified priority
        """
        return [error for error in self.classification_history if error.priority == priority]
    
    def get_category_errors(self, category: ErrorCategory) -> List[ErrorInfo]:
        """
        Get all errors of a specific category
        
        Args:
            category: Error category to filter by
            
        Returns:
            List[ErrorInfo]: List of errors in specified category
        """
        return [error for error in self.classification_history if error.category == category]
    
    def get_classification_summary(self) -> Dict[str, Any]:
        """
        Get summary of error classifications
        
        Returns:
            Dict: Summary statistics of classified errors
        """
        total_errors = len(self.classification_history)
        
        if total_errors == 0:
            return {"total_errors": 0, "categories": {}, "priorities": {}}
        
        # Count by category
        category_counts = {}
        for category in ErrorCategory:
            category_counts[category.value] = len(self.get_category_errors(category))
        
        # Count by priority
        priority_counts = {}
        for priority in PriorityLevel:
            priority_counts[priority.name] = len(self.get_priority_errors(priority))
        
        summary = {
            "total_errors": total_errors,
            "categories": category_counts,
            "priorities": priority_counts,
            "timestamp": time.time()
        }
        
        return summary
    
    def _determine_category(self, error_type: str, error_message: str) -> ErrorCategory:
        """
        Determine error category based on type and message
        
        Args:
            error_type: Type of error
            error_message: Error message content
            
        Returns:
            ErrorCategory: Determined category
        """
        error_text = f"{error_type} {error_message}".lower()
        
        # Check against known patterns
        for pattern, category in self.error_patterns.items():
            if pattern.lower() in error_text:
                return ErrorCategory(category)
        
        # Default categorization based on keywords
        if any(keyword in error_text for keyword in ["consensus", "bft", "leader", "view"]):
            return ErrorCategory.CONSENSUS
        elif any(keyword in error_text for keyword in ["security", "encryption", "key", "certificate"]):
            return ErrorCategory.SECURITY
        elif any(keyword in error_text for keyword in ["performance", "resource", "cpu", "memory"]):
            return ErrorCategory.PERFORMANCE
        elif any(keyword in error_text for keyword in ["storage", "backup", "database", "persistence"]):
            return ErrorCategory.STORAGE
        elif any(keyword in error_text for keyword in ["network", "timeout", "connection"]):
            return ErrorCategory.NETWORK
        elif any(keyword in error_text for keyword in ["api", "endpoint", "request", "response"]):
            return ErrorCategory.API
        else:
            return ErrorCategory.OPERATIONAL
    
    @staticmethod
    def _assess_impact(error_data: Dict[str, Any], category: ErrorCategory) -> ImpactLevel:
        """
        Assess impact level of an error
        
        Args:
            error_data: Error data dictionary
            category: Error category
            
        Returns:
            ImpactLevel: Assessed impact level
        """
        error_type = error_data.get("error_type", "").lower()
        
        # High impact patterns for HieraChain
        if category == ErrorCategory.CONSENSUS:
            if "insufficient nodes" in error_type or "bft" in error_type:
                return ImpactLevel.CATASTROPHIC
            elif "leader failure" in error_type or "view change" in error_type:
                return ImpactLevel.MAJOR
            else:
                return ImpactLevel.MODERATE
        
        elif category == ErrorCategory.SECURITY:
            if "encryption" in error_type or "key" in error_type:
                return ImpactLevel.MAJOR
            elif "certificate" in error_type or "authentication" in error_type:
                return ImpactLevel.MODERATE
            else:
                return ImpactLevel.MINOR
        
        elif category == ErrorCategory.PERFORMANCE:
            if "resource" in error_type and "critical" in error_type:
                return ImpactLevel.MAJOR
            elif "threshold" in error_type:
                return ImpactLevel.MODERATE
            else:
                return ImpactLevel.MINOR
        
        elif category == ErrorCategory.STORAGE:
            if "backup" in error_type and "failed" in error_type:
                return ImpactLevel.MAJOR
            elif "corruption" in error_type:
                return ImpactLevel.MAJOR
            else:
                return ImpactLevel.MODERATE
        
        elif category == ErrorCategory.NETWORK:
            if "partition" in error_type or "connectivity" in error_type:
                return ImpactLevel.MAJOR
            elif "timeout" in error_type:
                return ImpactLevel.MODERATE
            else:
                return ImpactLevel.MINOR
        
        else:  # API, OPERATIONAL
            return ImpactLevel.MINOR
    
    @staticmethod
    def _assess_likelihood(_error_data: Dict[str, Any], category: ErrorCategory) -> LikelihoodLevel:
        """
        Assess likelihood level of an error
        
        Args:
            _error_data: Error data dictionary
            category: Error category
            
        Returns:
            LikelihoodLevel: Assessed likelihood level
        """
        # Base likelihood assessment on category and historical data
        if category == ErrorCategory.CONSENSUS:
            return LikelihoodLevel.MEDIUM  # Consensus issues are possible in distributed systems
        elif category == ErrorCategory.SECURITY:
            return LikelihoodLevel.LOW     # Security issues should be rare with proper implementation
        elif category == ErrorCategory.PERFORMANCE:
            return LikelihoodLevel.HIGH    # Performance issues are common under load
        elif category == ErrorCategory.STORAGE:
            return LikelihoodLevel.MEDIUM  # Storage issues are moderately common
        elif category == ErrorCategory.NETWORK:
            return LikelihoodLevel.HIGH    # Network issues are common in distributed systems
        elif category == ErrorCategory.API:
            return LikelihoodLevel.LOW     # API issues should be caught in testing
        else:  # OPERATIONAL
            return LikelihoodLevel.MEDIUM
    
    def _determine_mitigation_strategy(self, category: ErrorCategory, priority: PriorityLevel) -> str:
        """
        Determine appropriate mitigation strategy
        
        Args:
            category: Error category
            priority: Priority level
            
        Returns:
            str: Mitigation strategy identifier
        """
        strategy_key = f"{category.value}_{priority.name.lower()}"
        return self.mitigation_strategies.get(strategy_key, "monitor_and_log")
    
    @staticmethod
    def _generate_error_id(error_data: Dict[str, Any]) -> str:
        """
        Generate unique error ID
        
        Args:
            error_data: Error data dictionary
            
        Returns:
            str: Unique error ID
        """
        content = f"{error_data.get('error_type', '')}{error_data.get('message', '')}{time.time()}"
        hash_value = hashlib.md5(content.encode()).hexdigest()[:12]
        return f"ERR-{hash_value.upper()}"
    
    @staticmethod
    def _log_classification(error_info: ErrorInfo) -> None:
        """
        Log error classification for audit trail
        
        Args:
            error_info: Classified error information
        """
        log_entry = {
            "event": "error_classified",
            "error_id": error_info.error_id,
            "category": error_info.category.value,
            "priority": error_info.priority.name,
            "impact": error_info.impact.name,
            "likelihood": error_info.likelihood.name,
            "mitigation_strategy": error_info.mitigation_strategy,
            "timestamp": error_info.timestamp
        }
        
        try:
            os.makedirs("log/error_mitigation", exist_ok=True)
            with open("log/error_mitigation/error_classifications.log", "a") as f:
                f.write(f"{datetime.now().isoformat()}: {json.dumps(log_entry)}\n")
        except Exception as e:
            logger.error(f"Failed to log error classification: {e}")
    
    @staticmethod
    def _load_error_patterns() -> Dict[str, str]:
        """
        Load error patterns for classification
        
        Returns:
            Dict: Error patterns mapping to categories
        """
        # Define error patterns specific to HieraChain
        patterns = {
            "insufficient nodes": "consensus",
            "bft consensus": "consensus",
            "leader failure": "consensus",
            "view change": "consensus",
            "message ordering": "consensus",
            "signature verification": "security",
            "encryption": "security",
            "key rotation": "security",
            "certificate": "security",
            "cpu threshold": "performance",
            "memory threshold": "performance",
            "resource usage": "performance",
            "backup failed": "storage",
            "data corruption": "storage",
            "world state": "storage",
            "network partition": "network",
            "timeout": "network",
            "connectivity": "network",
            "api endpoint": "api",
            "request validation": "api",
            "response error": "api",
            "multi org sync": "operational",
            "entity tracing": "operational",
            "block creation": "operational"
        }
        return patterns
    
    @staticmethod
    def _load_mitigation_strategies() -> Dict[str, str]:
        """
        Load mitigation strategies for different error types
        
        Returns:
            Dict: Mitigation strategies mapping
        """
        strategies = {
            # Consensus errors
            "consensus_critical": "immediate_scaling_and_recovery",
            "consensus_high": "auto_scale_nodes",
            "consensus_medium": "monitor_and_view_change",
            "consensus_low": "log_and_monitor",
            
            # Security errors
            "security_critical": "immediate_lockdown_and_investigation",
            "security_high": "rotate_keys_and_audit",
            "security_medium": "schedule_security_review",
            "security_low": "monitor_and_log",
            
            # Performance errors
            "performance_critical": "immediate_resource_scaling",
            "performance_high": "auto_scale_resources",
            "performance_medium": "optimize_and_monitor",
            "performance_low": "monitor_and_log",
            
            # Storage errors
            "storage_critical": "immediate_backup_recovery",
            "storage_high": "verify_and_restore_backup",
            "storage_medium": "integrity_check_and_repair",
            "storage_low": "monitor_and_log",
            
            # Network errors
            "network_critical": "activate_redundant_paths",
            "network_high": "network_recovery_procedures",
            "network_medium": "adjust_timeouts_and_monitor",
            "network_low": "monitor_and_log",
            
            # API errors
            "api_critical": "api_circuit_breaker",
            "api_high": "api_validation_enhancement",
            "api_medium": "api_monitoring_increase",
            "api_low": "monitor_and_log",
            
            # Operational errors
            "operational_critical": "immediate_manual_intervention",
            "operational_high": "automated_recovery_procedures",
            "operational_medium": "schedule_maintenance",
            "operational_low": "monitor_and_log"
        }
        return strategies


# Utility functions for error classification
def classify_error_quick(error_type: str, message: str, config: Dict[str, Any] = None) -> ErrorInfo:
    """
    Quick error classification utility function
    
    Args:
        error_type: Type of error
        message: Error message
        config: Optional configuration
        
    Returns:
        ErrorInfo: Classified error information
    """
    if config is None:
        config = {}
    
    classifier = ErrorClassifier(config)
    error_data = {
        "error_type": error_type,
        "message": message,
        "timestamp": time.time()
    }
    
    return classifier.classify_error(error_data)


def get_priority_threshold(priority: PriorityLevel) -> Dict[str, Any]:
    """
    Get thresholds and timeframes for different priority levels
    
    Args:
        priority: Priority level
        
    Returns:
        Dict: Priority thresholds and requirements
    """
    thresholds = {
        PriorityLevel.CRITICAL: {
            "response_time_minutes": 5,
            "escalation_time_minutes": 15,
            "auto_recovery": True,
            "alert_level": "immediate"
        },
        PriorityLevel.HIGH: {
            "response_time_minutes": 30,
            "escalation_time_minutes": 120,
            "auto_recovery": True,
            "alert_level": "urgent"
        },
        PriorityLevel.MEDIUM: {
            "response_time_minutes": 240,
            "escalation_time_minutes": 1440,
            "auto_recovery": False,
            "alert_level": "standard"
        },
        PriorityLevel.LOW: {
            "response_time_minutes": 1440,
            "escalation_time_minutes": 10080,
            "auto_recovery": False,
            "alert_level": "low"
        }
    }
    
    return thresholds.get(priority, thresholds[PriorityLevel.LOW])
