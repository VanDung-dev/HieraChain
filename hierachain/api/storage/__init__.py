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
    process_contract_implementation,
    process_event_details,
    process_private_data_value,
    resolve_cid_field,
    resolve_event_details,
    resolve_multiple_events,
    upload_to_ipfs_background,
)
from .explorer_helpers import (
    build_cid_badge_html,
    build_cid_resolution_button_html,
    format_event_for_display,
    format_event_table_row_html,
    get_explorer_css_styles,
    get_explorer_javascript,
    resolve_event_for_explorer,
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
    "process_private_data_value",
    "process_contract_implementation",
    "resolve_cid_field",
    "resolve_event_details",
    "resolve_multiple_events",
    "close_ipfs_client",
    # Explorer Helpers
    "format_event_for_display",
    "resolve_event_for_explorer",
    "build_cid_badge_html",
    "build_cid_resolution_button_html",
    "get_explorer_css_styles",
    "get_explorer_javascript",
    "format_event_table_row_html",
]
