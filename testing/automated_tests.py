"""
Automated Testing Module for Hierarchical Blockchain Framework

This module provides comprehensive automated testing capabilities for
risk management, mitigation strategies, and system validation.
Includes configuration validation, unit tests, and integration tests
for the risk management system.
"""

import time
import json
import pytest
import logging
from typing import Dict, List, Any, Tuple
import tempfile

from hierarchical_blockchain.risk_management.risk_analyzer import (
    RiskAnalyzer, RiskAssessment, RiskCategory, RiskSeverity
)
from hierarchical_blockchain.risk_management.mitigation_strategies import (
    MitigationManager, MitigationStatus, ConsensusMitigationStrategies,
    SecurityMitigationStrategies, PerformanceMitigationStrategies,
    StorageMitigationStrategies
)
from hierarchical_blockchain.risk_management.audit_logger import (
    AuditLogger, AuditEventType, AuditSeverity,
    FileAuditStorage, AuditFilter
)


class TestConfigurationValidator:
    """Test configuration validation for risk profiles"""
    
    @staticmethod
    def validate_risk_profile_config(config_path: str) -> Tuple[bool, List[str]]:
        """
        Validate risk profile configuration file.
        
        Args:
            config_path: Path to risk profile configuration file
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        try:
            with open(config_path, 'r') as f:
                if config_path.endswith('.json'):
                    config = json.load(f)
                elif config_path.endswith('.yaml') or config_path.endswith('.yml'):
                    import yaml
                    config = yaml.safe_load(f)
                else:
                    errors.append("Unsupported configuration file format")
                    return False, errors
            
            # Validate risk_management section
            if 'risk_management' not in config:
                errors.append("Missing 'risk_management' section")
                return False, errors
            
            risk_config = config['risk_management']
            
            # Validate consensus configuration
            if 'consensus' in risk_config:
                consensus_config = risk_config['consensus']
                if 'bft' in consensus_config:
                    bft_config = consensus_config['bft']
                    min_nodes = bft_config.get('min_nodes', 0)
                    fault_tolerance = bft_config.get('fault_tolerance', 1)
                    
                    if min_nodes < (3 * fault_tolerance + 1):
                        errors.append(f"BFT consensus: min_nodes ({min_nodes}) < 3*f+1 ({3*fault_tolerance+1})")
            
            # Validate security configuration
            if 'security' in risk_config:
                security_config = risk_config['security']
                if 'msp' in security_config:
                    msp_config = security_config['msp']
                    cert_lifetimes = msp_config.get('certificate_lifetimes', {})
                    
                    required_certs = ['root', 'intermediate', 'entity']
                    for cert_type in required_certs:
                        if cert_type not in cert_lifetimes:
                            errors.append(f"Missing certificate lifetime for: {cert_type}")
            
            # Validate performance thresholds
            if 'performance' in risk_config:
                perf_config = risk_config['performance']
                required_thresholds = ['ordering_service', 'caching']
                
                for threshold in required_thresholds:
                    if threshold not in perf_config:
                        errors.append(f"Missing performance threshold: {threshold}")
            
            # Validate mitigation configuration
            if 'mitigation' in config:
                mitigation_config = config['mitigation']
                if 'testing' in mitigation_config:
                    testing_config = mitigation_config['testing']
                    coverage_target = testing_config.get('coverage_target', 0)
                    
                    if coverage_target < 80:
                        errors.append(f"Test coverage target too low: {coverage_target}% (minimum 80%)")
            
            return len(errors) == 0, errors
            
        except Exception as e:
            errors.append(f"Configuration validation error: {str(e)}")
            return False, errors
    
    @staticmethod
    def validate_consensus_configuration(consensus_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate consensus configuration specifically for BFT requirements."""
        errors = []
        
        node_count = consensus_data.get('node_count', 0)
        fault_tolerance = consensus_data.get('fault_tolerance', 1)
        min_required = 3 * fault_tolerance + 1
        
        if node_count < min_required:
            errors.append(f"Insufficient nodes for BFT consensus: {node_count} < {min_required}")
        
        leader_timeout = consensus_data.get('leader_timeout', 0)
        if leader_timeout <= 0:
            errors.append("Leader timeout must be positive")
        
        if leader_timeout > 300:  # 5 minutes
            errors.append(f"Leader timeout too high: {leader_timeout}s (maximum 300s)")
        
        return len(errors) == 0, errors


