"""
Advanced Membership Service Provider (MSP) for HieraChain Framework.

This module implements enterprise-grade identity management with hierarchical certificate 
management, role-based access control, and attribute-based policies for large-scale 
business applications.
"""

import time
import hashlib
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass
from enum import Enum


class CertificateStatus(Enum):
    """Certificate status enumeration"""
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
    SUSPENDED = "suspended"


@dataclass
class Certificate:
    """Certificate data structure"""
    cert_id: str
    subject: str
    issuer: str
    public_key: str
    valid_from: float
    valid_until: float
    status: CertificateStatus
    attributes: Dict[str, Any]
    signature: str
    
    def is_valid(self) -> bool:
        """Check if certificate is currently valid"""
        current_time = time.time()
        return (
            self.status == CertificateStatus.ACTIVE and
            self.valid_from <= current_time <= self.valid_until
        )

    def is_expired(self) -> bool:
        """Check if certificate has expired"""
        return time.time() > self.valid_until

class CertificateAuthority:
    """Hierarchical Certificate Authority for enterprise environments"""
    
    def __init__(self, root_cert: str, intermediate_certs: List[str], policy: Dict[str, Any]):
        """
        Initialize Certificate Authority.
        
        Args:
            root_cert: Root certificate for the CA hierarchy
            intermediate_certs: List of intermediate certificates
            policy: CA policy configuration
        """
        self.root_cert = root_cert
        self.intermediate_certs = intermediate_certs
        self.policy = policy
        self.issued_certificates: Dict[str, Certificate] = {}
        self.revoked_certificates: Set[str] = set()
        
    def issue_certificate(self, subject: str, public_key: str, 
                         attributes: Dict[str, Any], valid_days: int = 365) -> Certificate:
        """
        Issue a new certificate for an entity.
        
        Args:
            subject: Certificate subject identifier
            public_key: Entity's public key
            attributes: Certificate attributes
            valid_days: Certificate validity period in days
            
        Returns:
            Issued certificate
        """
        cert_id = self._generate_cert_id(subject, public_key)
        current_time = time.time()
        valid_until = current_time + (valid_days * 24 * 60 * 60)
        
        certificate = Certificate(
            cert_id=cert_id,
            subject=subject,
            issuer=self.root_cert,
            public_key=public_key,
            valid_from=current_time,
            valid_until=valid_until,
            status=CertificateStatus.ACTIVE,
            attributes=attributes,
            signature=self._sign_certificate(cert_id, subject, public_key)
        )
        
        self.issued_certificates[cert_id] = certificate
        return certificate
    
    def revoke_certificate(self, cert_id: str, _reason: str = "unspecified") -> bool:
        """
        Revoke a certificate.
        
        Args:
            cert_id: Certificate ID to revoke
            _reason: Revocation reason
            
        Returns:
            True if successfully revoked
        """
        if cert_id in self.issued_certificates:
            self.issued_certificates[cert_id].status = CertificateStatus.REVOKED
            self.revoked_certificates.add(cert_id)
            return True
        return False
    
    def verify_certificate(self, cert_id: str) -> bool:
        """
        Verify certificate validity and status.
        
        Args:
            cert_id: Certificate ID to verify
            
        Returns:
            True if certificate is valid and not revoked
        """
        if cert_id in self.revoked_certificates:
            return False
            
        certificate = self.issued_certificates.get(cert_id)
        if not certificate:
            return False
            
        return certificate.is_valid()
    
    @staticmethod
    def _generate_cert_id(subject: str, public_key: str) -> str:
        """Generate unique certificate ID"""
        data = f"{subject}:{public_key}:{time.time()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    @staticmethod
    def _sign_certificate(cert_id: str, subject: str, public_key: str) -> str:
        """Generate certificate signature"""
        data = f"{cert_id}:{subject}:{public_key}"
        return hashlib.sha256(data.encode()).hexdigest()


