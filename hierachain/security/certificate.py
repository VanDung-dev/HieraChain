"""
Certificate Management Utilities for HieraChain Ledger.

Provides certificate validation, chain verification, and certificate
lifecycle management for enterprise blockchain deployments.
"""

from __future__ import annotations

import time
import hashlib
from typing import Any
from datetime import datetime, timezone

from hierachain.security.secure_logging import get_security_logger
from hierachain.security.certificate_types import (
    CertificateType,
    CertificateValidationError,
    CertificateInfo,
)

logger = get_security_logger()

__all__ = [
    "CertificateType",
    "CertificateValidationError",
    "CertificateInfo",
    "CertificateRevocationList",
    "CertificateValidator",
    "CertificateManager",
]


class CertificateRevocationList:
    def __init__(self):
        self.revoked_certificates: dict[str, dict[str, Any]] = {}
        self.last_updated = time.time()
        self.version = 1

    def revoke_certificate(self, serial_number: str, reason: str = "unspecified", revocation_date: datetime | None = None) -> None:
        self.revoked_certificates[serial_number] = {
            "serial_number": serial_number,
            "reason": reason,
            "revocation_date": revocation_date or datetime.now(timezone.utc),
            "added_to_crl": time.time(),
        }
        self.last_updated = time.time()
        self.version += 1

    def is_revoked(self, serial_number: str) -> bool:
        return serial_number in self.revoked_certificates

    def get_revocation_info(self, serial_number: str) -> dict[str, Any] | None:
        return self.revoked_certificates.get(serial_number)

    def get_crl_info(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "last_updated": self.last_updated,
            "revoked_count": len(self.revoked_certificates),
            "revoked_certificates": list(self.revoked_certificates.keys()),
        }


def _validate_key_usage(cert: CertificateInfo) -> dict[str, Any]:
    valid = True
    warnings: list[str] = []
    rules = {
        CertificateType.ROOT_CA: (["keyCertSign", "cRLSign"], all, "Root CA certificate missing required key usage extensions"),
        CertificateType.INTERMEDIATE_CA: (["keyCertSign"], all, "Intermediate CA certificate missing required key usage extensions"),
        CertificateType.TLS_SERVER: (["keyEncipherment", "digitalSignature"], any, "TLS server certificate missing required key usage extensions"),
    }
    rule = rules.get(cert.certificate_type)
    if not rule:
        return {"valid": valid, "warnings": warnings}
    required_usage, checker, warning_message = rule
    if not checker(usage in cert.key_usage for usage in required_usage):
        warnings.append(warning_message)
    return {"valid": valid, "warnings": warnings}