class TestRiskAnalyzer:
    """Unit tests for RiskAnalyzer class"""
    
    def setup_method(self):
        """Setup test environment before each test"""
        self.risk_analyzer = RiskAnalyzer()
        self.sample_system_data = {
            'consensus': {
                'node_count': 3,
                'fault_tolerance': 1,
                'leader_timeout': 45,
                'failed_message_verifications': 10,
                'total_messages': 1000
            },
            'security': {
                'certificates': [
                    {
                        'id': 'cert_001',
                        'expires_at': time.time() + 86400  # Expires in 1 day
                    }
                ],
                'failed_authentications': 3,
                'encryption_configs': [
                    {
                        'id': 'config_001',
                        'key_size': 128  # Below recommended 256
                    }
                ]
            },
            'performance': {
                'cpu_usage': 85,  # Above threshold
                'memory_usage': 70,
                'event_pool_size': 5000
            },
            'storage': {
                'world_state_size': 500000,
                'last_backup_time': time.time() - 172800  # 2 days ago
            }
        }
    
    def test_consensus_risk_analysis(self):
        """Test consensus risk analysis"""
        risks = self.risk_analyzer.analyze_consensus_risks(self.sample_system_data['consensus'])
        
        # Should detect insufficient nodes (3 < 4 for f=1)
        consensus_001_risks = [r for r in risks if r.risk_id == 'CONSENSUS_001']
        assert len(consensus_001_risks) == 1
        assert consensus_001_risks[0].severity == RiskSeverity.CRITICAL
        
        # Should detect high leader timeout
        consensus_002_risks = [r for r in risks if r.risk_id == 'CONSENSUS_002']
        assert len(consensus_002_risks) == 1
        assert consensus_002_risks[0].severity == RiskSeverity.MEDIUM
    
    def test_security_risk_analysis(self):
        """Test security risk analysis"""
        risks = self.risk_analyzer.analyze_security_risks(self.sample_system_data['security'])
        
        # Should detect expiring certificate
        cert_risks = [r for r in risks if r.risk_id.startswith('SECURITY_001')]
        assert len(cert_risks) == 1
        assert cert_risks[0].severity == RiskSeverity.HIGH
        
        # Should detect weak encryption
        encryption_risks = [r for r in risks if r.risk_id.startswith('SECURITY_003')]
        assert len(encryption_risks) == 1
        assert encryption_risks[0].severity == RiskSeverity.HIGH
    
    def test_performance_risk_analysis(self):
        """Test performance risk analysis"""
        risks = self.risk_analyzer.analyze_performance_risks(self.sample_system_data['performance'])
        
        # Should detect high CPU usage
        cpu_risks = [r for r in risks if r.risk_id == 'PERFORMANCE_001']
        assert len(cpu_risks) == 1
        assert cpu_risks[0].severity == RiskSeverity.HIGH
    
    def test_storage_risk_analysis(self):
        """Test storage risk analysis"""
        risks = self.risk_analyzer.analyze_storage_risks(self.sample_system_data['storage'])
        
        # Should detect backup overdue
        backup_risks = [r for r in risks if r.risk_id == 'STORAGE_002']
        assert len(backup_risks) == 1
        assert backup_risks[0].severity == RiskSeverity.HIGH
    
    def test_comprehensive_analysis(self):
        """Test comprehensive risk analysis"""
        all_risks = self.risk_analyzer.perform_comprehensive_analysis(self.sample_system_data)
        
        assert 'consensus' in all_risks
        assert 'security' in all_risks
        assert 'performance' in all_risks
        assert 'storage' in all_risks
        
        # Should have detected multiple risks
        total_risk_count = sum(len(risks) for risks in all_risks.values())
        assert total_risk_count > 0
    
    def test_risk_summary(self):
        """Test risk summary generation"""
        self.risk_analyzer.perform_comprehensive_analysis(self.sample_system_data)
        summary = self.risk_analyzer.get_risk_summary()
        
        assert 'total_risks' in summary
        assert 'by_severity' in summary
        assert 'by_category' in summary
        assert 'highest_severity' in summary
        
        assert summary['total_risks'] > 0
        assert summary['highest_severity'] == 'critical'


