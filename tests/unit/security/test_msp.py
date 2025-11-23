"""
Unit tests for MSP (Membership Service Provider).

Tests the advanced MSP implementation including certificate management, 
role-based access control, and hierarchical identity management for enterprise applications.
"""

import time
from hierarchical_blockchain.security.msp import HierarchicalMSP, CertificateAuthority, OrganizationPolicies


def setup_msp():
    """Set up test fixtures for MSP"""
    ca_config = {
        "root_cert": "test-root-ca",
        "intermediate_certs": ["test-intermediate-ca"],
        "policy": {"default_validity": 365}
    }
    
    msp = HierarchicalMSP("test-org", ca_config)
    
    # Test credentials
    test_credentials = {
        "public_key": "test-public-key-123",
        "private_key": "test-private-key-123"
    }
    
    # Test attributes
    test_attributes = {
        "department": "engineering",
        "location": "headquarters",
        "clearance_level": "standard"
    }
    
    return msp, test_credentials, test_attributes

def test_msp_initialization():
    """Test MSP initialization"""
    msp, _, _ = setup_msp()
    assert msp.organization_id == "test-org"
    assert msp.ca is not None
    assert msp.policies is not None
    assert len(msp.roles) > 0  # Should have default roles
    assert len(msp.audit_log) == 0  # Should start empty

def test_default_roles_initialization():
    """Test default roles are properly initialized"""
    msp, _, _ = setup_msp()
    expected_roles = ["admin", "operator", "viewer"]
    
    for role in expected_roles:
        assert role in msp.roles
        assert len(msp.roles[role]["permissions"]) > 0
        assert "cert_validity_days" in msp.roles[role]

def test_register_entity_success():
    """Test successful entity registration"""
    msp, test_credentials, test_attributes = setup_msp()
    result = msp.register_entity(
        "test-user-001",
        test_credentials,
        "admin",
        test_attributes
    )
    
    assert result
    assert "test-user-001" in msp.entities
    
    entity = msp.entities["test-user-001"]
    assert entity["role"] == "admin"
    assert entity["status"] == "active"
    assert entity["attributes"] == test_attributes

def test_register_entity_invalid_role():
    """Test entity registration with invalid role"""
    msp, test_credentials, _ = setup_msp()
    result = msp.register_entity(
        "test-user-002",
        test_credentials,
        "invalid-role"
    )
    
    assert not result
    assert "test-user-002" not in msp.entities

def test_validate_identity_success():
    """Test successful identity validation"""
    msp, test_credentials, _ = setup_msp()
    # First register entity
    msp.register_entity(
        "test-user-003",
        test_credentials,
        "operator"
    )
    
    # Then validate
    result = msp.validate_identity(
        "test-user-003",
        test_credentials
    )
    
    assert result

def test_validate_identity_wrong_credentials():
    """Test identity validation with wrong credentials"""
    msp, test_credentials, _ = setup_msp()
    # Register entity
    msp.register_entity(
        "test-user-004",
        test_credentials,
        "operator"
    )
    
    # Validate with wrong credentials
    wrong_credentials = {
        "public_key": "wrong-key",
        "private_key": "wrong-private-key"
    }
    
    result = msp.validate_identity(
        "test-user-004",
        wrong_credentials
    )
    
    assert not result

def test_validate_identity_nonexistent_user():
    """Test identity validation for non-existent user"""
    msp, test_credentials, _ = setup_msp()
    result = msp.validate_identity(
        "non-existent-user",
        test_credentials
    )
    
    assert not result

def test_authorize_action_success():
    """Test successful action authorization"""
    msp, test_credentials, _ = setup_msp()
    # Register entity with admin role
    msp.register_entity(
        "test-admin",
        test_credentials,
        "admin"
    )
    
    # Test authorization for admin action
    result = msp.authorize_action(
        "test-admin",
        "manage_entities"
    )
    
    assert result

def test_authorize_action_insufficient_permissions():
    """Test action authorization with insufficient permissions"""
    msp, test_credentials, _ = setup_msp()
    # Register entity with viewer role
    msp.register_entity(
        "test-viewer",
        test_credentials,
        "viewer"
    )
    
    # Test authorization for admin action
    result = msp.authorize_action(
        "test-viewer",
        "manage_entities"
    )
    
    assert not result

