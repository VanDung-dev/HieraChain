"""Certificate validation helpers for HieraChain Ledger."""

from __future__ import annotations

from typing import Any

from hierachain.error_mitigation.validator_exceptions import ValidationError, SecurityError


def validate_certificate(certificate: Any) -> None:
    if certificate.is_expired():
        raise SecurityError("Certificate validation failed: Certificate has expired")