class TestMitigationManager:
    """Unit tests for MitigationManager class"""
    
    def setup_method(self):
        """Setup test environment before each test"""
        self.mitigation_manager = MitigationManager()
        
        # Create sample risk assessments
        self.sample_risks = [
            RiskAssessment(
                risk_id="CONSENSUS_001",
                category=RiskCategory.CONSENSUS,
                severity=RiskSeverity.CRITICAL,
                description="Insufficient validator nodes",
                impact="Consensus failure",
                likelihood=0.9,
                mitigation_recommendations=["Add more nodes"],
                detected_at=time.time(),
                affected_components=["consensus"]
            ),
            RiskAssessment(
                risk_id="SECURITY_001_cert001",
                category=RiskCategory.SECURITY,
                severity=RiskSeverity.HIGH,
                description="Certificate expiring",
                impact="Authentication failure",
                likelihood=0.8,
                mitigation_recommendations=["Renew certificate"],
                detected_at=time.time(),
                affected_components=["security"]
            )
        ]
    
    def test_mitigation_plan_creation(self):
        """Test creation of mitigation plans from risks"""
        plan = self.mitigation_manager.create_mitigation_plan(self.sample_risks)
        
        assert len(plan) > 0
        
        # Should have actions for consensus and security risks
        action_ids = [action.action_id for action, _ in plan]
        assert 'add_validator_nodes' in action_ids
        assert 'renew_certificates' in action_ids
    
    def test_consensus_mitigation_strategies(self):
        """Test consensus mitigation strategies"""
        # Test add_validator_nodes
        result = ConsensusMitigationStrategies.add_validator_nodes({
            'required_count': 2,
            'node_configs': []
        })
        assert result == True
        
        # Test optimize_leader_timeout
        result = ConsensusMitigationStrategies.optimize_leader_timeout({
            'target_timeout': 15,
            'network_latency': 2.0
        })
        assert result == True
    
    def test_security_mitigation_strategies(self):
        """Test security mitigation strategies"""
        # Test renew_certificates
        result = SecurityMitigationStrategies.renew_certificates({
            'certificate_ids': ['cert_001', 'cert_002'],
            'ca_config': {}
        })
        assert result == True
        
        # Test implement_rate_limiting
        result = SecurityMitigationStrategies.implement_rate_limiting({
            'max_attempts': 5,
            'time_window': 300
        })
        assert result == True
    
    def test_performance_mitigation_strategies(self):
        """Test performance mitigation strategies"""
        # Test scale_processing_capacity
        result = PerformanceMitigationStrategies.scale_processing_capacity({
            'target_capacity': 3,
            'scaling_type': 'horizontal'
        })
        assert result == True
        
        # Test optimize_memory_usage
        result = PerformanceMitigationStrategies.optimize_memory_usage({
            'optimization_targets': ['caching', 'garbage_collection'],
            'memory_limit': '4GB'
        })
        assert result == True
    
    def test_storage_mitigation_strategies(self):
        """Test storage mitigation strategies"""
        # Test execute_backup
        result = StorageMitigationStrategies.execute_backup({
            'backup_target': '/tmp/test_backup',
            'compression': True
        })
        assert result == True
        
        # Test implement_state_pruning
        result = StorageMitigationStrategies.implement_state_pruning({
            'retention_days': 90,
            'pruning_interval': 86400
        })
        assert result == True
    
    def test_mitigation_execution(self):
        """Test execution of mitigation plans"""
        plan = self.mitigation_manager.create_mitigation_plan(self.sample_risks)
        results = self.mitigation_manager.execute_mitigation_plan(plan)
        
        assert len(results) > 0
        
        for result in results:
            assert result.status in [MitigationStatus.COMPLETED, MitigationStatus.FAILED]
            assert result.start_time > 0
            assert result.end_time is not None
    
    def test_execution_status_tracking(self):
        """Test tracking of execution status"""
        plan = self.mitigation_manager.create_mitigation_plan(self.sample_risks)
        self.mitigation_manager.execute_mitigation_plan(plan)
        
        status = self.mitigation_manager.get_execution_status()
        
        assert 'total_executed' in status
        assert 'success_rate' in status
        assert 'average_duration' in status
        
        assert status['total_executed'] > 0
        assert 0.0 <= status['success_rate'] <= 1.0