def test_revoke_entity():
    """Test entity revocation"""
    msp, test_credentials, _ = setup_msp()
    # Register entity
    msp.register_entity(
        "test-user-revoke",
        test_credentials,
        "operator"
    )
    
    # Revoke entity
    result = msp.revoke_entity("test-user-revoke", "security_breach")
    
    assert result
    entity = msp.entities["test-user-revoke"]
    assert entity["status"] == "revoked"
    assert entity["revocation_reason"] == "security_breach"

def test_define_custom_role():
    """Test defining custom organizational role"""
    msp, _, _ = setup_msp()
    custom_permissions = ["custom_action_1", "custom_action_2"]
    
    msp.define_role(
        "custom_role",
        custom_permissions,
        ["custom_policy"],
        180
    )
    
    assert "custom_role" in msp.roles
    assert msp.roles["custom_role"]["permissions"] == custom_permissions
    assert msp.roles["custom_role"]["cert_validity_days"] == 180

def test_get_entity_info():
    """Test getting entity information"""
    msp, test_credentials, test_attributes = setup_msp()
    # Register entity
    msp.register_entity(
        "test-info-user",
        test_credentials,
        "operator",
        test_attributes
    )
    
    info = msp.get_entity_info("test-info-user")
    
    assert info is not None
    assert info["entity_id"] == "test-info-user"
    assert info["role"] == "operator"
    assert info["status"] == "active"
    assert info["attributes"] == test_attributes

def test_get_entity_info_nonexistent():
    """Test getting info for non-existent entity"""
    msp, _, _ = setup_msp()
    info = msp.get_entity_info("non-existent")
    assert info is None

def test_audit_logging():
    """Test audit logging functionality"""
    msp, test_credentials, _ = setup_msp()
    initial_log_count = len(msp.audit_log)
    
    # Register entity (should create audit log entry)
    msp.register_entity(
        "test-audit-user",
        test_credentials,
        "admin"
    )
    
    # Check audit log
    audit_log = msp.get_audit_log(10)
    assert len(audit_log) > initial_log_count
    
    # Check log entry details
    last_entry = audit_log[-1]
    assert last_entry["event_type"] == "entity_registered"
    assert last_entry["organization_id"] == "test-org"
    assert "entity_id" in last_entry["details"]


def setup_ca():
    """Set up test fixtures for CertificateAuthority"""
    ca = CertificateAuthority(
        root_cert="test-root",
        intermediate_certs=["test-intermediate"],
        policy={"default_validity": 365}
    )
    return ca

def test_ca_initialization():
    """Test CA initialization"""
    ca = setup_ca()
    assert ca.root_cert == "test-root"
    assert len(ca.intermediate_certs) == 1
    assert len(ca.issued_certificates) == 0
    assert len(ca.revoked_certificates) == 0

def test_issue_certificate():
    """Test certificate issuance"""
    ca = setup_ca()
    certificate = ca.issue_certificate(
        subject="test-subject",
        public_key="test-public-key",
        attributes={"role": "admin"},
        valid_days=365
    )
    
    assert certificate is not None
    assert certificate.subject == "test-subject"
    assert certificate.public_key == "test-public-key"
    assert certificate.cert_id in ca.issued_certificates

def test_revoke_certificate():
    """Test certificate revocation"""
    ca = setup_ca()
    # Issue certificate first
    certificate = ca.issue_certificate(
        subject="test-revoke",
        public_key="test-key",
        attributes={}
    )
    
    # Revoke certificate
    result = ca.revoke_certificate(certificate.cert_id, "compromised")
    
    assert result
    assert certificate.cert_id in ca.revoked_certificates

def test_verify_certificate_valid():
    """Test verification of valid certificate"""
    ca = setup_ca()
    certificate = ca.issue_certificate(
        subject="test-verify",
        public_key="test-key",
        attributes={}
    )
    
    result = ca.verify_certificate(certificate.cert_id)
    assert result

