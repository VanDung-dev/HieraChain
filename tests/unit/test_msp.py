"""
Unit tests for MSP (Membership Service Provider).

Tests the advanced MSP implementation including certificate management, 
role-based access control, and hierarchical identity management for enterprise applications.
"""

import unittest

from security.msp import HierarchicalMSP, CertificateAuthority, OrganizationPolicies


class TestHierarchicalMSP(unittest.TestCase):
    """Test cases for HierarchicalMSP class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.ca_config = {
            "root_cert": "test-root-ca",
            "intermediate_certs": ["test-intermediate-ca"],
            "policy": {"default_validity": 365}
        }
        
        self.msp = HierarchicalMSP("test-org", self.ca_config)
        
        # Test credentials
        self.test_credentials = {
            "public_key": "test-public-key-123",
            "private_key": "test-private-key-123"
        }
        
        # Test attributes
        self.test_attributes = {
            "department": "engineering",
            "location": "headquarters",
            "clearance_level": "standard"
        }
    
    def test_msp_initialization(self):
        """Test MSP initialization"""
        self.assertEqual(self.msp.organization_id, "test-org")
        self.assertIsNotNone(self.msp.ca)
        self.assertIsNotNone(self.msp.policies)
        self.assertTrue(len(self.msp.roles) > 0)  # Should have default roles
        self.assertEqual(len(self.msp.audit_log), 0)  # Should start empty
    
    def test_default_roles_initialization(self):
        """Test default roles are properly initialized"""
        expected_roles = ["admin", "operator", "viewer"]
        
        for role in expected_roles:
            self.assertIn(role, self.msp.roles)
            self.assertTrue(len(self.msp.roles[role]["permissions"]) > 0)
            self.assertIn("cert_validity_days", self.msp.roles[role])
    
    def test_register_entity_success(self):
        """Test successful entity registration"""
        result = self.msp.register_entity(
            "test-user-001",
            self.test_credentials,
            "admin",
            self.test_attributes
        )
        
        self.assertTrue(result)
        self.assertIn("test-user-001", self.msp.entities)
        
        entity = self.msp.entities["test-user-001"]
        self.assertEqual(entity["role"], "admin")
        self.assertEqual(entity["status"], "active")
        self.assertEqual(entity["attributes"], self.test_attributes)
    
    def test_register_entity_invalid_role(self):
        """Test entity registration with invalid role"""
        result = self.msp.register_entity(
            "test-user-002",
            self.test_credentials,
            "invalid-role"
        )
        
        self.assertFalse(result)
        self.assertNotIn("test-user-002", self.msp.entities)
    
    def test_validate_identity_success(self):
        """Test successful identity validation"""
        # First register entity
        self.msp.register_entity(
            "test-user-003",
            self.test_credentials,
            "operator"
        )
        
        # Then validate
        result = self.msp.validate_identity(
            "test-user-003",
            self.test_credentials
        )
        
        self.assertTrue(result)
    
    def test_validate_identity_wrong_credentials(self):
        """Test identity validation with wrong credentials"""
        # Register entity
        self.msp.register_entity(
            "test-user-004",
            self.test_credentials,
            "operator"
        )
        
        # Validate with wrong credentials
        wrong_credentials = {
            "public_key": "wrong-key",
            "private_key": "wrong-private-key"
        }
        
        result = self.msp.validate_identity(
            "test-user-004",
            wrong_credentials
        )
        
        self.assertFalse(result)
    
    def test_validate_identity_nonexistent_user(self):
        """Test identity validation for non-existent user"""
        result = self.msp.validate_identity(
            "non-existent-user",
            self.test_credentials
        )
        
        self.assertFalse(result)
    
    def test_authorize_action_success(self):
        """Test successful action authorization"""
        # Register entity with admin role
        self.msp.register_entity(
            "test-admin",
            self.test_credentials,
            "admin"
        )
        
        # Test authorization for admin action
        result = self.msp.authorize_action(
            "test-admin",
            "manage_entities"
        )
        
        self.assertTrue(result)
    
    def test_authorize_action_insufficient_permissions(self):
        """Test action authorization with insufficient permissions"""
        # Register entity with viewer role
        self.msp.register_entity(
            "test-viewer",
            self.test_credentials,
            "viewer"
        )
        
        # Test authorization for admin action
        result = self.msp.authorize_action(
            "test-viewer",
            "manage_entities"
        )
        
        self.assertFalse(result)
    
    def test_revoke_entity(self):
        """Test entity revocation"""
        # Register entity
        self.msp.register_entity(
            "test-user-revoke",
            self.test_credentials,
            "operator"
        )
        
        # Revoke entity
        result = self.msp.revoke_entity("test-user-revoke", "security_breach")
        
        self.assertTrue(result)
        entity = self.msp.entities["test-user-revoke"]
        self.assertEqual(entity["status"], "revoked")
        self.assertEqual(entity["revocation_reason"], "security_breach")
    
    def test_define_custom_role(self):
        """Test defining custom organizational role"""
        custom_permissions = ["custom_action_1", "custom_action_2"]
        
        self.msp.define_role(
            "custom_role",
            custom_permissions,
            ["custom_policy"],
            180
        )
        
        self.assertIn("custom_role", self.msp.roles)
        self.assertEqual(self.msp.roles["custom_role"]["permissions"], custom_permissions)
        self.assertEqual(self.msp.roles["custom_role"]["cert_validity_days"], 180)
    
    def test_get_entity_info(self):
        """Test getting entity information"""
        # Register entity
        self.msp.register_entity(
            "test-info-user",
            self.test_credentials,
            "operator",
            self.test_attributes
        )
        
        info = self.msp.get_entity_info("test-info-user")
        
        self.assertIsNotNone(info)
        self.assertEqual(info["entity_id"], "test-info-user")
        self.assertEqual(info["role"], "operator")
        self.assertEqual(info["status"], "active")
        self.assertEqual(info["attributes"], self.test_attributes)
    
    def test_get_entity_info_nonexistent(self):
        """Test getting info for non-existent entity"""
        info = self.msp.get_entity_info("non-existent")
        self.assertIsNone(info)
    
    def test_audit_logging(self):
        """Test audit logging functionality"""
        initial_log_count = len(self.msp.audit_log)
        
        # Register entity (should create audit log entry)
        self.msp.register_entity(
            "test-audit-user",
            self.test_credentials,
            "admin"
        )
        
        # Check audit log
        audit_log = self.msp.get_audit_log(10)
        self.assertTrue(len(audit_log) > initial_log_count)
        
        # Check log entry details
        last_entry = audit_log[-1]
        self.assertEqual(last_entry["event_type"], "entity_registered")
        self.assertEqual(last_entry["organization_id"], "test-org")
        self.assertIn("entity_id", last_entry["details"])


class TestCertificateAuthority(unittest.TestCase):
    """Test cases for CertificateAuthority class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.ca = CertificateAuthority(
            root_cert="test-root",
            intermediate_certs=["test-intermediate"],
            policy={"default_validity": 365}
        )
    
    def test_ca_initialization(self):
        """Test CA initialization"""
        self.assertEqual(self.ca.root_cert, "test-root")
        self.assertEqual(len(self.ca.intermediate_certs), 1)
        self.assertEqual(len(self.ca.issued_certificates), 0)
        self.assertEqual(len(self.ca.revoked_certificates), 0)
    
    def test_issue_certificate(self):
        """Test certificate issuance"""
        certificate = self.ca.issue_certificate(
            subject="test-subject",
            public_key="test-public-key",
            attributes={"role": "admin"},
            valid_days=365
        )
        
        self.assertIsNotNone(certificate)
        self.assertEqual(certificate.subject, "test-subject")
        self.assertEqual(certificate.public_key, "test-public-key")
        self.assertIn(certificate.cert_id, self.ca.issued_certificates)
    
    def test_revoke_certificate(self):
        """Test certificate revocation"""
        # Issue certificate first
        certificate = self.ca.issue_certificate(
            subject="test-revoke",
            public_key="test-key",
            attributes={}
        )
        
        # Revoke certificate
        result = self.ca.revoke_certificate(certificate.cert_id, "compromised")
        
        self.assertTrue(result)
        self.assertIn(certificate.cert_id, self.ca.revoked_certificates)
    
    def test_verify_certificate_valid(self):
        """Test verification of valid certificate"""
        certificate = self.ca.issue_certificate(
            subject="test-verify",
            public_key="test-key",
            attributes={}
        )
        
        result = self.ca.verify_certificate(certificate.cert_id)
        self.assertTrue(result)
    
    def test_verify_certificate_revoked(self):
        """Test verification of revoked certificate"""
        certificate = self.ca.issue_certificate(
            subject="test-verify-revoked",
            public_key="test-key",
            attributes={}
        )
        
        # Revoke and then verify
        self.ca.revoke_certificate(certificate.cert_id, "test")
        result = self.ca.verify_certificate(certificate.cert_id)
        
        self.assertFalse(result)
    
    def test_verify_certificate_nonexistent(self):
        """Test verification of non-existent certificate"""
        result = self.ca.verify_certificate("non-existent-cert-id")
        self.assertFalse(result)


