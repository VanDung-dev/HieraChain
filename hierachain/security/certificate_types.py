"""
Certificate types for HieraChain Ledger.

Defines enums, exceptions, and dataclasses for certificate management.
"""

from typing import Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timezone


class CertificateType(Enum):
    ROOT_CA = "root_ca"
    INTERMEDIATE_CA = "intermediate_ca"
    END_ENTITY = "end_entity"
    TLS_SERVER = "tls_server"
    TLS_CLIENT = "tls_client"


class CertificateValidationError(Exception):
    pass


@dataclass
class CertificateInfo:
    serial_number: str
    subject: str
    issuer: str
    valid_from: datetime
    valid_until: datetime
    public_key: str
    signature: str
    certificate_type: CertificateType
    key_usage: list[str]
    subject_alt_names: list[str]

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.valid_until

    def is_valid_now(self) -> bool:
        now = datetime.now(timezone.utc)
        return self.valid_from <= now <= self.valid_until

    def days_until_expiry(self) -> int:
        if self.is_expired():
            return 0
        delta = self.valid_until - datetime.now(timezone.utc)
        return delta.days

    def to_dict(self) -> dict[str, Any]:
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
            "days_until_expiry": self.days_until_expiry(),
        }
