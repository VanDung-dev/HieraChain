"""
Unit tests for MSP (Membership Service Provider).

Tests the advanced MSP implementation including certificate management, 
role-based access control, and hierarchical identity management for enterprise applications.
"""

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
    def init_msp():
        msp, _, _ = setup_msp()
        return msp

    msp = init_msp()

    assert msp.organization_id == "test-org"
    assert msp.ca is not None
    assert msp.policies is not None
    assert len(msp.roles) > 0  # Should have default roles
    assert len(msp.audit_log) == 0  # Should start empty


def test_default_roles_initialization():
    """Test default roles are properly initialized"""
    def init_roles():
        msp, _, _ = setup_msp()
        return msp

    msp = init_roles()

    expected_roles = ["admin", "operator", "viewer"]
    
    for role in expected_roles:
        assert role in msp.roles
        assert len(msp.roles[role]["permissions"]) > 0
        assert "cert_validity_days" in msp.roles[role]


def test_register_entity_success():
    """Test successful entity registration"""
    msp, test_credentials, test_attributes = setup_msp()

    def register_entity():
        return msp.register_entity(
            "test-user-001",
            test_credentials,
            "admin",
            test_attributes
        )

    result = register_entity()

    assert result
    assert "test-user-001" in msp.entities
    
    entity = msp.entities["test-user-001"]
    assert entity["role"] == "admin"
    assert entity["status"] == "active"
    assert entity["attributes"] == test_attributes


def test_register_entity_invalid_role():
    """Test entity registration with invalid role"""
    msp, test_credentials, _ = setup_msp()

    def register_invalid_role():
        return msp.register_entity(
            "test-user-002",
            test_credentials,
            "invalid-role"
        )

    result = register_invalid_role()

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

    def validate_identity():
        return msp.validate_identity(
            "test-user-003",
            test_credentials
        )

    result = validate_identity()
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

    def validate_wrong_credentials():
        return msp.validate_identity(
            "test-user-004",
            wrong_credentials
        )

    result = validate_wrong_credentials()
    assert not result


def test_validate_identity_nonexistent_user():
    """Test identity validation for non-existent user"""
    msp, test_credentials, _ = setup_msp()

    def validate_nonexistent():
        return msp.validate_identity(
            "non-existent-user",
            test_credentials
        )

    result = validate_nonexistent()
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

    def authorize_admin_action():
        return msp.authorize_action(
            "test-admin",
            "manage_entities"
        )

    result = authorize_admin_action()
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

    def authorize_restricted_action():
        return msp.authorize_action(
            "test-viewer",
            "manage_entities"
        )

    result = authorize_restricted_action()
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

    def revoke_entity():
        return msp.revoke_entity("test-user-revoke", "security_breach")

    result = revoke_entity()
    assert result

    entity = msp.entities["test-user-revoke"]
    assert entity["status"] == "revoked"
    assert entity["revocation_reason"] == "security_breach"


def test_define_custom_role():
    """Test defining custom organizational role"""
    msp, _, _ = setup_msp()
    custom_permissions = ["custom_action_1", "custom_action_2"]

    def define_role():
        msp.define_role(
            "custom_role",
            custom_permissions,
            ["custom_policy"],
            180
        )

    define_role()

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

    def get_info():
        return msp.get_entity_info("test-info-user")

    info = get_info()

    assert info is not None
    assert info["entity_id"] == "test-info-user"
    assert info["role"] == "operator"
    assert info["status"] == "active"
    assert info["attributes"] == test_attributes


def test_get_entity_info_nonexistent():
    """Test getting info for non-existent entity"""
    msp, _, _ = setup_msp()

    def get_nonexistent_info():
        return msp.get_entity_info("non-existent")

    info = get_nonexistent_info()
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

    def get_audit_log():
        return msp.get_audit_log(10)

    audit_log = get_audit_log()
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
    def init_ca():
        return setup_ca()

    ca = init_ca()

    assert ca.root_cert == "test-root"
    assert len(ca.intermediate_certs) == 1
    assert len(ca.issued_certificates) == 0
    assert len(ca.revoked_certificates) == 0


def test_issue_certificate():
    """Test certificate issuance"""
    ca = setup_ca()

    def issue_cert():
        return ca.issue_certificate(
            subject="test-subject",
            public_key="test-public-key",
            attributes={"role": "admin"},
            valid_days=365
        )

    certificate = issue_cert()

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

    def revoke_cert():
        return ca.revoke_certificate(certificate.cert_id, "compromised")

    result = revoke_cert()

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

    def verify_cert():
        return ca.verify_certificate(certificate.cert_id)

    result = verify_cert()
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

    def verify_revoked_cert():
        return ca.verify_certificate(certificate.cert_id)

    result = verify_revoked_cert()
    assert not result


def test_verify_certificate_nonexistent():
    """Test verification of non-existent certificate"""
    ca = setup_ca()

    def verify_nonexistent_cert():
        return ca.verify_certificate("non-existent-cert-id")

    result = verify_nonexistent_cert()
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

    def define_policy():
        policies.define_policy("test_policy", policy_config)

    define_policy()

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

    def evaluate_policy():
        return policies.evaluate_policy("test_policy", context)

    result = evaluate_policy()
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

    def evaluate_policy_missing_attrs():
        return policies.evaluate_policy("test_policy", context)

    result = evaluate_policy_missing_attrs()
    assert not result


