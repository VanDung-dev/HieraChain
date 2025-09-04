"""
Certificate Management Utilities for Hierarchical Blockchain Framework.

This module provides certificate management utilities that support the advanced MSP 
implementation and enhance enterprise security capabilities. It includes certificate 
validation, chain verification, and certificate lifecycle management for enterprise 
blockchain deployments.
"""

import time
import hashlib
import base64
import json
from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timezone
import re


class CertificateType(Enum):
    """Certificate type enumeration"""
    ROOT_CA = "root_ca"
    INTERMEDIATE_CA = "intermediate_ca"
    END_ENTITY = "end_entity"
    TLS_SERVER = "tls_server"
    TLS_CLIENT = "tls_client"


class CertificateValidationError(Exception):
    """Certificate validation error"""
    pass


@dataclass
class CertificateInfo:
    """Certificate information structure"""
    serial_number: str
    subject: str
    issuer: str
    valid_from: datetime
    valid_until: datetime
    public_key: str
    signature: str
    certificate_type: CertificateType
    key_usage: List[str]
    subject_alt_names: List[str]
    
    def is_expired(self) -> bool:
        """Check if certificate is expired"""
        return datetime.now(timezone.utc) > self.valid_until
    
    def is_valid_now(self) -> bool:
        """Check if certificate is currently valid"""
        now = datetime.now(timezone.utc)
        return self.valid_from <= now <= self.valid_until
    
    def days_until_expiry(self) -> int:
        """Get number of days until certificate expires"""
        if self.is_expired():
            return 0
        delta = self.valid_until - datetime.now(timezone.utc)
        return delta.days
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "serial_number": self.serial_number,
            "subject": self.subject,
            "issuer": self.issuer,
            "valid_from": self.valid_from.isoformat(),
            "valid_until": self.valid_until.isoformat(),
            "public_key": self.public_key,
            "signature": self.signature,
            "certificate_type": self.certificate_type.value,
            "key_usage": self.key_usage,
            "subject_alt_names": self.subject_alt_names,
            "is_expired": self.is_expired(),
            "days_until_expiry": self.days_until_expiry()
        }


class CertificateRevocationList:
    """Certificate Revocation List management"""
    
    def __init__(self):
        self.revoked_certificates: Dict[str, Dict[str, Any]] = {}
        self.last_updated = time.time()
        self.version = 1
        
    def revoke_certificate(self, serial_number: str, reason: str = "unspecified",
                         revocation_date: Optional[datetime] = None) -> None:
        """
        Revoke a certificate.
        
        Args:
            serial_number: Certificate serial number
            reason: Revocation reason
            revocation_date: Date of revocation (defaults to now)
        """
        self.revoked_certificates[serial_number] = {
            "serial_number": serial_number,
            "reason": reason,
            "revocation_date": revocation_date or datetime.now(timezone.utc),
            "added_to_crl": time.time()
        }
        
        self.last_updated = time.time()
        self.version += 1
    
    def is_revoked(self, serial_number: str) -> bool:
        """Check if certificate is revoked"""
        return serial_number in self.revoked_certificates
    
    def get_revocation_info(self, serial_number: str) -> Optional[Dict[str, Any]]:
        """Get revocation information for a certificate"""
        return self.revoked_certificates.get(serial_number)
    
    def get_crl_info(self) -> Dict[str, Any]:
        """Get CRL information"""
        return {
            "version": self.version,
            "last_updated": self.last_updated,
            "revoked_count": len(self.revoked_certificates),
            "revoked_certificates": list(self.revoked_certificates.keys())
        }


