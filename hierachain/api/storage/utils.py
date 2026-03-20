"""
Utility functions for IPFS CID validation and data handling.

This module provides helper functions for working with IPFS CIDs,
detecting whether data is stored on-chain or off-chain, and
backward compatibility handling.
"""

import re
from typing import Any


# CID Patterns
CID_V0_PATTERN = re.compile(r'^Qm[1-9A-HJ-NP-Za-km-z]{44,}$')
CID_V1_PATTERN = re.compile(r'^b[a-z2-7]{58,}$')


def is_valid_cid(cid: str) -> bool:
    """
    Check if a string is a valid IPFS CID.

    Args:
        cid: String to check

    Returns:
        True if valid CID (v0 or v1), False otherwise

    Examples:
        >>> is_valid_cid("QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG")
        True
        >>> is_valid_cid("bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi")
        True
        >>> is_valid_cid("invalid_string")
        False
    """
    if not isinstance(cid, str):
        return False

    # Check CIDv0 (base58btc, starts with Qm)
    if CID_V0_PATTERN.match(cid):
        return True

    # Check CIDv1 (base32, starts with b)
    if CID_V1_PATTERN.match(cid):
        return True

    return False


def is_cid_string(value: Any) -> bool:
    """
    Check if a value is a string that looks like a CID.

    More lenient than is_valid_cid - just checks if it starts with
    typical CID prefixes. Useful for quick detection without full validation.

    Args:
        value: Value to check

    Returns:
        True if looks like a CID string

    Examples:
        >>> is_cid_string("QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG")
        True
        >>> is_cid_string({"data": "value"})
        False
    """
    if not isinstance(value, str):
        return False

    # Quick check for common CID prefixes
    return value.startswith('Qm') or value.startswith('b')


def detect_data_location(data: dict[str, Any], cid_field: str = "cid") -> str:
    """
    Detect whether data is stored on-chain or off-chain (IPFS).

    Args:
        data: Data dictionary to check
        cid_field: Name of the CID field (default: "cid")

    Returns:
        "offchain" if CID is present and valid
        "onchain" if data is inline
        "unknown" if unclear

    Examples:
        >>> detect_data_location({"details": {"key": "value"}})
        'onchain'
        >>> detect_data_location({"details_cid": "QmXx...", "details_nonce": "abc123"})
        'offchain'
    """
    # 1. Check for CID field
    if cid_field in data and is_cid_string(data[cid_field]):
        return "offchain"

    # 2. Check for common CID field patterns
    cid_fields = [k for k in data.keys() if k.endswith('_cid')]
    if cid_fields and any(is_cid_string(data[f]) for f in cid_fields):
        return "offchain"

    # Exclude CID-related fields and standard event metadata
    standard_fields = {
        'entity_id', 'event', 'timestamp', 'data',
        'creator_id', 'signature', 'index', 'hash', 'merkle_root'
    }
    data_fields = [
        k for k in data.keys()
        if k != cid_field
        and not k.endswith(('_cid', '_nonce', '_metadata'))
        and k not in standard_fields
    ]

    # If we have fields like 'details', 'value', or 'implementation' with actual data
    if any(data.get(f) for f in data_fields):
        return "onchain"

    return "unknown"


def extract_cid_info(data: dict[str, Any], prefix: str = "details") -> dict[str, Any] | None:
    """
    Extract CID-related information from a data dictionary.

    Args:
        data: Data dictionary
        prefix: Field prefix to look for (e.g., "details", "value", "implementation")

    Returns:
        Dict with cid, nonce, and metadata if found, None otherwise

    Examples:
        >>> extract_cid_info({
        ...     "details_cid": "QmXx...",
        ...     "details_nonce": "abc123",
        ...     "details_metadata": {"channel": "test"}
        ... })
        {'cid': 'QmXx...', 'nonce': 'abc123', 'metadata': {'channel': 'test'}}
    """
    cid_field = f"{prefix}_cid"
    nonce_field = f"{prefix}_nonce"
    metadata_field = f"{prefix}_metadata"

    cid = data.get(cid_field)
    if not cid or not is_cid_string(cid):
        return None

    return {
        "cid": cid,
        "nonce": data.get(nonce_field),
        "metadata": data.get(metadata_field)
    }


