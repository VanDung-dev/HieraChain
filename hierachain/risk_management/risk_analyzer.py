"""
Risk Analysis Tools for HieraChain Framework

This module provides comprehensive risk analysis capabilities for identifying
and assessing technical and operational risks in the HieraChain system.
Focuses on consensus, security, performance, and storage risks.
"""

import time
import logging
import os
from typing import Any, Optional
from dataclasses import dataclass
from enum import Enum


class RiskSeverity(Enum):
    """Risk severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskCategory(Enum):
    """Risk categories based on dev4 guidelines"""
    CONSENSUS = "consensus"
    SECURITY = "security"
    PERFORMANCE = "performance"
    STORAGE = "storage"
    OPERATIONAL = "operational"


@dataclass
class RiskAssessment:
    """Risk assessment result"""
    risk_id: str
    category: RiskCategory
    severity: RiskSeverity
    description: str
    impact: str
    likelihood: float  # 0.0 to 1.0
    mitigation_recommendations: list[str]
    detected_at: float
    affected_components: list[str]


class RiskAnalyzer:
    """
    Comprehensive risk analysis tool for HieraChain systems.
    
    Analyzes technical and operational risks across consensus, security,
    performance, storage, and operational domains.
    """
    
    def __init__(self, config: Optional[dict[str, Any]] = None):
        """
        Initialize risk analyzer with configuration.
        
        Args:
            config: Risk analysis configuration parameters
        """
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        # Ensure log directory exists
        os.makedirs('log/risk_management', exist_ok=True)
        handler = logging.FileHandler('log/risk_management/risk_analyzer.log')
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.risk_history: list[RiskAssessment] = []
        self.active_risks: dict[str, RiskAssessment] = {}
        
        # Risk thresholds from configuration
        self.thresholds = self.config.get('thresholds', {
            'consensus': {
                'min_nodes': 4,  # For BFT consensus with f=1
                'max_leader_timeout': 30,
                'max_message_delay': 5.0
            },
            'security': {
                'certificate_expiry_warning': 30,  # days
                'max_failed_authentications': 5,
                'encryption_strength_min': 256
            },
            'performance': {
                'max_cpu_usage': 80,  # percentage
                'max_memory_usage': 90,  # percentage
                'max_event_pool_size': 10000,
                'max_block_creation_time': 10.0  # seconds
            },
            'storage': {
                'max_world_state_size': 1000000,  # entries
                'backup_interval_max': 86400,  # seconds
                'query_timeout_max': 30.0  # seconds
            }
        })
    
    def analyze_consensus_risks(self, consensus_data: dict[str, Any]) -> list[RiskAssessment]:
        """
        Analyze consensus mechanism risks.
        
        Args:
            consensus_data: Current consensus system data
            
        Returns:
            List of identified consensus risks
        """
        risks = []
        
        # Check BFT node count requirement (n >= 3f + 1)
        node_count = consensus_data.get('node_count', 0)
        fault_tolerance = consensus_data.get('fault_tolerance', 1)
        min_required = 3 * fault_tolerance + 1
        
        if node_count < min_required:
            risks.append(RiskAssessment(
                risk_id="CONSENSUS_001",
                category=RiskCategory.CONSENSUS,
                severity=RiskSeverity.CRITICAL,
                description=f"Insufficient nodes for BFT consensus: {node_count} < {min_required}",
                impact="Consensus failure, potential network partition",
                likelihood=0.9,
                mitigation_recommendations=[
                    f"Add {min_required - node_count} more validator nodes",
                    "Implement node health monitoring",
                    "Set up automatic node replacement procedures"
                ],
                detected_at=time.time(),
                affected_components=["consensus", "network"]
            ))
        
        # Check leader selection and timeout risks
        leader_timeout = consensus_data.get('leader_timeout', 0)
        if leader_timeout > self.thresholds['consensus']['max_leader_timeout']:
            risks.append(RiskAssessment(
                risk_id="CONSENSUS_002",
                category=RiskCategory.CONSENSUS,
                severity=RiskSeverity.MEDIUM,
                description=f"Leader timeout too high: {leader_timeout}s",
                impact="Slow consensus, potential performance degradation",
                likelihood=0.6,
                mitigation_recommendations=[
                    "Reduce leader timeout to recommended value",
                    "Implement faster leader election mechanism",
                    "Monitor network latency between nodes"
                ],
                detected_at=time.time(),
                affected_components=["consensus"]
            ))
        
        # Check message verification risks
        failed_verifications = consensus_data.get('failed_message_verifications', 0)
        total_messages = consensus_data.get('total_messages', 1)
        failure_rate = failed_verifications / total_messages
        
        if failure_rate > 0.05:  # 5% failure rate threshold
            risks.append(RiskAssessment(
                risk_id="CONSENSUS_003",
                category=RiskCategory.CONSENSUS,
                severity=RiskSeverity.HIGH,
                description=f"High message verification failure rate: {failure_rate:.2%}",
                impact="Potential security compromise, consensus instability",
                likelihood=0.8,
                mitigation_recommendations=[
                    "Investigate message signature issues",
                    "Check for malicious nodes",
                    "Strengthen message authentication"
                ],
                detected_at=time.time(),
                affected_components=["consensus", "security"]
            ))
        
        return risks
    
    def analyze_security_risks(self, security_data: dict[str, Any]) -> list[RiskAssessment]:
        """
        Analyze security-related risks.
        
        Args:
            security_data: Current security system data
            
        Returns:
            List of identified security risks
        """
        risks = []
        
        # Certificate expiry risks
        certificates = security_data.get('certificates', [])
        current_time = time.time()
        warning_threshold = self.thresholds['security']['certificate_expiry_warning'] * 24 * 3600
        
        for cert in certificates:
            expiry_time = cert.get('expires_at', 0)
            if expiry_time - current_time < warning_threshold:
                severity = RiskSeverity.CRITICAL if expiry_time < current_time else RiskSeverity.HIGH
                risks.append(RiskAssessment(
                    risk_id=f"SECURITY_001_{cert.get('id', 'unknown')}",
                    category=RiskCategory.SECURITY,
                    severity=severity,
                    description=f"Certificate {cert.get('id')} expires soon or has expired",
                    impact="Authentication failures, access denial",
                    likelihood=1.0 if expiry_time < current_time else 0.9,
                    mitigation_recommendations=[
                        "Renew certificate immediately",
                        "Implement automated certificate renewal",
                        "Set up certificate expiry monitoring"
                    ],
                    detected_at=time.time(),
                    affected_components=["security", "authentication"]
                ))
        
        # Authentication failure risks
        failed_auth = security_data.get('failed_authentications', 0)
        if failed_auth > self.thresholds['security']['max_failed_authentications']:
            risks.append(RiskAssessment(
                risk_id="SECURITY_002",
                category=RiskCategory.SECURITY,
                severity=RiskSeverity.MEDIUM,
                description=f"High authentication failure count: {failed_auth}",
                impact="Potential brute force attack, system overload",
                likelihood=0.7,
                mitigation_recommendations=[
                    "Implement rate limiting",
                    "Enable account lockout policies",
                    "Investigate authentication attempts"
                ],
                detected_at=time.time(),
                affected_components=["security", "authentication"]
            ))
        
        # Encryption strength risks
        encryption_configs = security_data.get('encryption_configs', [])
        for config in encryption_configs:
            key_size = config.get('key_size', 0)
            if key_size < self.thresholds['security']['encryption_strength_min']:
                risks.append(RiskAssessment(
                    risk_id=f"SECURITY_003_{config.get('id', 'unknown')}",
                    category=RiskCategory.SECURITY,
                    severity=RiskSeverity.HIGH,
                    description=f"Weak encryption key size: {key_size} bits",
                    impact="Cryptographic vulnerability, data breach risk",
                    likelihood=0.8,
                    mitigation_recommendations=[
                        "Upgrade to stronger encryption (AES-256)",
                        "Implement key rotation policies",
                        "Audit all encryption configurations"
                    ],
                    detected_at=time.time(),
                    affected_components=["security", "encryption"]
                ))
        
        return risks
    
    def analyze_performance_risks(self, performance_data: dict[str, Any]) -> list[RiskAssessment]:
        """
        Analyze performance-related risks.
        
        Args:
            performance_data: Current system performance data
            
        Returns:
            List of identified performance risks
        """
        risks = []
        
        # CPU usage risks
        cpu_usage = performance_data.get('cpu_usage', 0)
        if cpu_usage > self.thresholds['performance']['max_cpu_usage']:
            risks.append(RiskAssessment(
                risk_id="PERFORMANCE_001",
                category=RiskCategory.PERFORMANCE,
                severity=RiskSeverity.HIGH,
                description=f"High CPU usage: {cpu_usage}%",
                impact="System slowdown, potential service interruption",
                likelihood=0.8,
                mitigation_recommendations=[
                    "Scale out processing nodes",
                    "Optimize resource-intensive operations",
                    "Implement load balancing"
                ],
                detected_at=time.time(),
                affected_components=["performance", "system"]
            ))
        
        # Memory usage risks
        memory_usage = performance_data.get('memory_usage', 0)
        if memory_usage > self.thresholds['performance']['max_memory_usage']:
            risks.append(RiskAssessment(
                risk_id="PERFORMANCE_002",
                category=RiskCategory.PERFORMANCE,
                severity=RiskSeverity.HIGH,
                description=f"High memory usage: {memory_usage}%",
                impact="Memory exhaustion, system crashes",
                likelihood=0.9,
                mitigation_recommendations=[
                    "Increase system memory",
                    "Implement memory optimization",
                    "Add memory monitoring and alerting"
                ],
                detected_at=time.time(),
                affected_components=["performance", "memory"]
            ))
        
        # Event pool risks
        pool_size = performance_data.get('event_pool_size', 0)
        if pool_size > self.thresholds['performance']['max_event_pool_size']:
            risks.append(RiskAssessment(
                risk_id="PERFORMANCE_003",
                category=RiskCategory.PERFORMANCE,
                severity=RiskSeverity.MEDIUM,
                description=f"Event pool overflow: {pool_size} events",
                impact="Event drops, processing delays",
                likelihood=0.7,
                mitigation_recommendations=[
                    "Increase processing capacity",
                    "Implement pool size limits",
                    "Optimize event processing pipeline"
                ],
                detected_at=time.time(),
                affected_components=["performance", "ordering"]
            ))
        
        return risks
    
    def analyze_storage_risks(self, storage_data: dict[str, Any]) -> list[RiskAssessment]:
        """
        Analyze storage-related risks.
        
        Args:
            storage_data: Current storage system data
            
        Returns:
            List of identified storage risks
        """
        risks = []
        
        # World state size risks
        world_state_size = storage_data.get('world_state_size', 0)
        if world_state_size > self.thresholds['storage']['max_world_state_size']:
            risks.append(RiskAssessment(
                risk_id="STORAGE_001",
                category=RiskCategory.STORAGE,
                severity=RiskSeverity.MEDIUM,
                description=f"Large world state: {world_state_size} entries",
                impact="Slow queries, increased memory usage",
                likelihood=0.6,
                mitigation_recommendations=[
                    "Implement state pruning",
                    "Optimize storage indices",
                    "Consider data archiving"
                ],
                detected_at=time.time(),
                affected_components=["storage", "world_state"]
            ))
        
        # Backup interval risks
        last_backup = storage_data.get('last_backup_time', 0)
        current_time = time.time()
        backup_age = current_time - last_backup
        
        if backup_age > self.thresholds['storage']['backup_interval_max']:
            risks.append(RiskAssessment(
                risk_id="STORAGE_002",
                category=RiskCategory.STORAGE,
                severity=RiskSeverity.HIGH,
                description=f"Backup overdue: {backup_age / 3600:.1f} hours since last backup",
                impact="Data loss risk, recovery difficulties",
                likelihood=0.8,
                mitigation_recommendations=[
                    "Execute backup immediately",
                    "Implement automated backup scheduling",
                    "Set up backup monitoring"
                ],
                detected_at=time.time(),
                affected_components=["storage", "backup"]
            ))
        
        return risks
    
    def perform_comprehensive_analysis(self, system_data: dict[str, Any]) -> dict[str, list[RiskAssessment]]:
        """
        Perform comprehensive risk analysis across all categories.
        
        Args:
            system_data: Complete system data for analysis
            
        Returns:
            Dictionary of risks organized by category
        """
        all_risks = {
            'consensus': self.analyze_consensus_risks(system_data.get('consensus', {})),
            'security': self.analyze_security_risks(system_data.get('security', {})),
            'performance': self.analyze_performance_risks(system_data.get('performance', {})),
            'storage': self.analyze_storage_risks(system_data.get('storage', {}))
        }
        
        # Update active risks
        for category_risks in all_risks.values():
            for risk in category_risks:
                self.active_risks[risk.risk_id] = risk
                self.risk_history.append(risk)
        
        # Log critical risks
        for category, risks in all_risks.items():
            critical_risks = [r for r in risks if r.severity == RiskSeverity.CRITICAL]
            if critical_risks:
                self.logger.critical(f"Found {len(critical_risks)} critical risks in {category}")
        
        return all_risks
    
    def get_risk_summary(self) -> dict[str, Any]:
        """
        Get summary of current risk status.
        
        Returns:
            Risk summary statistics
        """
        if not self.active_risks:
            return {
                'total_risks': 0,
                'by_severity': {},
                'by_category': {},
                'highest_severity': None
            }
        
        risks = list(self.active_risks.values())
        severity_counts = {}
        category_counts = {}
        
        for risk in risks:
            severity_counts[risk.severity.value] = severity_counts.get(risk.severity.value, 0) + 1
            category_counts[risk.category.value] = category_counts.get(risk.category.value, 0) + 1
        
        # Find highest severity
        severity_order = [RiskSeverity.CRITICAL, RiskSeverity.HIGH, RiskSeverity.MEDIUM, RiskSeverity.LOW]
        highest_severity = None
        for severity in severity_order:
            if severity.value in severity_counts:
                highest_severity = severity.value
                break
        
        return {
            'total_risks': len(risks),
            'by_severity': severity_counts,
            'by_category': category_counts,
            'highest_severity': highest_severity,
            'last_analysis': time.time()
        }
    
    def resolve_risk(self, risk_id: str, resolution_notes: str = "") -> bool:
        """
        Mark a risk as resolved.
        
        Args:
            risk_id: ID of the risk to resolve
            resolution_notes: Notes about the resolution
            
        Returns:
            True if risk was found and resolved
        """
        if risk_id in self.active_risks:
            _risk = self.active_risks.pop(risk_id)
            self.logger.info(f"Risk {risk_id} resolved: {resolution_notes}")
            return True
        return False