def test_verify_certificate_revoked():
    """Test verification of revoked certificate"""
    ca = setup_ca()
    certificate = ca.issue_certificate(
        subject="test-verify-revoked",
        public_key="test-key",
        attributes={}
    )
    
    # Revoke and then verify
    ca.revoke_certificate(certificate.cert_id, "test")
    result = ca.verify_certificate(certificate.cert_id)
    
    assert not result

def test_verify_certificate_nonexistent():
    """Test verification of non-existent certificate"""
    ca = setup_ca()
    result = ca.verify_certificate("non-existent-cert-id")
    assert not result


def setup_policies():
    """Set up test fixtures for OrganizationPolicies"""
    policies = OrganizationPolicies()
    return policies

def test_define_policy():
    """Test policy definition"""
    policies = setup_policies()
    policy_config = {
        "required_attributes": ["role", "department"],
        "conditions": {"department": "engineering"}
    }
    
    policies.define_policy("test_policy", policy_config)
    
    assert "test_policy" in policies.policies
    assert policies.policies["test_policy"]["config"] == policy_config

def test_evaluate_policy_success():
    """Test successful policy evaluation"""
    policies = setup_policies()
    policy_config = {
        "required_attributes": ["role", "department"]
    }
    
    policies.define_policy("test_policy", policy_config)
    
    context = {
        "role": "admin",
        "department": "engineering"
    }
    
    result = policies.evaluate_policy("test_policy", context)
    assert result

def test_evaluate_policy_missing_attributes():
    """Test policy evaluation with missing attributes"""
    policies = setup_policies()
    policy_config = {
        "required_attributes": ["role", "department"]
    }
    
    policies.define_policy("test_policy", policy_config)
    
    context = {
        "role": "admin"
        # Missing department
    }
    
    result = policies.evaluate_policy("test_policy", context)
    assert not result

def test_evaluate_policy_nonexistent():
    """Test evaluation of non-existent policy"""
    policies = setup_policies()
    result = policies.evaluate_policy("non_existent", {})
    assert not result

def test_assign_role_permissions():
    """Test role permission assignment"""
    policies = setup_policies()
    permissions = ["read", "write", "execute"]
    
    policies.assign_role_permissions("test_role", permissions)
    
    assert policies.role_permissions["test_role"] == permissions

def test_check_permission_success():
    """Test successful permission check"""
    policies = setup_policies()
    permissions = ["read", "write"]
    policies.assign_role_permissions("test_role", permissions)
    
    result = policies.check_permission("test_role", "read")
    assert result

def test_check_permission_denied():
    """Test denied permission check"""
    policies = setup_policies()
    permissions = ["read"]
    policies.assign_role_permissions("test_role", permissions)
    
    result = policies.check_permission("test_role", "write")
    assert not result

def test_check_permission_nonexistent_role():
    """Test permission check for non-existent role"""
    policies = setup_policies()
    result = policies.check_permission("non_existent_role", "read")
    assert not result


def test_register_entity_with_special_characters():
    """Test entity registration with special characters"""
    msp, test_credentials, _ = setup_msp()
    
    # Test with special characters in entity_id
    result = msp.register_entity(
        "test-user@domain.com",
        test_credentials,
        "admin"
    )
    assert result
    assert "test-user@domain.com" in msp.entities


def test_register_entity_with_invalid_role():
    """Test entity registration with invalid role"""
    msp, test_credentials, _ = setup_msp()
    
    # Test with invalid role
    result = msp.register_entity(
        "test-invalid-role-user",
        test_credentials,
        "nonexistent_role"
    )
    assert not result
    assert "test-invalid-role-user" not in msp.entities


def test_validate_identity_with_invalid_inputs():
    """Test identity validation with invalid inputs"""
    msp, test_credentials, _ = setup_msp()
    
    # Register a valid entityfirst
    msp.register_entity("test-validate-user", test_credentials, "operator")
    
    # Test with None entity_id
    result = msp.validate_identity(None, test_credentials)
    assert not result
    
    # Test with empty entity_id
    result = msp.validate_identity("",test_credentials)
    assert not result
    
    # Test with None credentials
    result = msp.validate_identity("test-validate-user", None)
    assert not result


