"""
MSP types for HieraChain Ledger.

Defines enums and dataclasses for Membership Service Provider.
"""

import time
from typing import Any
from dataclasses import dataclass
from enum import Enum


class CertificateStatus(Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
    SUSPENDED = "suspended"


@dataclass
class Certificate:
    cert_id: str
    subject: str
    issuer: str
    public_key: str
    valid_from: float
    valid_until: float
    status: CertificateStatus
    attributes: dict[str, Any]
    signature: str

    def is_valid(self) -> bool:
        current_time = time.time()
        return self.status == CertificateStatus.ACTIVE and self.valid_from <= current_time <= self.valid_until

    def is_expired(self) -> bool:
        return time.time() > self.valid_until