def test_evaluate_policy_nonexistent():
    """Test evaluation of non-existent policy"""
    policies = setup_policies()

    def evaluate_nonexistent_policy():
        return policies.evaluate_policy("non_existent", {})

    result = evaluate_nonexistent_policy()
    assert not result


def test_assign_role_permissions():
    """Test role permission assignment"""
    policies = setup_policies()
    permissions = ["read", "write", "execute"]

    def assign_permissions():
        policies.assign_role_permissions("test_role", permissions)

    assign_permissions()
    assert policies.role_permissions["test_role"] == permissions


def test_check_permission_success():
    """Test successful permission check"""
    policies = setup_policies()
    permissions = ["read", "write"]
    policies.assign_role_permissions("test_role", permissions)

    def check_perm_success():
        return policies.check_permission("test_role", "read")

    result = check_perm_success()
    assert result


def test_check_permission_denied():
    """Test denied permission check"""
    policies = setup_policies()
    permissions = ["read"]
    policies.assign_role_permissions("test_role", permissions)

    def check_perm_denied():
        return policies.check_permission("test_role", "write")

    result = check_perm_denied()
    assert not result


def test_check_permission_nonexistent_role():
    """Test permission check for non-existent role"""
    policies = setup_policies()

    def check_nonexistent_role():
        return policies.check_permission("non_existent_role", "read")

    result = check_nonexistent_role()
    assert not result


def test_register_entity_with_special_characters():
    """Test entity registration with special characters"""
    msp, test_credentials, _ = setup_msp()

    def register_special_chars():
        # Test with special characters in entity_id
        return msp.register_entity(
            "test-user@domain.com",
            test_credentials,
            "admin"
        )

    result = register_special_chars()

    assert result
    assert "test-user@domain.com" in msp.entities


def test_register_entity_with_invalid_role_edge_case():
    """Test entity registration with invalid role"""
    msp, test_credentials, _ = setup_msp()

    def register_invalid_role():
        # Test with invalid role
        return msp.register_entity(
            "test-invalid-role-user",
            test_credentials,
            "nonexistent_role"
        )

    result = register_invalid_role()

    assert not result
    assert "test-invalid-role-user" not in msp.entities


def test_validate_identity_with_invalid_inputs():
    """Test identity validation with invalid inputs"""
    msp, test_credentials, _ = setup_msp()
    
    # Register a valid entity first
    msp.register_entity("test-validate-user", test_credentials, "operator")

    def validate_all_cases():
        # Test with None entity_id
        result1 = msp.validate_identity(None, test_credentials)

        # Test with empty entity_id
        result2 = msp.validate_identity("", test_credentials)

        # Test with None credentials
        result3 = msp.validate_identity("test-validate-user", None)

        return result1, result2, result3

    result1, result2, result3 = validate_all_cases()

    assert not result1
    assert not result2
    assert not result3


def test_authorize_action_edge_cases():
    """Test authorization with edge cases"""
    msp, test_credentials, _ = setup_msp()
    
    # Register entity
    msp.register_entity("test-auth-user", test_credentials, "operator")

    def authorize_all_cases():
        # Test with empty action
        result1 = msp.authorize_action("test-auth-user", "")

        # Test with None action
        result2 = msp.authorize_action("test-auth-user", None)

        # Test with non-existent user
        result3 = msp.authorize_action("nonexistent_user", "view_data")

        return result1, result2, result3

    result1, result2, result3 = authorize_all_cases()

    assert not result1
    assert not result2
    assert not result3


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
    credentials = {
        "public_key": "integration-test-key",
        "private_key": "integration-test-private"
    }
    
    attributes = {
        "department": "security",
        "clearance": "high"
    }

    def full_lifecycle():
        msp = setup_integration_msp()

        # 1. Register entity
        register_result = msp.register_entity(
            "integration-user",
            credentials,
            "admin",
            attributes
        )

        # 2. Validate identity
        # For validation, we should only pass the public key, not the private key
        validation_credentials = {
            "public_key": credentials["public_key"]
        }
        validate_result = msp.validate_identity(
            "integration-user",
            validation_credentials
        )

        # 3. Authorize actions
        auth_result = msp.authorize_action(
            "integration-user",
            "manage_entities"
        )

        # 4. Get entity info
        info = msp.get_entity_info("integration-user")

        # 5. Revoke entity
        revoke_result = msp.revoke_entity(
            "integration-user",
            "end_of_employment"
        )

        # 6. Try to validate again (should still work even after revocation)
        validate_after_revoke = msp.validate_identity(
            "integration-user",
            validation_credentials
        )

        return register_result, validate_result, auth_result, info, revoke_result, validate_after_revoke

    results = full_lifecycle()
    register_result, validate_result, auth_result, info, revoke_result, validate_after_revoke = results

    assert register_result, "Entity registration failed"
    assert validate_result, "Identity validation failed after registration"
    assert auth_result, "Authorization failed for admin user"
    assert info is not None, "Failed to get entity info"
    assert info["role"] == "admin", "Entity role mismatch"
    assert revoke_result, "Entity revocation failed"


