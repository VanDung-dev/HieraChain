"""
Storage module for HieraChain API.

This module provides integration with distributed storage systems like IPFS
for off-chain data storage with encryption support.
"""

from .ipfs_client import IPFSClient, IPFSError, create_ipfs_client_from_env
from .encryption import AESEncryption, EncryptionError
from .utils import (
    is_valid_cid,
    is_cid_string,
    detect_data_location,
    extract_cid_info,
    normalize_data_field,
    build_cid_reference,
    is_backward_compatible_data,
    validate_nonce_format,
    format_cid_display
)
from .endpoint_helpers import (
    get_ipfs_client,
    is_ipfs_enabled,
    upload_to_ipfs_background,
    download_from_ipfs,
    process_event_details,
    process_private_data_value,
    process_contract_implementation,
    resolve_cid_field,
    resolve_event_details,
    resolve_multiple_events,
    close_ipfs_client
)

__all__ = [
    # IPFS Client
    "IPFSClient",
    "IPFSError",
    "create_ipfs_client_from_env",
    # Encryption
    "AESEncryption",
    "EncryptionError",
    # Utilities
    "is_valid_cid",
    "is_cid_string",
    "detect_data_location",
    "extract_cid_info",
    "normalize_data_field",
    "build_cid_reference",
    "is_backward_compatible_data",
    "validate_nonce_format",
    "format_cid_display",
    # Endpoint Helpers
    "get_ipfs_client",
    "is_ipfs_enabled",
    "upload_to_ipfs_background",
    "download_from_ipfs",
    "process_event_details",
    "process_private_data_value",
    "process_contract_implementation",
    "resolve_cid_field",
    "resolve_event_details",
    "resolve_multiple_events",
    "close_ipfs_client",
]
