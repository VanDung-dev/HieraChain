"""
Helper functions for IPFS integration in API endpoints.

This module provides utilities for handling IPFS upload/download
in FastAPI endpoints with BackgroundTasks support.
"""

from typing import Any
from fastapi import BackgroundTasks

from hierachain.config.settings import settings
from hierachain.security.secure_logging import SecureLogger
from hierachain.api.storage.ipfs_client import (
    IPFSClient, IPFSError, create_ipfs_client_from_env
)
from hierachain.api.storage.utils import is_cid_string

logger = SecureLogger("hierachain.storage.endpoint_helpers")

# Global IPFS client (lazy initialized)
_ipfs_client: IPFSClient | None = None


def get_ipfs_client() -> IPFSClient:
    """
    Get or create IPFS client singleton.

    Returns:
        IPFSClient instance

    Raises:
        IPFSError: If IPFS is not enabled or client creation fails
    """
    global _ipfs_client

    if not settings.IPFS_ENABLED:
        raise IPFSError("IPFS integration is not enabled. Set HRC_IPFS_ENABLED=true")

    if _ipfs_client is None:
        _ipfs_client = create_ipfs_client_from_env()
        logger.info("IPFS client initialized for endpoint operations")

    if _ipfs_client is None:
        raise RuntimeError("IPFS client initialization failed")
    return _ipfs_client


def is_ipfs_enabled() -> bool:
    """Check if IPFS integration is enabled."""
    return settings.IPFS_ENABLED


async def upload_to_ipfs_background(
    data: dict[str, Any],
    metadata: dict[str, Any] | None = None,
    background_tasks: BackgroundTasks | None = None
) -> dict[str, Any]:
    """
    Upload data to IPFS in background task.

    Args:
        data: Data to upload (will be JSON serialized)
        metadata: Optional metadata for AAD encryption
        background_tasks: FastAPI BackgroundTasks instance

    Returns:
        Dict with CID, nonce, and metadata

    Raises:
        IPFSError: If upload fails
    """
    if not is_ipfs_enabled():
        raise IPFSError("IPFS is not enabled")

    client = get_ipfs_client()

    # Upload synchronously (encryption is fast)
    result = client.upload_json(data, encrypt=True, metadata=metadata)

    if background_tasks:
        from hierachain.monitoring import alert_manager
        # Asynchronously log security event using background task
        background_tasks.add_task(
            logger.info,
            "Data uploaded to IPFS (bg logged)",
            cid=result["cid"],
            size=result["size"],
            encrypted=result["encrypted"]
        )
    else:
        logger.info(
            "Data uploaded to IPFS",
            cid=result["cid"],
            size=result["size"],
            encrypted=result["encrypted"]
        )

    return {
        "cid": result["cid"],
        "nonce": result["nonce"],
        "metadata": metadata,
        "size": result["size"]
    }