def normalize_data_field(
    data: dict[str, Any],
    field_name: str,
    prefer_offchain: bool = True
) -> tuple[Any | None, dict[str, Any] | None]:
    """
    Normalize a data field that can be either on-chain or off-chain.

    Args:
        data: Data dictionary
        field_name: Base field name (e.g., "details", "value", "implementation")
        prefer_offchain: If both on-chain and off-chain data exist, prefer off-chain

    Returns:
        Tuple of (inline_data, cid_info)
        - If on-chain: (data, None)
        - If off-chain: (None, {cid, nonce, metadata})

    Examples:
        >>> normalize_data_field({"details": {"key": "value"}}, "details")
        ({'key': 'value'}, None)
        >>> normalize_data_field({
        ...     "details_cid": "QmXx...",
        ...     "details_nonce": "abc"
        ... }, "details")
        (None, {'cid': 'QmXx...', 'nonce': 'abc', 'metadata': None})
    """
    # Extract CID info
    cid_info = extract_cid_info(data, field_name)

    # Extract inline data
    inline_data = data.get(field_name)

    # Determine what to return based on preference
    if prefer_offchain and cid_info:
        return None, cid_info
    elif inline_data:
        return inline_data, None
    elif cid_info:
        return None, cid_info
    else:
        return None, None


def build_cid_reference(
    cid: str,
    nonce: str,
    metadata: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Build a CID reference dictionary.

    Args:
        cid: IPFS CID
        nonce: Encryption nonce (hex string)
        metadata: Optional metadata used as AAD

    Returns:
        Dictionary with CID reference info

    Examples:
        >>> build_cid_reference("QmXx...", "abc123")
        {'cid': 'QmXx...', 'nonce': 'abc123', 'encrypted': True}
    """
    ref = {
        "cid": cid,
        "nonce": nonce,
        "encrypted": True
    }

    if metadata:
        ref["metadata"] = metadata

    return ref


def is_backward_compatible_data(data: dict[str, Any]) -> bool:
    """
    Check if data structure is backward compatible (has inline data).

    Args:
        data: Data dictionary to check

    Returns:
        True if contains inline data fields (backward compatible)

    Examples:
        >>> is_backward_compatible_data({"details": {"key": "value"}})
        True
        >>> is_backward_compatible_data({"details_cid": "QmXx..."})
        False
    """
    # Check for common data fields (not CID/nonce/metadata)
    data_fields = ['details', 'value', 'implementation', 'data', 'content']
    return any(field in data for field in data_fields)


def validate_nonce_format(nonce: str) -> bool:
    """
    Validate nonce format (should be 24 hex characters for AES-GCM).

    Args:
        nonce: Nonce string to validate

    Returns:
        True if valid format

    Examples:
        >>> validate_nonce_format("a1b2c3d4e5f6789012345678")
        True
        >>> validate_nonce_format("invalid")
        False
    """
    if not isinstance(nonce, str):
        return False

    # Should be 24 hex characters (12 bytes)
    if len(nonce) != 24:
        return False

    # Should be valid hex
    try:
        bytes.fromhex(nonce)
        return True
    except ValueError:
        return False


def format_cid_display(cid: str, max_length: int = 12) -> str:
    """
    Format CID for display (truncate long CIDs).

    Args:
        cid: Full CID
        max_length: Maximum length to show before truncation

    Returns:
        Formatted CID string

    Examples:
        >>> format_cid_display("QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG", 12)
        'QmYwAPJzv5CZ...dWEz79ojWnPbdG'
    """
    if len(cid) <= max_length * 2:
        return cid

    # Show start and end
    start = cid[:max_length]
    end = cid[-max_length:]
    return f"{start}...{end}"