class CertificateValidator:
    def __init__(self):
        self.trusted_cas: dict[str, CertificateInfo] = {}
        self.crl = CertificateRevocationList()

    def add_trusted_ca(self, ca_cert: CertificateInfo) -> None:
        self.trusted_cas[ca_cert.subject] = ca_cert

    def remove_trusted_ca(self, subject: str) -> bool:
        if subject in self.trusted_cas:
            del self.trusted_cas[subject]
            return True
        return False

    def validate_certificate(self, cert: CertificateInfo) -> dict[str, Any]:
        valid = True
        errors: list[str] = []
        warnings: list[str] = []
        if cert.is_expired():
            valid = False
            errors.append("Certificate has expired")
        elif cert.days_until_expiry() <= 30:
            warnings.append(f"Certificate expires in {cert.days_until_expiry()} days")
        if self.crl.is_revoked(cert.serial_number):
            valid = False
            errors.append("Certificate has been revoked")
            revocation_info = self.crl.get_revocation_info(cert.serial_number)
            if revocation_info:
                errors.append(f"Revoked on: {revocation_info.get('revocation_date', 'Unknown date')}")
                errors.append(f"Reason: {revocation_info.get('reason', 'Unspecified')}")
        chain_validation = self.validate_certificate_chain(cert)
        if not chain_validation["valid"]:
            valid = False
            errors.extend(chain_validation.get("errors", []))
        warnings.extend(chain_validation.get("warnings", []))
        key_usage_validation = _validate_key_usage(cert)
        if not key_usage_validation["valid"]:
            warnings.extend(key_usage_validation.get("warnings", []))
        return {"valid": valid, "errors": errors, "warnings": warnings, "certificate": cert.subject, "validated_at": time.time()}

    def validate_certificate_chain(self, cert: CertificateInfo) -> dict[str, Any]:
        result = {"valid": False, "errors": [], "warnings": [], "chain_length": 0, "trust_anchor": ""}
        return self._recursive_validate_chain(cert, set(), result)

    def _recursive_validate_chain(self, cert: CertificateInfo, visited: set[str], result: dict[str, Any]) -> dict[str, Any]:
        result["chain_length"] += 1
        if result["chain_length"] > 10:
            result["errors"].append("Certificate chain too long (>10)")
            return result
        if cert.subject in visited:
            result["errors"].append("Circular certificate chain detected")
            return result
        visited.add(cert.subject)
        if cert.subject == cert.issuer:
            return self._finalize_root_validation(cert, result)
        issuer_cert = self.trusted_cas.get(cert.issuer)
        if not issuer_cert:
            result["errors"].append(f"Issuer certificate not found: {cert.issuer}")
            return result
        if issuer_cert.is_expired():
            result["errors"].append(f"Issuer certificate has expired: {cert.issuer}")
            return result
        return self._recursive_validate_chain(issuer_cert, visited, result)

    def _finalize_root_validation(self, cert: CertificateInfo, result: dict[str, Any]) -> dict[str, Any]:
        if cert.subject in self.trusted_cas:
            result["valid"] = True
            result["trust_anchor"] = cert.subject
        else:
            result["errors"].append(f"Self-signed certificate {cert.subject} is not in trusted CA list")
        return result


def _generate_serial() -> str:
    return hashlib.sha256(str(time.time()).encode()).hexdigest()[:16]


def _parse_date(date_str: str) -> datetime:
    if not date_str:
        return datetime.now(timezone.utc)
    try:
        formats = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return datetime.now(timezone.utc)
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)


def parse_certificate_data(cert_data: str) -> CertificateInfo:
    lines = cert_data.strip().split('\n')
    cert_info: dict[str, str] = {}
    for line in lines:
        if ':' in line:
            key, value = line.split(':', 1)
            cert_info[key.strip()] = value.strip()
    return CertificateInfo(
        serial_number=cert_info.get("Serial", _generate_serial()),
        subject=cert_info.get("Subject", "Unknown"),
        issuer=cert_info.get("Issuer", "Unknown"),
        valid_from=_parse_date(cert_info.get("ValidFrom", "")),
        valid_until=_parse_date(cert_info.get("ValidUntil", "")),
        public_key=cert_info.get("PublicKey", ""),
        signature=cert_info.get("Signature", ""),
        certificate_type=CertificateType(cert_info.get("Type", "end_entity")),
        key_usage=cert_info.get("KeyUsage", "").split(','),
        subject_alt_names=cert_info.get("SubjectAltNames", "").split(','),
    )


def _init_certificate_templates() -> dict[str, dict[str, Any]]:
    return {
        "root_ca": {"key_usage": ["keyCertSign", "cRLSign"], "basic_constraints": "CA:TRUE", "validity_years": 10},
        "intermediate_ca": {"key_usage": ["keyCertSign", "cRLSign"], "basic_constraints": "CA:TRUE, pathlen:0", "validity_years": 5},
        "end_entity": {"key_usage": ["digitalSignature", "keyEncipherment"], "basic_constraints": "CA:FALSE", "validity_years": 1},
        "tls_server": {"key_usage": ["digitalSignature", "keyEncipherment"], "extended_key_usage": ["serverAuth"], "basic_constraints": "CA:FALSE", "validity_years": 1},
    }