class CertificateValidator:
    """Certificate validation utilities"""
    
    def __init__(self):
        self.trusted_cas: Dict[str, CertificateInfo] = {}
        self.crl = CertificateRevocationList()
        
    def add_trusted_ca(self, ca_cert: CertificateInfo) -> None:
        """Add trusted CA certificate"""
        self.trusted_cas[ca_cert.subject] = ca_cert
    
    def remove_trusted_ca(self, subject: str) -> bool:
        """Remove trusted CA certificate"""
        if subject in self.trusted_cas:
            del self.trusted_cas[subject]
            return True
        return False
    
    def validate_certificate(self, cert: CertificateInfo) -> Dict[str, Any]:
        """
        Validate certificate against trusted CAs and policies.
        
        Args:
            cert: Certificate to validate
            
        Returns:
            Validation result with details
        """
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "certificate": cert.subject,
            "validated_at": time.time()
        }
        
        # Check certificate expiry
        if cert.is_expired():
            validation_result["valid"] = False
            validation_result["errors"].append("Certificate has expired")
        elif cert.days_until_expiry() <= 30:
            validation_result["warnings"].append(
                f"Certificate expires in {cert.days_until_expiry()} days"
            )
        
        # Check if certificate is revoked
        if self.crl.is_revoked(cert.serial_number):
            validation_result["valid"] = False
            validation_result["errors"].append("Certificate has been revoked")
            revocation_info = self.crl.get_revocation_info(cert.serial_number)
            validation_result["revocation_info"] = revocation_info
        
        # Validate certificate chain
        chain_validation = self.validate_certificate_chain(cert)
        if not chain_validation["valid"]:
            validation_result["valid"] = False
            validation_result["errors"].extend(chain_validation["errors"])
        
        validation_result["warnings"].extend(chain_validation.get("warnings", []))
        
        # Validate key usage
        key_usage_validation = self._validate_key_usage(cert)
        if not key_usage_validation["valid"]:
            validation_result["warnings"].extend(key_usage_validation["warnings"])
        
        return validation_result
    
    def validate_certificate_chain(self, cert: CertificateInfo) -> Dict[str, Any]:
        """
        Validate certificate chain to trusted root CA.
        
        Args:
            cert: Certificate to validate chain for
            
        Returns:
            Chain validation result
        """
        chain_result = {
            "valid": False,
            "errors": [],
            "warnings": [],
            "chain_length": 0,
            "trust_anchor": None
        }
        
        current_cert = cert
        chain_length = 0
        visited_subjects = set()
        
        while current_cert and chain_length < 10:  # Prevent infinite loops
            chain_length += 1
            
            # Check for circular chains
            if current_cert.subject in visited_subjects:
                chain_result["errors"].append("Circular certificate chain detected")
                return chain_result
            
            visited_subjects.add(current_cert.subject)
            
            # Check if this is a self-signed root CA
            if current_cert.subject == current_cert.issuer:
                if current_cert.subject in self.trusted_cas:
                    chain_result["valid"] = True
                    chain_result["trust_anchor"] = current_cert.subject
                    chain_result["chain_length"] = chain_length
                    return chain_result
                else:
                    chain_result["errors"].append(
                        f"Self-signed certificate {current_cert.subject} is not in trusted CA list"
                    )
                    return chain_result
            
            # Look for issuer certificate
            issuer_cert = self.trusted_cas.get(current_cert.issuer)
            if not issuer_cert:
                chain_result["errors"].append(
                    f"Issuer certificate not found: {current_cert.issuer}"
                )
                return chain_result
            
            # Validate issuer certificate
            if issuer_cert.is_expired():
                chain_result["errors"].append(
                    f"Issuer certificate has expired: {current_cert.issuer}"
                )
                return chain_result
            
            # Move up the chain
            current_cert = issuer_cert
        
        if chain_length >= 10:
            chain_result["errors"].append("Certificate chain too long (>10)")
        
        return chain_result
    
    def _validate_key_usage(self, cert: CertificateInfo) -> Dict[str, Any]:
        """Validate certificate key usage"""
        result = {
            "valid": True,
            "warnings": []
        }
        
        # Check if key usage is appropriate for certificate type
        if cert.certificate_type == CertificateType.ROOT_CA:
            required_usage = ["keyCertSign", "cRLSign"]
            if not all(usage in cert.key_usage for usage in required_usage):
                result["warnings"].append(
                    "Root CA certificate missing required key usage extensions"
                )
        
        elif cert.certificate_type == CertificateType.INTERMEDIATE_CA:
            required_usage = ["keyCertSign"]
            if not all(usage in cert.key_usage for usage in required_usage):
                result["warnings"].append(
                    "Intermediate CA certificate missing required key usage extensions"
                )
        
        elif cert.certificate_type == CertificateType.TLS_SERVER:
            required_usage = ["keyEncipherment", "digitalSignature"]
            if not any(usage in cert.key_usage for usage in required_usage):
                result["warnings"].append(
                    "TLS server certificate missing required key usage extensions"
                )
        
        return result