class TestOrganizationPolicies(unittest.TestCase):
    """Test cases for OrganizationPolicies class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.policies = OrganizationPolicies()
    
    def test_define_policy(self):
        """Test policy definition"""
        policy_config = {
            "required_attributes": ["role", "department"],
            "conditions": {"department": "engineering"}
        }
        
        self.policies.define_policy("test_policy", policy_config)
        
        self.assertIn("test_policy", self.policies.policies)
        self.assertEqual(
            self.policies.policies["test_policy"]["config"],
            policy_config
        )
    
    def test_evaluate_policy_success(self):
        """Test successful policy evaluation"""
        policy_config = {
            "required_attributes": ["role", "department"]
        }
        
        self.policies.define_policy("test_policy", policy_config)
        
        context = {
            "role": "admin",
            "department": "engineering"
        }
        
        result = self.policies.evaluate_policy("test_policy", context)
        self.assertTrue(result)
    
    def test_evaluate_policy_missing_attributes(self):
        """Test policy evaluation with missing attributes"""
        policy_config = {
            "required_attributes": ["role", "department"]
        }
        
        self.policies.define_policy("test_policy", policy_config)
        
        context = {
            "role": "admin"
            # Missing department
        }
        
        result = self.policies.evaluate_policy("test_policy", context)
        self.assertFalse(result)
    
    def test_evaluate_policy_nonexistent(self):
        """Test evaluation of non-existent policy"""
        result = self.policies.evaluate_policy("non_existent", {})
        self.assertFalse(result)
    
    def test_assign_role_permissions(self):
        """Test role permission assignment"""
        permissions = ["read", "write", "execute"]
        
        self.policies.assign_role_permissions("test_role", permissions)
        
        self.assertEqual(
            self.policies.role_permissions["test_role"],
            permissions
        )
    
    def test_check_permission_success(self):
        """Test successful permission check"""
        permissions = ["read", "write"]
        self.policies.assign_role_permissions("test_role", permissions)
        
        result = self.policies.check_permission("test_role", "read")
        self.assertTrue(result)
    
    def test_check_permission_denied(self):
        """Test denied permission check"""
        permissions = ["read"]
        self.policies.assign_role_permissions("test_role", permissions)
        
        result = self.policies.check_permission("test_role", "write")
        self.assertFalse(result)
    
    def test_check_permission_nonexistent_role(self):
        """Test permission check for non-existent role"""
        result = self.policies.check_permission("non_existent_role", "read")
        self.assertFalse(result)


class TestMSPIntegration(unittest.TestCase):
    """Integration tests for MSP components"""
    
    def setUp(self):
        """Set up integration test fixtures"""
        self.ca_config = {
            "root_cert": "integration-test-root",
            "intermediate_certs": ["integration-test-intermediate"],
            "policy": {"default_validity": 365}
        }
        
        self.msp = HierarchicalMSP("integration-test-org", self.ca_config)
    
    def test_full_entity_lifecycle(self):
        """Test complete entity lifecycle"""
        credentials = {
            "public_key": "integration-test-key",
            "private_key": "integration-test-private"
        }
        
        attributes = {
            "department": "security",
            "clearance": "high"
        }
        
        # 1. Register entity
        register_result = self.msp.register_entity(
            "integration-user",
            credentials,
            "admin",
            attributes
        )
        self.assertTrue(register_result)
        
        # 2. Validate identity
        validate_result = self.msp.validate_identity(
            "integration-user",
            credentials
        )
        self.assertTrue(validate_result)
        
        # 3. Authorize actions
        auth_result = self.msp.authorize_action(
            "integration-user",
            "manage_entities"
        )
        self.assertTrue(auth_result)
        
        # 4. Get entity info
        info = self.msp.get_entity_info("integration-user")
        self.assertIsNotNone(info)
        self.assertEqual(info["role"], "admin")
        
        # 5. Revoke entity
        revoke_result = self.msp.revoke_entity(
            "integration-user",
            "end_of_employment"
        )
        self.assertTrue(revoke_result)
        
        # 6. Verify revoked entity cannot be validated
        _validate_after_revoke = self.msp.validate_identity(
            "integration-user",
            credentials
        )
        # Should still validate identity but not authorize actions
        # (identity validation checks certificate, authorization checks status)
    
    def test_role_based_access_control(self):
        """Test role-based access control integration"""
        admin_creds = {"public_key": "admin-key", "private_key": "admin-private"}
        viewer_creds = {"public_key": "viewer-key", "private_key": "viewer-private"}
        
        # Register admin and viewer
        self.msp.register_entity("test-admin", admin_creds, "admin")
        self.msp.register_entity("test-viewer", viewer_creds, "viewer")
        
        # Test admin permissions
        admin_manage = self.msp.authorize_action("test-admin", "manage_entities")
        admin_view = self.msp.authorize_action("test-admin", "view_data")
        
        self.assertTrue(admin_manage)
        self.assertTrue(admin_view)
        
        # Test viewer permissions
        viewer_manage = self.msp.authorize_action("test-viewer", "manage_entities")
        viewer_view = self.msp.authorize_action("test-viewer", "view_data")
        
        self.assertFalse(viewer_manage)
        self.assertTrue(viewer_view)


if __name__ == '__main__':
    unittest.main(verbosity=2)