class CertificateManager:
    def __init__(self):
        self.certificates: dict[str, CertificateInfo] = {}
        self.validator = CertificateValidator()
        self.certificate_store: dict[str, dict[str, Any]] = {}
        self.certificate_templates = _init_certificate_templates()
        self.statistics = {"total_certificates": 0, "active_certificates": 0, "expired_certificates": 0, "revoked_certificates": 0, "certificates_by_type": {}}

    def store_certificate(self, cert: CertificateInfo, metadata: dict[str, Any] | None = None) -> str:
        storage_id = f"{cert.subject}:{cert.serial_number}"
        self.certificates[storage_id] = cert
        self.certificate_store[storage_id] = {"certificate": cert, "metadata": metadata or {}, "stored_at": time.time(), "access_count": 0, "last_accessed": None}
        self._update_statistics()
        return storage_id

    def get_certificate(self, storage_id: str) -> CertificateInfo | None:
        if storage_id in self.certificate_store:
            entry = self.certificate_store[storage_id]
            entry["access_count"] += 1
            entry["last_accessed"] = time.time()
            return entry["certificate"]
        return None

    def validate_certificate_by_id(self, storage_id: str) -> dict[str, Any] | None:
        cert = self.get_certificate(storage_id)
        return self.validator.validate_certificate(cert) if cert else None

    def get_certificates_by_subject(self, subject: str) -> list[CertificateInfo]:
        return [entry["certificate"] for entry in self.certificate_store.values() if entry["certificate"].subject == subject]

    def get_expiring_certificates(self, days_threshold: int = 30) -> list[CertificateInfo]:
        return [entry["certificate"] for entry in self.certificate_store.values() if not entry["certificate"].is_expired() and entry["certificate"].days_until_expiry() <= days_threshold]

    def revoke_certificate(self, storage_id: str, reason: str = "unspecified") -> bool:
        cert = self.get_certificate(storage_id)
        if cert:
            self.validator.crl.revoke_certificate(cert.serial_number, reason)
            if storage_id in self.certificate_store:
                self.certificate_store[storage_id]["metadata"]["revoked"] = True
                self.certificate_store[storage_id]["metadata"]["revocation_reason"] = reason
                self.certificate_store[storage_id]["metadata"]["revoked_at"] = time.time()
            self._update_statistics()
            return True
        return False

    def cleanup_expired_certificates(self) -> int:
        expired_ids = [sid for sid, entry in self.certificate_store.items() if entry["certificate"].is_expired()]
        for storage_id in expired_ids:
            del self.certificate_store[storage_id]
            if storage_id in self.certificates:
                del self.certificates[storage_id]
        self._update_statistics()
        return len(expired_ids)

    def get_certificate_statistics(self) -> dict[str, Any]:
        self._update_statistics()
        return self.statistics.copy()

    def export_certificate_info(self, storage_id: str) -> dict[str, Any] | None:
        if storage_id not in self.certificate_store:
            return None
        entry = self.certificate_store[storage_id]
        cert = entry["certificate"]
        return {
            "storage_id": storage_id,
            "certificate_info": cert.to_dict(),
            "metadata": entry["metadata"],
            "storage_info": {"stored_at": entry["stored_at"], "access_count": entry["access_count"], "last_accessed": entry["last_accessed"]},
            "validation_result": self.validator.validate_certificate(cert),
        }

    def _update_statistics(self) -> None:
        total_certs = len(self.certificate_store)
        active_certs = 0
        expired_certs = 0
        revoked_certs = 0
        by_type: dict[str, int] = {}
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
        self.statistics = {"total_certificates": total_certs, "active_certificates": active_certs, "expired_certificates": expired_certs, "revoked_certificates": revoked_certs, "certificates_by_type": by_type}

    def __str__(self) -> str:
        return f"CertificateManager(certificates={len(self.certificates)})"

    def __repr__(self) -> str:
        return f"CertificateManager(total={len(self.certificates)}, active={self.statistics.get('active_certificates', 0)})"
