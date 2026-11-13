"""Operation-type validation shared by domain chain implementations."""

from typing import Any

_OPERATION_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "quality_check": ("check_type", "check_result"),
    "approval": ("approval_type", "approver_id"),
    "resource_allocation": ("resource_type", "resource_id"),
    "compliance_check": ("compliance_type",),
}


def validate_operation_data(
    operation_type: str, operation_data: dict[str, Any]
) -> bool:
    """Return True when *operation_data* has the fields required by *operation_type*."""
    required = _OPERATION_REQUIRED_FIELDS.get(operation_type)
    if required is None:
        return True
    return all(field in operation_data for field in required)