async def download_from_ipfs(
    cid: str,
    nonce: str | None,
    metadata: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Download and decrypt data from IPFS.

    Args:
        cid: IPFS CID
        nonce: Encryption nonce (hex string)
        metadata: Optional metadata used as AAD

    Returns:
        Decrypted data as dict

    Raises:
        IPFSError: If download or decryption fails
    """
    if not is_ipfs_enabled():
        raise IPFSError("IPFS is not enabled")

    client = get_ipfs_client()

    data = client.download_json(
        cid=cid,
        encrypted=True,
        nonce=nonce,
        metadata=metadata
    )

    logger.debug("Data downloaded from IPFS", cid=cid)

    return data


def process_event_details(
    event_request: Any,
    background_tasks: BackgroundTasks | None = None
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """
    Process event details - either use inline data or upload to IPFS.

    Args:
        event_request: EventRequest schema instance
        background_tasks: FastAPI BackgroundTasks instance

    Returns:
        Tuple of (inline_details, cid_info)
        - If on-chain: (details_dict, None)
        - If off-chain: (None, {cid, nonce, metadata})

    Example::

        details, cid_info = process_event_details(event_request)
        if cid_info:
            event["details_cid"] = cid_info["cid"]
            event["details_nonce"] = cid_info["nonce"]
        else:
            event["details"] = details
    """
    _ = background_tasks  # reserved for future background task support
    # Check if CID is already provided (data already in IPFS)
    if hasattr(event_request, 'details_cid') and event_request.details_cid:
        return None, {
            "cid": event_request.details_cid,
            "nonce": event_request.details_nonce,
            "metadata": event_request.details_metadata
        }

    # Return inline details if provided
    if hasattr(event_request, 'details') and event_request.details:
        return event_request.details, None

    # No details provided
    return None, None


def process_private_data_value(
    private_data_request: Any,
    background_tasks: BackgroundTasks | None = None
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """
    Process private data value - either use inline data or IPFS CID.

    Args:
        private_data_request: PrivateDataRequest schema instance
        background_tasks: FastAPI BackgroundTasks instance

    Returns:
        Tuple of (inline_value, cid_info)
    """
    _ = background_tasks  # reserved for future background task support
    # Check if CID is already provided
    if hasattr(private_data_request, 'value_cid') and private_data_request.value_cid:
        return None, {
            "cid": private_data_request.value_cid,
            "nonce": private_data_request.value_nonce,
            "metadata": private_data_request.value_metadata
        }

    # Return inline value if provided
    if hasattr(private_data_request, 'value') and private_data_request.value:
        return private_data_request.value, None

    # No value provided
    return None, None


def process_contract_implementation(
    contract_request: Any,
    background_tasks: BackgroundTasks | None = None
) -> tuple[str | None, dict[str, Any] | None]:
    """
    Process contract implementation - either use inline code or IPFS CID.

    Args:
        contract_request: ContractCreateRequest schema instance
        background_tasks: FastAPI BackgroundTasks instance

    Returns:
        Tuple of (inline_implementation, cid_info)
    """
    _ = background_tasks  # reserved for future background task support
    # Check if CID is already provided
    if hasattr(contract_request, 'implementation_cid') and contract_request.implementation_cid:
        return None, {
            "cid": contract_request.implementation_cid,
            "nonce": contract_request.implementation_nonce,
            "metadata": contract_request.implementation_metadata
        }

    # Return inline implementation if provided
    if hasattr(contract_request, 'implementation') and contract_request.implementation:
        return contract_request.implementation, None

    # No implementation provided
    return None, None


async def resolve_cid_field(
    data: dict[str, Any],
    field_prefix: str
) -> dict[str, Any]:
    """
    Resolve CID field to actual data if present.

    Args:
        data: Data dict that may contain CID fields
        field_prefix: Field prefix (e.g., "details", "value", "implementation")

    Returns:
        Data dict with resolved field (CID replaced with actual data)

    Example:
        resolved = await resolve_cid_field(data, "details")
        # resolved now has "details" key with actual data
    """
    cid_field = f"{field_prefix}_cid"
    nonce_field = f"{field_prefix}_nonce"
    metadata_field = f"{field_prefix}_metadata"

    # Check if CID exists
    if cid_field not in data or not is_cid_string(data[cid_field]):
        return data

    # Download and decrypt
    try:
        resolved_data = await download_from_ipfs(
            cid=data[cid_field],
            nonce=data.get(nonce_field),
            metadata=data.get(metadata_field)
        )

        # Add resolved data to result
        result = dict(data)
        result[field_prefix] = resolved_data

        # Optionally remove CID fields (keep for reference)
        # del result[cid_field]
        # del result[nonce_field]
        # if metadata_field in result:
        #     del result[metadata_field]

        return result

    except Exception as e:
        logger.error(
            "Failed to resolve CID field",
            field=field_prefix,
            cid=data.get(cid_field),
            error=str(e)
        )
        # Return original data if resolution fails
        return data


async def resolve_event_details(
    event: dict[str, Any],
    resolve: bool = False
) -> dict[str, Any]:
    """
    Resolve event details from IPFS if requested.

    Args:
        event: Event dict
        resolve: Whether to resolve CID to actual data

    Returns:
        Event dict with resolved details if requested
    """
    if not resolve or not is_ipfs_enabled():
        return event

    return await resolve_cid_field(event, "details")


async def resolve_multiple_events(
    events: list[dict[str, Any]],
    resolve: bool = False
) -> list[dict[str, Any]]:
    """
    Resolve details for multiple events.

    Args:
        events: List of event dicts
        resolve: Whether to resolve CIDs

    Returns:
        List of events with resolved details
    """
    if not resolve or not is_ipfs_enabled():
        return events

    resolved = []
    for event in events:
        resolved.append(await resolve_event_details(event, resolve=True))

    return resolved


def close_ipfs_client():
    """Close the global IPFS client connection."""
    global _ipfs_client
    if _ipfs_client is not None:
        _ipfs_client.close()
        _ipfs_client = None
        logger.info("IPFS client connection closed")