class CertificateManager:
    """
    Certificate management utilities for enterprise blockchain applications.
    
    Provides comprehensive certificate lifecycle management, validation, and 
    chain verification capabilities for the hierarchical blockchain framework.
    """
    
    def __init__(self):
        self.certificates: Dict[str, CertificateInfo] = {}
        self.validator = CertificateValidator()
        self.certificate_store: Dict[str, Dict[str, Any]] = {}
        
        # Certificate templates for different types
        self.certificate_templates = self._init_certificate_templates()
        
        # Statistics
        self.statistics = {
            "total_certificates": 0,
            "active_certificates": 0,
            "expired_certificates": 0,
            "revoked_certificates": 0,
            "certificates_by_type": {}
        }
    
    def parse_certificate_data(self, cert_data: str) -> CertificateInfo:
        """
        Parse certificate data (simulated X.509 parsing).
        
        Note: This is a simplified implementation. In production, you would 
        use a proper X.509 certificate parsing library like cryptography.
        
        Args:
            cert_data: Certificate data string
            
        Returns:
            Parsed certificate information
        """
        # This is a simplified parser for demonstration
        # In production, use proper X.509 parsing
        
        # Extract basic information from cert_data
        # This would typically involve ASN.1 parsing
        
        lines = cert_data.strip().split('\n')
        cert_info = {}
        
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                cert_info[key.strip()] = value.strip()
        
        # Create CertificateInfo object
        return CertificateInfo(
            serial_number=cert_info.get("Serial", self._generate_serial()),
            subject=cert_info.get("Subject", "Unknown"),
            issuer=cert_info.get("Issuer", "Unknown"),
            valid_from=self._parse_date(cert_info.get("ValidFrom", "")),
            valid_until=self._parse_date(cert_info.get("ValidUntil", "")),
            public_key=cert_info.get("PublicKey", ""),
            signature=cert_info.get("Signature", ""),
            certificate_type=CertificateType(cert_info.get("Type", "end_entity")),
            key_usage=cert_info.get("KeyUsage", "").split(','),
            subject_alt_names=cert_info.get("SubjectAltNames", "").split(',')
        )
    
    def store_certificate(self, cert: CertificateInfo, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Store certificate with metadata.
        
        Args:
            cert: Certificate to store
            metadata: Additional metadata
            
        Returns:
            Certificate storage ID
        """
        storage_id = f"{cert.subject}:{cert.serial_number}"
        
        self.certificates[storage_id] = cert
        self.certificate_store[storage_id] = {
            "certificate": cert,
            "metadata": metadata or {},
            "stored_at": time.time(),
            "access_count": 0,
            "last_accessed": None
        }
        
        # Update statistics
        self._update_statistics()
        
        return storage_id
    
    def get_certificate(self, storage_id: str) -> Optional[CertificateInfo]:
        """Get certificate by storage ID"""
        if storage_id in self.certificate_store:
            entry = self.certificate_store[storage_id]
            entry["access_count"] += 1
            entry["last_accessed"] = time.time()
            return entry["certificate"]
        return None
    
    def validate_certificate_by_id(self, storage_id: str) -> Optional[Dict[str, Any]]:
        """Validate certificate by storage ID"""
        cert = self.get_certificate(storage_id)
        if cert:
            return self.validator.validate_certificate(cert)
        return None
    
    def get_certificates_by_subject(self, subject: str) -> List[CertificateInfo]:
        """Get all certificates for a subject"""
        matching_certs = []
        for storage_id, entry in self.certificate_store.items():
            if entry["certificate"].subject == subject:
                matching_certs.append(entry["certificate"])
        return matching_certs
    
    def get_expiring_certificates(self, days_threshold: int = 30) -> List[CertificateInfo]:
        """Get certificates expiring within threshold"""
        expiring_certs = []
        for entry in self.certificate_store.values():
            cert = entry["certificate"]
            if not cert.is_expired() and cert.days_until_expiry() <= days_threshold:
                expiring_certs.append(cert)
        return expiring_certs
    
    def revoke_certificate(self, storage_id: str, reason: str = "unspecified") -> bool:
        """Revoke a certificate"""
        cert = self.get_certificate(storage_id)
        if cert:
            self.validator.crl.revoke_certificate(cert.serial_number, reason)
            
            # Update metadata
            if storage_id in self.certificate_store:
                self.certificate_store[storage_id]["metadata"]["revoked"] = True
                self.certificate_store[storage_id]["metadata"]["revocation_reason"] = reason
                self.certificate_store[storage_id]["metadata"]["revoked_at"] = time.time()
            
            self._update_statistics()
            return True
        return False
    
    def cleanup_expired_certificates(self) -> int:
        """Remove expired certificates from storage"""
        expired_ids = []
        
        for storage_id, entry in self.certificate_store.items():
            if entry["certificate"].is_expired():
                expired_ids.append(storage_id)
        
        # Remove expired certificates
        for storage_id in expired_ids:
            del self.certificate_store[storage_id]
            if storage_id in self.certificates:
                del self.certificates[storage_id]
        
        self._update_statistics()
        return len(expired_ids)
    
    def get_certificate_statistics(self) -> Dict[str, Any]:
        """Get certificate management statistics"""
        self._update_statistics()
        return self.statistics.copy()
    
    def export_certificate_info(self, storage_id: str) -> Optional[Dict[str, Any]]:
        """Export comprehensive certificate information"""
        if storage_id not in self.certificate_store:
            return None
            
        entry = self.certificate_store[storage_id]
        cert = entry["certificate"]
        
        return {
            "storage_id": storage_id,
            "certificate_info": cert.to_dict(),
            "metadata": entry["metadata"],
            "storage_info": {
                "stored_at": entry["stored_at"],
                "access_count": entry["access_count"],
                "last_accessed": entry["last_accessed"]
            },
            "validation_result": self.validator.validate_certificate(cert)
        }
    
    def _generate_serial(self) -> str:
        """Generate certificate serial number"""
        return hashlib.sha256(str(time.time()).encode()).hexdigest()[:16]
    
    def _parse_date(self, date_str: str) -> datetime:
        """Parse date string to datetime"""
        if not date_str:
            return datetime.now(timezone.utc)
        
        try:
            # Try multiple date formats
            formats = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
                "%Y/%m/%d %H:%M:%S",
                "%Y/%m/%d"
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
            
            # If all formats fail, return current time
            return datetime.now(timezone.utc)
            
        except Exception:
            return datetime.now(timezone.utc)
    
    def _init_certificate_templates(self) -> Dict[str, Dict[str, Any]]:
        """Initialize certificate templates"""
        return {
            "root_ca": {
                "key_usage": ["keyCertSign", "cRLSign"],
                "basic_constraints": "CA:TRUE",
                "validity_years": 10
            },
            "intermediate_ca": {
                "key_usage": ["keyCertSign", "cRLSign"],
                "basic_constraints": "CA:TRUE, pathlen:0",
                "validity_years": 5
            },
            "end_entity": {
                "key_usage": ["digitalSignature", "keyEncipherment"],
                "basic_constraints": "CA:FALSE",
                "validity_years": 1
            },
            "tls_server": {
                "key_usage": ["digitalSignature", "keyEncipherment"],
                "extended_key_usage": ["serverAuth"],
                "basic_constraints": "CA:FALSE",
                "validity_years": 1
            }
        }
    
    def _update_statistics(self) -> None:
        """Update certificate statistics"""
        total_certs = len(self.certificate_store)
        active_certs = 0
        expired_certs = 0
        revoked_certs = 0
        by_type = {}
        
        for entry in self.certificate_store.values():
            cert = entry["certificate"]
            
            if cert.is_expired():
                expired_certs += 1
            elif self.validator.crl.is_revoked(cert.serial_number):
                revoked_certs += 1
            else:
                active_certs += 1
            
            cert_type = cert.certificate_type.value
            by_type[cert_type] = by_type.get(cert_type, 0) + 1
        
        self.statistics = {
            "total_certificates": total_certs,
            "active_certificates": active_certs,
            "expired_certificates": expired_certs,
            "revoked_certificates": revoked_certs,
            "certificates_by_type": by_type
        }
    
    def __str__(self) -> str:
        """String representation"""
        return f"CertificateManager(certificates={len(self.certificates)})"
    
    def __repr__(self) -> str:
        """Detailed string representation"""
        return (f"CertificateManager(total={len(self.certificates)}, "
                f"active={self.statistics.get('active_certificates', 0)})")