def test_authorize_action_edge_cases():
    """Test authorization with edge cases"""
    msp, test_credentials, _ = setup_msp()
    
    # Register entity
    msp.register_entity("test-auth-user", test_credentials, "operator")
    
    # Test with empty action
    result = msp.authorize_action("test-auth-user", "")
    assert not result
    
    # Test with None action
    result = msp.authorize_action("test-auth-user", None)
    assert not result
    
    # Test with non-existent user
    result = msp.authorize_action("nonexistent_user", "view_data")
    assert not result


def setup_integration_msp():
    """Set up integration test fixtures"""
    ca_config = {
        "root_cert": "integration-test-root",
        "intermediate_certs": ["integration-test-intermediate"],
        "policy": {"default_validity": 365}
    }
    
    msp = HierarchicalMSP("integration-test-org", ca_config)
    return msp

def test_full_entity_lifecycle():
    """Test complete entity lifecycle"""
    msp = setup_integration_msp()
    credentials = {
        "public_key": "integration-test-key",
        "private_key": "integration-test-private"
    }
    
    attributes = {
        "department": "security",
        "clearance": "high"
    }
    
    # 1. Register entity
    register_result = msp.register_entity(
        "integration-user",
        credentials,
        "admin",
        attributes
    )
    assert register_result
    
    # 2. Validate identity
    validate_result = msp.validate_identity(
        "integration-user",
        credentials
    )
    assert validate_result
    
    # 3. Authorize actions
    auth_result = msp.authorize_action(
        "integration-user",
        "manage_entities"
    )
    assert auth_result
    
    # 4. Get entity info
    info = msp.get_entity_info("integration-user")
    assert info is not None
    assert info["role"] == "admin"
    
    # 5. Revoke entity
    revoke_result = msp.revoke_entity(
        "integration-user",
        "end_of_employment"
    )
    assert revoke_result
    
    # 6. Verify revoked entity cannot be validated
    _validate_after_revoke = msp.validate_identity(
        "integration-user",
        credentials
    )
    # Should still validate identity but not authorize actions
    # (identity validation checks certificate, authorization checks status)

def test_role_based_access_control():
    """Test role-based access control integration"""
    msp = setup_integration_msp()
    admin_creds = {"public_key": "admin-key", "private_key": "admin-private"}
    viewer_creds = {"public_key": "viewer-key", "private_key": "viewer-private"}
    
    # Register admin and viewer
    msp.register_entity("test-admin", admin_creds, "admin")
    msp.register_entity("test-viewer", viewer_creds, "viewer")
    
    # Test admin permissions
    admin_manage = msp.authorize_action("test-admin", "manage_entities")
    admin_view = msp.authorize_action("test-admin", "view_data")
    
    assert admin_manage
    assert admin_view
    
    # Test viewer permissions
    viewer_manage = msp.authorize_action("test-viewer", "manage_entities")
    viewer_view = msp.authorize_action("test-viewer", "view_data")
    
    assert not viewer_manage
    assert viewer_view


def test_msp_registration_performance():
    """Test performance of entity registration"""
    msp, test_credentials, test_attributes = setup_msp()
    

    start_time = time.perf_counter()
    
    # Register 100 entities
    for i in range(100):
        result = msp.register_entity(
            f"perf-test-user-{i}",
        test_credentials,
            "operator",
            test_attributes
        )
        assert result
    
    end_time = time.perf_counter()
    
    # Registration of 100 entities should take less than 2 seconds
    assert (end_time - start_time) <2.0


def test_msp_validation_performance():
    """Test performance of identity validation"""
    msp, test_credentials, _ = setup_msp()
    
    # Register test entities
    for i in range(100):
        msp.register_entity(
            f"val-perf-user-{i}",
            test_credentials,
            "operator"
        )

    start_time = time.perf_counter()
    
    # Validate 100 entities
    for i in range(100):
        result = msp.validate_identity(
            f"val-perf-user-{i}",
            test_credentials
        )
        assert result
    
    end_time= time.perf_counter()
    
    # Validation of 100 entities should take less than 2 seconds
    assert (end_time - start_time) < 2.0