def test_role_based_access_control():
    """Test role-based access control integration"""
    msp = setup_integration_msp()
    admin_creds = {"public_key": "admin-key", "private_key": "admin-private"}
    viewer_creds = {"public_key": "viewer-key", "private_key": "viewer-private"}
    
    # Register admin and viewer
    msp.register_entity("test-admin", admin_creds, "admin")
    msp.register_entity("test-viewer", viewer_creds, "viewer")

    def test_rbac():
        # Test admin permissions
        admin_manage = msp.authorize_action("test-admin", "manage_entities")
        admin_view = msp.authorize_action("test-admin", "view_data")

        # Test viewer permissions
        viewer_manage = msp.authorize_action("test-viewer", "manage_entities")
        viewer_view = msp.authorize_action("test-viewer", "view_data")

        return (admin_manage, admin_view, viewer_manage, viewer_view)

    results = test_rbac()
    admin_manage, admin_view, viewer_manage, viewer_view = results

    assert admin_manage
    assert admin_view
    assert not viewer_manage
    assert viewer_view


def test_msp_registration_performance(benchmark=None):
    """Test performance of entity registration"""
    msp, test_credentials, test_attributes = setup_msp()
    

    def register_entities():
        # Register 100 entities
        for i in range(100):
            result = msp.register_entity(
                f"perf-test-user-{i}",
                test_credentials,
                "operator",
                test_attributes
            )
            assert result

    # Benchmark the registration of 100 entities
    if benchmark:
        benchmark(register_entities)
    else:
        register_entities()


def test_msp_validation_performance(benchmark=None):
    """Test performance of identity validation"""
    msp, test_credentials, _ = setup_msp()
    
    # Register test entities
    for i in range(100):
        msp.register_entity(
            f"val-perf-user-{i}",
            test_credentials,
            "operator"
        )

    def validate_entities():
        # Validate 100 entities
        for a in range(100):
            result = msp.validate_identity(
                f"val-perf-user-{a}",
                test_credentials
            )
            assert result

    # Benchmark the validation of 100 entities
    if benchmark:
        benchmark(validate_entities)
    else:
        validate_entities()


def test_msp_authorization_performance(benchmark=None):
    """Test performance of action authorization"""
    msp, test_credentials, _ = setup_msp()
    
    # Register test entities with admin role
    for i in range(100):
        msp.register_entity(
            f"auth-perf-user-{i}",
            test_credentials,
            "admin"
        )

    def authorize_entities():
        # Authorize 100 entities for various actions
        for a in range(100):
            result1 = msp.authorize_action(f"auth-perf-user-{a}", "manage_entities")
            result2 = msp.authorize_action(f"auth-perf-user-{a}", "view_data")
            assert result1
            assert result2

    # Benchmark the authorization of 100 entities for 2 actions each
    if benchmark:
        benchmark(authorize_entities)
    else:
        authorize_entities()


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

    def test_sql_injections():
        results = []
        for attempt in sql_injection_attempts:
            # These should be treated as regular entity_ids
            result = msp.register_entity(attempt, credentials, "operator")
            results.append(result)

            # Validation should work normally
            is_valid = msp.validate_identity(attempt, credentials)
            results.append(is_valid)

            # Entity info should be retrievable
            entity_info = msp.get_entity_info(attempt)
            results.append(entity_info is not None)
        return results

    results = test_sql_injections()

    # All operations should succeed
    for i in range(0, len(results), 3):
        assert results[i] is True    # Registration
        assert results[i+1] is True  # Validation
        assert results[i+2] is True  # Info retrieval


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

    def test_xss_attempts():
        results = []
        for a, attributes in enumerate(xss_attempts):
            entity_id = f"xss-test-entity-{a}"
            result = msp.register_entity(entity_id, credentials, "viewer", attributes)
            results.append(result)

            # Entity info should be retrievable withattributes preserved
            entity_info = msp.get_entity_info(entity_id)
            results.append(entity_info is not None)
            if entity_info:
                results.append(entity_info["attributes"] == attributes)
        return results

    results = test_xss_attempts()

    # All operations should succeed
    for i in range(0, len(results), 3):
        assert results[i] is True     # Registration
        assert results[i+1] is True   # Info retrieval
        assert results[i+2] is True   # Attributes preserved


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

    def test_traversal_attempts():
        results = []
        for attempt in traversal_attempts:
            # These should be treated as regular entity_ids
            result = msp.register_entity(attempt, credentials, "operator")
            results.append(result)

            # Validation should work normally
            is_valid = msp.validate_identity(attempt, credentials)
            results.append(is_valid)
        return results

    results = test_traversal_attempts()

    # All operations should succeed
    for i in range(0, len(results), 2):
        assert results[i] is True     # Registration
        assert results[i+1] is True   # Validation