class OrganizationPolicies:
    """Organization policy management"""
    
    def __init__(self):
        self.policies: Dict[str, Dict[str, Any]] = {}
        self.role_permissions: Dict[str, List[str]] = {}
    
    def define_policy(self, policy_id: str, policy_config: Dict[str, Any]) -> None:
        """Define a new organizational policy"""
        self.policies[policy_id] = {
            "config": policy_config,
            "created_at": time.time(),
            "version": "1.0"
        }
    
    def evaluate_policy(self, policy_id: str, context: Dict[str, Any]) -> bool:
        """Evaluate policy against given context"""
        if policy_id not in self.policies:
            return False
            
        policy = self.policies[policy_id]
        # Simplified policy evaluation - can be extended
        required_attributes = policy["config"].get("required_attributes", [])
        
        for attr in required_attributes:
            if attr not in context:
                return False
                
        return True
    
    def assign_role_permissions(self, role: str, permissions: List[str]) -> None:
        """Assign permissions to a role"""
        self.role_permissions[role] = permissions
    
    def check_permission(self, role: str, permission: str) -> bool:
        """Check if role has specific permission"""
        return permission in self.role_permissions.get(role, [])


class HierarchicalMSP:
    """
    Enterprise-grade Membership Service Provider with hierarchical certificate management.
    
    This class provides comprehensive identity management for enterprise blockchain applications,
    including certificate management, role-based access control, and audit logging.
    """
    
    def __init__(self, organization_id: str, ca_config: Dict[str, Any]):
        """
        Initialize Hierarchical MSP.
        
        Args:
            organization_id: Unique enterprise organization identifier
            ca_config: Certificate authority configuration with hierarchical trust chains
        """
        self.organization_id = organization_id
        self.ca = CertificateAuthority(
            root_cert=ca_config["root_cert"],
            intermediate_certs=ca_config.get("intermediate_certs", []),
            policy=ca_config.get("policy", {})
        )
        self.roles: Dict[str, Dict[str, Any]] = {}
        self.policies = OrganizationPolicies()
        self.audit_log: List[Dict[str, Any]] = []
        self.entities: Dict[str, Dict[str, Any]] = {}
        
        # Initialize default roles
        self._initialize_default_roles()
        
    def register_entity(self, entity_id: str, credentials: Dict[str, Any], 
                       role: str, attributes: Optional[Dict[str, Any]] = None) -> bool:
        """
        Register entity with role-based access control and attribute-based policies.
        
        Args:
            entity_id: Unique entity identifier
            credentials: Entity credentials including public key
            role: Entity role in the organization
            attributes: Optional additional attributes
            
        Returns:
            True if registration successful
        """
        try:
            # Validate role exists
            if role not in self.roles:
                raise ValueError(f"Role {role} not defined in organization")
            
            # Issue certificate for the entity
            certificate = self.ca.issue_certificate(
                subject=entity_id,
                public_key=credentials["public_key"],
                attributes=attributes or {},
                valid_days=self.roles[role].get("cert_validity_days", 365)
            )
            
            # Register entity
            self.entities[entity_id] = {
                "certificate": certificate,
                "role": role,
                "attributes": attributes or {},
                "credentials": credentials,
                "registered_at": time.time(),
                "last_activity": time.time(),
                "status": "active"
            }
            
            # Log the registration
            self._log_event("entity_registered", {
                "entity_id": entity_id,
                "role": role,
                "certificate_id": certificate.cert_id
            })
            
            return True
            
        except Exception as e:
            self._log_event("entity_registration_failed", {
                "entity_id": entity_id,
                "error": str(e)
            })
            return False

    def validate_identity(self, entity_id: str, credentials: Dict[str, Any]) -> bool:
        """
        Validate entity identity and credentials.

        Args:
            entity_id: Entity identifier to validate
            credentials: Credentials to verify
            
        Returns:
            True if identity is valid
        """
        if entity_id not in self.entities:
            return False

        if credentials is None:
            return False

        entity = self.entities[entity_id]

        # Check certificate validity
        certificate = entity["certificate"]
        if not self.ca.verify_certificate(certificate.cert_id):
            return False

        # Verify credentials
        if entity["credentials"]["public_key"] != credentials.get("public_key"):
            return False

        # Update last activity
        entity["last_activity"] = time.time()

        self._log_event("identity_validated", {"entity_id": entity_id})
        return True
    
    def authorize_action(self, entity_id: str, action: str, resource: str = None) -> bool:
        """
        Authorize entity action based on role and policies.
        
        Args:
            entity_id: Entity requesting authorization
            action: Action to be performed
            resource: Optional resource being accessed
            
        Returns:
            True if action is authorized
        """
        if entity_id not in self.entities:
            return False
            
        entity = self.entities[entity_id]
        role = entity["role"]
        
        # Check role permissions
        if not self.policies.check_permission(role, action):
            return False
        
        # Evaluate additional policies if needed
        policy_context = {
            "entity_id": entity_id,
            "role": role,
            "action": action,
            "resource": resource,
            "attributes": entity["attributes"]
        }
        
        # Apply organization-specific policies
        for policy_id in self.roles[role].get("policies", []):
            if not self.policies.evaluate_policy(policy_id, policy_context):
                return False
        
        self._log_event("action_authorized", {
            "entity_id": entity_id,
            "action": action,
            "resource": resource
        })
        
        return True
    
    def revoke_entity(self, entity_id: str, reason: str = "administrative") -> bool:
        """
        Revoke entity access.
        
        Args:
            entity_id: Entity to revoke
            reason: Revocation reason
            
        Returns:
            True if successfully revoked
        """
        if entity_id not in self.entities:
            return False
            
        entity = self.entities[entity_id]
        certificate = entity["certificate"]
        
        # Revoke certificate
        self.ca.revoke_certificate(certificate.cert_id, reason)
        
        # Update entity status
        entity["status"] = "revoked"
        entity["revoked_at"] = time.time()
        entity["revocation_reason"] = reason
        
        self._log_event("entity_revoked", {
            "entity_id": entity_id,
            "reason": reason
        })
        
        return True
    
    def define_role(self, role_name: str, permissions: List[str], 
                   policies: List[str] = None, cert_validity_days: int = 365) -> None:
        """
        Define a new organizational role.
        
        Args:
            role_name: Name of the role
            permissions: List of permissions for this role
            policies: List of policy IDs to apply
            cert_validity_days: Certificate validity period for this role
        """
        self.roles[role_name] = {
            "permissions": permissions,
            "policies": policies or [],
            "cert_validity_days": cert_validity_days,
            "created_at": time.time()
        }
        
        # Assign permissions to role in policy engine
        self.policies.assign_role_permissions(role_name, permissions)
        
        self._log_event("role_defined", {
            "role_name": role_name,
            "permissions": permissions
        })
    
    def get_entity_info(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about an entity"""
        if entity_id not in self.entities:
            return None
            
        entity = self.entities[entity_id]
        return {
            "entity_id": entity_id,
            "role": entity["role"],
            "status": entity["status"],
            "registered_at": entity["registered_at"],
            "last_activity": entity["last_activity"],
            "certificate_valid": self.ca.verify_certificate(entity["certificate"].cert_id),
            "attributes": entity["attributes"]
        }
    
    def get_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent audit log entries"""
        return self.audit_log[-limit:] if limit > 0 else self.audit_log
    
    def _initialize_default_roles(self) -> None:
        """Initialize default organizational roles"""
        default_roles = {
            "admin": {
                "permissions": [
                    "manage_entities", "view_audit_log", "define_policies",
                    "create_channels", "manage_certificates", "submit_events", 
                    "view_channels", "query_data", "view_data"
                ],
                "policies": [],
                "cert_validity_days": 365
            },
            "operator": {
                "permissions": [
                    "submit_events", "view_channels", "query_data"
                ],
                "policies": [],
                "cert_validity_days": 180
            },
            "viewer": {
                "permissions": ["view_data", "query_data"],
                "policies": [],
                "cert_validity_days": 90
            }
        }
        
        for role_name, role_config in default_roles.items():
            self.roles[role_name] = {
                **role_config,
                "created_at": time.time()
            }
            self.policies.assign_role_permissions(role_name, role_config["permissions"])
    
    def _log_event(self, event_type: str, details: Dict[str, Any]) -> None:
        """Log an audit event"""
        self.audit_log.append({
            "timestamp": time.time(),
            "event_type": event_type,
            "organization_id": self.organization_id,
            "details": details
        })
    
    def __str__(self) -> str:
        """String representation of MSP"""
        return f"HierarchicalMSP(org={self.organization_id}, entities={len(self.entities)})"
    
    def __repr__(self) -> str:
        """Detailed string representation"""
        return (f"HierarchicalMSP(organization_id='{self.organization_id}', "
                f"entities={len(self.entities)}, roles={len(self.roles)})")