class TestAuditLogger:
    """Unit tests for AuditLogger class"""
    
    def setup_method(self):
        """Setup test environment before each test"""
        # Create temporary directory for audit logs
        self.temp_dir = tempfile.mkdtemp()
        self.audit_storage = FileAuditStorage(self.temp_dir)
        self.audit_logger = AuditLogger(storage=self.audit_storage)
    
    def teardown_method(self):
        """Cleanup after each test"""
        # Clean up temporary files
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_risk_detection_logging(self):
        """Test logging of risk detection events"""
        self.audit_logger.log_risk_detection(
            risk_id="TEST_RISK_001",
            risk_category="consensus",
            severity="warning",
            description="Test risk detected",
            affected_components=["consensus", "network"],
            details={"test_param": "test_value"}
        )
        
        # Query for the logged event
        filter_criteria = AuditFilter(
            event_types=[AuditEventType.RISK_DETECTED]
        )
        events = self.audit_logger.query_events(filter_criteria)
        
        assert len(events) == 1
        assert events[0].event_type == AuditEventType.RISK_DETECTED
        assert events[0].severity == AuditSeverity.WARNING
        assert "TEST_RISK_001" in events[0].details['risk_id']
    
    def test_mitigation_action_logging(self):
        """Test logging of mitigation action events"""
        self.audit_logger.log_mitigation_action(
            action_id="TEST_ACTION_001",
            status="completed",
            description="Test mitigation completed",
            details={"duration": 30.5}
        )
        
        filter_criteria = AuditFilter(
            event_types=[AuditEventType.MITIGATION_COMPLETED]
        )
        events = self.audit_logger.query_events(filter_criteria)
        
        assert len(events) == 1
        assert events[0].event_type == AuditEventType.MITIGATION_COMPLETED
        assert events[0].details['action_id'] == "TEST_ACTION_001"
    
    def test_security_event_logging(self):
        """Test logging of security events"""
        self.audit_logger.log_security_event(
            event_type="authentication_failure",
            description="Failed login attempt",
            details={"username": "test_user", "attempts": 3},
            user_id="user_001",
            ip_address="192.168.1.100",
            severity="warning"
        )
        
        filter_criteria = AuditFilter(
            event_types=[AuditEventType.SECURITY_EVENT]
        )
        events = self.audit_logger.query_events(filter_criteria)
        
        assert len(events) == 1
        assert events[0].event_type == AuditEventType.SECURITY_EVENT
        assert events[0].user_id == "user_001"
        assert events[0].ip_address == "192.168.1.100"
    
    def test_performance_event_logging(self):
        """Test logging of performance events"""
        self.audit_logger.log_performance_event(
            metric_name="cpu_usage",
            value=85.5,
            threshold=80.0,
            description="CPU usage exceeded threshold",
            details={"host": "blockchain-node-01"}
        )
        
        filter_criteria = AuditFilter(
            event_types=[AuditEventType.PERFORMANCE_EVENT]
        )
        events = self.audit_logger.query_events(filter_criteria)
        
        assert len(events) == 1
        assert events[0].event_type == AuditEventType.PERFORMANCE_EVENT
        assert events[0].details['metric_name'] == "cpu_usage"
        assert events[0].details['value'] == 85.5
    
    def test_audit_event_filtering(self):
        """Test filtering of audit events"""
        # Log multiple events with different severities
        self.audit_logger.log_risk_detection(
            "RISK_001", "consensus", "critical", "Critical risk",
            ["consensus"], {}
        )
        self.audit_logger.log_risk_detection(
            "RISK_002", "security", "warning", "Warning risk",
            ["security"], {}
        )
        
        # Filter for critical events only
        critical_filter = AuditFilter(
            severity_levels=[AuditSeverity.CRITICAL]
        )
        critical_events = self.audit_logger.query_events(critical_filter)
        
        assert len(critical_events) == 1
        assert critical_events[0].severity == AuditSeverity.CRITICAL
    
    def test_report_generation(self):
        """Test audit report generation"""
        self.audit_logger.log_risk_detection(
            "RISK_001", "consensus", "warning", "Test risk",
            ["consensus"], {}
        )
        
        filter_criteria = AuditFilter()
        
        # Test JSON report
        json_report = self.audit_logger.generate_report(filter_criteria, "json")
        assert json_report.startswith('[')
        
        # Test CSV report
        csv_report = self.audit_logger.generate_report(filter_criteria, "csv")
        assert "event_id,event_type,severity" in csv_report
    
    def test_audit_statistics(self):
        """Test audit statistics tracking"""
        # Log some events
        self.audit_logger.log_risk_detection(
            "RISK_001", "consensus", "warning", "Test risk", ["consensus"], {}
        )
        self.audit_logger.log_mitigation_action(
            "ACTION_001", "completed", "Test action", {}
        )
        
        stats = self.audit_logger.get_statistics()
        
        assert stats['total_events'] == 2
        assert 'risk_detected' in stats['events_by_type']
        assert 'mitigation_completed' in stats['events_by_type']
        assert 'warning' in stats['events_by_severity']