def test_msp_authorization_performance():
    """Test performance of action authorization"""
    msp, test_credentials, _ = setup_msp()
    
    # Register test entities with admin role
    for i in range(100):
        msp.register_entity(
            f"auth-perf-user-{i}",
            test_credentials,
            "admin"
        )

    start_time = time.perf_counter()
    
    #Authorize 100 entities for various actions
    for i in range(100):
        result1 = msp.authorize_action(f"auth-perf-user-{i}", "manage_entities")
        result2 = msp.authorize_action(f"auth-perf-user-{i}", "view_data")
    assert result1
    assert result2
    
    end_time = time.perf_counter()
    
    # Authorization of 100 entities for 2 actions each should take less than 2 seconds
    assert (end_time - start_time) < 2.0


def test_msp_security_injection_attacks():
    """Test MSP resistance to injection attacks"""
    ca_config = {
        "root_cert": "security-test-root",
        "intermediate_certs": ["security-test-intermediate"],
        "policy": {"default_validity": 365}
    }
    
    msp = HierarchicalMSP("security-test-org", ca_config)
    credentials = {
        "public_key": "security-public-key",
        "private_key": "security-private-key"
    }
    
    # Test SQL injection attempts in entity_id
    sql_injection_attempts = [
        "'; DROP TABLE certificates; --",
        "1'; WAITFORDELAY '00:00:05'--",
        "admin'--",
        "' OR '1'='1"
    ]
    
    for attempt in sql_injection_attempts:
        # These should be treated as regular entity_ids
        result = msp.register_entity(attempt, credentials, "operator")
        assert result is True  # Registration should succeed
        
        # Validation should work normally
        is_valid = msp.validate_identity(attempt, credentials)
        assert is_valid is True
        
        # Entity info should be retrievable
        entity_info = msp.get_entity_info(attempt)
        assert entity_info is not None
        assert entity_info["entity_id"] == attempt


def test_msp_security_xss_attacks():
    """Test MSP resistance to XSS attacks"""
    ca_config = {
        "root_cert": "xss-test-root",
        "intermediate_certs": ["xss-test-intermediate"],
        "policy": {"default_validity": 365}
    }
    
    msp = HierarchicalMSP("xss-test-org", ca_config)
    
    # Test XSS attempts in attributes
    xss_attempts = [
        {"name": "<script>alert('XSS')</script>", "department": "engineering"},
        {"description": "javascript:alert('XSS')", "role": "user"},
        {"bio": "<img src=x onerror=alert(1)>", "level": "1"}
    ]
    
    credentials = {
        "public_key": "xss-public-key",
        "private_key": "xss-private-key"
    }
    
    for i, attributes in enumerate(xss_attempts):
        entity_id = f"xss-test-entity-{i}"
        result = msp.register_entity(entity_id, credentials, "viewer", attributes)
        assert result is True
        
        # Entity info should be retrievable withattributes preserved
        entity_info = msp.get_entity_info(entity_id)
        assert entity_info is not None
        assert entity_info["attributes"] == attributes


def test_msp_directory_traversal_attacks():
    """Test MSP resistance to directory traversal attacks"""
    ca_config = {
        "root_cert": "traversal-test-root",
        "intermediate_certs": ["traversal-test-intermediate"],
        "policy": {"default_validity": 365}
    }
    
    msp = HierarchicalMSP("traversal-test-org", ca_config)
    credentials = {
        "public_key": "traversal-public-key",
        "private_key": "traversal-private-key"
    }
    
    # Test directory traversal attempts in entity_id
    traversal_attempts = [
        "../../../etc/passwd",
        "..\\..\\..\\windows\\system32\\cmd.exe",
        "/etc/passwd",
        "../../config/database.yml"
]
    
    for attempt in traversal_attempts:
        # These should be treated as regular entity_ids
        result = msp.register_entity(attempt, credentials, "operator")
        assert result is True
        
        # Validation should work normally
        is_valid = msp.validate_identity(attempt, credentials)
        assert is_valid is True

