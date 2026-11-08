"""
Storage module for HieraChain API.

This module provides integration with distributed storage systems like IPFS
for off-chain data storage with encryption support.
"""

from .encryption import AESEncryption, EncryptionError
from .endpoint_helpers import (
    close_ipfs_client,
    download_from_ipfs,
    get_ipfs_client,
    is_ipfs_enabled,
    process_event_details,
    resolve_cid_field,
    resolve_event_details,
    resolve_multiple_events,
    upload_to_ipfs_background,
)
from .ipfs_client import IPFSClient, IPFSError, create_ipfs_client_from_env
from .utils import (
    build_cid_reference,
    detect_data_location,
    extract_cid_info,
    format_cid_display,
    is_backward_compatible_data,
    is_cid_string,
    is_valid_cid,
    normalize_data_field,
    validate_nonce_format,
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
    "resolve_cid_field",
    "resolve_event_details",
    "resolve_multiple_events",
    "close_ipfs_client",
]