class TestIntegrationScenarios:
    """Integration tests for complete risk management workflows"""
    
    def setup_method(self):
        """Setup integration test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.audit_storage = FileAuditStorage(self.temp_dir)
        self.audit_logger = AuditLogger(storage=self.audit_storage)
        self.risk_analyzer = RiskAnalyzer()
        self.mitigation_manager = MitigationManager()
    
    def teardown_method(self):
        """Cleanup after integration tests"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_end_to_end_risk_management(self):
        """Test complete end-to-end risk management workflow"""
        # Step 1: System data indicates risks
        system_data = {
            'consensus': {
                'node_count': 3,
                'fault_tolerance': 1,
                'leader_timeout': 45,
                'failed_message_verifications': 0,
                'total_messages': 1000
            },
            'security': {
                'certificates': [],
                'failed_authentications': 2,
                'encryption_configs': []
            },
            'performance': {
                'cpu_usage': 60,
                'memory_usage': 70,
                'event_pool_size': 5000
            },
            'storage': {
                'world_state_size': 500000,
                'last_backup_time': time.time() - 100000  # Very old backup (over 24 hours)
            }
        }
        
        # Step 2: Analyze risks
        all_risks = self.risk_analyzer.perform_comprehensive_analysis(system_data)
        
        # Should detect at least consensus and storage risks
        assert len(all_risks['consensus']) > 0  # Insufficient nodes
        assert len(all_risks['storage']) > 0    # Old backup
        
        # Step 3: Log risk detection
        for category, risks in all_risks.items():
            for risk in risks:
                # Map RiskSeverity to AuditSeverity
                severity_mapping = {
                    "low": "info",
                    "medium": "warning", 
                    "high": "error",
                    "critical": "critical"
                }
                audit_severity = severity_mapping.get(risk.severity.value, "warning")
                
                self.audit_logger.log_risk_detection(
                    risk_id=risk.risk_id,
                    risk_category=risk.category.value,
                    severity=audit_severity,
                    description=risk.description,
                    affected_components=risk.affected_components,
                    details={"impact": risk.impact, "likelihood": risk.likelihood}
                )
        
        # Step 4: Create and execute mitigation plan
        all_risks_list = []
        for risks in all_risks.values():
            all_risks_list.extend(risks)
        
        mitigation_plan = self.mitigation_manager.create_mitigation_plan(all_risks_list)
        assert len(mitigation_plan) > 0
        
        # Step 5: Execute mitigations and log actions
        results = self.mitigation_manager.execute_mitigation_plan(mitigation_plan)
        
        for result in results:
            self.audit_logger.log_mitigation_action(
                action_id=result.action_id,
                status=result.status.value,
                description=f"Mitigation execution result",
                details=result.output
            )
        
        # Step 6: Verify audit trail
        risk_events = self.audit_logger.query_events(
            AuditFilter(event_types=[AuditEventType.RISK_DETECTED])
        )
        mitigation_events = self.audit_logger.query_events(
            AuditFilter(event_types=[AuditEventType.MITIGATION_COMPLETED, AuditEventType.MITIGATION_FAILED])
        )
        
        assert len(risk_events) > 0
        assert len(mitigation_events) > 0
        
        # Step 7: Generate comprehensive report
        all_events_filter = AuditFilter()
        report = self.audit_logger.generate_report(all_events_filter, "json")
        
        assert len(report) > 0
        report_data = json.loads(report)
        assert len(report_data) > 0


# Pytest fixtures and configuration
@pytest.fixture
def sample_risk_config():
    """Fixture providing sample risk configuration"""
    return {
        "risk_management": {
            "consensus": {
                "bft": {
                    "min_nodes": 4,
                    "fault_tolerance": 1,
                    "message_verification": "strict"
                }
            },
            "security": {
                "msp": {
                    "certificate_lifetimes": {
                        "root": 3650,
                        "intermediate": 1825,
                        "entity": 365
                    },
                    "revocation_check": "daily"
                }
            },
            "performance": {
                "ordering_service": {
                    "batch_size": 250,
                    "timeout": 2.0,
                    "pool_limit": 10000
                },
                "caching": {
                    "eviction_policy": "LRU",
                    "max_size": 50000
                }
            }
        },
        "mitigation": {
            "testing": {
                "automated": True,
                "coverage_target": 90
            }
        }
    }


def run_automated_tests():
    """
    Entry point for running automated tests.
    
    This function can be called from the command line or other modules
    to execute the complete test suite.
    """
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Run pytest with specific options
    exit_code = pytest.main([
        __file__,
        "-v",  # Verbose output
        "--tb=short",  # Short traceback format
        "--durations=10",  # Show 10 slowest tests
    ])
    
    return exit_code == 0


if __name__ == "__main__":
    # Run tests when module is executed directly
    success = run_automated_tests()
    exit(0 if success else 1)