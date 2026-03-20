"""
API v2 endpoints for HieraChain Ledger

This module provides RESTful API endpoints for the advanced enterprise features,
including channels, private data collections, and enhanced domain contracts.
"""

import time
from fastapi import (
    APIRouter, HTTPException, status, Depends, BackgroundTasks
)
from hierachain.security.verify.api_key_verifier import require_chain_access

from hierachain.security.sanitization import (
    sanitize_string, sanitize_dict, sanitize_for_output,
)
from hierachain.security.secure_logging import SecureLogger
from hierachain.api.storage.endpoint_helpers import (
    process_private_data_value,
    process_contract_implementation
)
from hierachain.api.storage import IPFSError

from hierachain.api.v2.schemas import (
    ChannelCreateRequest, ChannelResponse,
    PrivateCollectionCreateRequest, PrivateDataRequest, PrivateDataResponse,
    ContractCreateRequest, ContractExecuteRequest, ContractResponse,
    OrganizationRequest, OrganizationResponse
)

# Secure logger for API v2
api_logger = SecureLogger("hierachain.api.v2")


router = APIRouter(prefix="/api/v2", tags=["HieraChain-v2"])

# In a production environment, these would be proper service instances
# For now, we'll use mock storage
_channels = {}
_private_collections = {}
_contracts = {}
_organizations = {}


@router.get("/health")
async def health_check():
    """Health check endpoint for API v2"""
    return {
        "status": "healthy",
        "version": "v2",
        "timestamp": time.time()
    }


@router.post(
    "/channels",
    response_model=ChannelResponse,
    dependencies=[Depends(require_chain_access)]
)
async def create_channel(channel_request: ChannelCreateRequest):
    """Create a new channel for secure inter-organization communication"""
    try:
        # In a real implementation, this would create an actual Channel object
        channel_id = channel_request.channel_id
        _channels[channel_id] = {
            "id": channel_id,
            "organizations": channel_request.organizations,
            "policy": channel_request.policy,
            "created_at": time.time()
        }

        # Secure audit logging
        api_logger.audit(
            action="create",
            resource="channel",
            success=True,
            channel_id=channel_id,
            org_count=len(channel_request.organizations)
        )

        return ChannelResponse(
            success=True,
            message=f"Channel '{channel_id}' created successfully",
            channel_id=channel_id
        )
    except Exception as e:
        api_logger.error(
            "Failed to create channel",
            error=str(e),
            channel_id=channel_request.channel_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create channel. An internal error has occurred."
        )


@router.get(
    "/channels/{channel_id}",
    response_model=ChannelResponse,
    dependencies=[Depends(require_chain_access)]
)
async def get_channel(channel_id: str):
    """Get information about a specific channel"""
    if channel_id not in _channels:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel '{channel_id}' not found"
        )
    
    return ChannelResponse(
        success=True,
        message=f"Channel '{channel_id}' found",
        channel_id=channel_id
    )


@router.post(
    "/channels/{channel_id}/private-collections",
    response_model=ChannelResponse,
    dependencies=[Depends(require_chain_access)]
)
async def create_private_collection(
    channel_id: str, collection_request: PrivateCollectionCreateRequest
):
    """Create a private data collection within a channel"""
    if channel_id not in _channels:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel '{channel_id}' not found"
        )
    
    try:
        # Sanitize user input before storing
        collection_name = sanitize_string(collection_request.name)
        safe_members = (
            [sanitize_string(m) for m in collection_request.members]
            if collection_request.members else []
        )
        safe_config = (
            sanitize_dict(collection_request.config)
            if collection_request.config else {}
        )

        _private_collections[collection_name] = {
            "name": collection_name,
            "channel_id": channel_id,
            "members": safe_members,
            "config": safe_config,
            "created_at": time.time()
        }

        api_logger.audit(
            action="create",
            resource="private_collection",
            success=True,
            collection_name=collection_name,
            channel_id=channel_id,
        )
        
        return ChannelResponse(
            success=True,
            message=(
                f"Private collection '{collection_name}'"
                f"created in channel '{channel_id}'"
            ),
            channel_id=channel_id
        )
    except Exception as e:
        api_logger.error(
            "Failed to create private collection",
            error=str(e),
            channel_id=channel_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Failed to create private collection. An internal error has occurred."
            )
        )


@router.post(
    "/private-data",
    response_model=PrivateDataResponse,
    dependencies=[Depends(require_chain_access)]
)
async def add_private_data(
    data_request: PrivateDataRequest,
    background_tasks: BackgroundTasks
):
    """
    Add private data to a collection.

    Supports both on-chain and off-chain (IPFS) storage:
    - On-chain: Provide 'value' dict in request
    - Off-chain: Provide 'value_cid' and 'value_nonce' in request (recommended for sensitive data)

    Off-chain storage provides additional security layer as data is encrypted
    and stored in private IPFS swarm.
    """
    collection_name = data_request.collection
    if collection_name not in _private_collections:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Private collection '{collection_name}' not found"
        )

    try:
        # Sanitize key before using
        key = sanitize_string(data_request.key)

        # Process private data value - handle both on-chain and off-chain
        inline_value, cid_info = process_private_data_value(
            data_request,
            background_tasks=background_tasks
        )

        # Store private data with appropriate storage type
        private_data_entry = {
            "key": key,
            "collection": collection_name,
            "event_metadata": data_request.event_metadata,
            "created_at": time.time()
        }

        if cid_info:
            # Off-chain storage (IPFS) - recommended for sensitive data
            private_data_entry["value_cid"] = cid_info["cid"]
            private_data_entry["value_nonce"] = cid_info["nonce"]
            if cid_info.get("metadata"):
                private_data_entry["value_metadata"] = cid_info["metadata"]

            api_logger.info(
                "Private data using off-chain storage",
                collection=collection_name,
                key=key,
                cid=cid_info["cid"]
            )
        else:
            # On-chain storage (traditional)
            private_data_entry["value"] = inline_value

        # Store in collection (in real implementation, this would go to private state DB)
        # For now, just log the operation

        api_logger.audit(
            action="add",
            resource="private_data",
            success=True,
            collection=collection_name,
            key=key,
            storage_type="offchain" if cid_info else "onchain"
        )

        return PrivateDataResponse(
            success=True,
            message=f"Private data added to collection '{collection_name}'" + (
                " (off-chain storage)" if cid_info else ""
            ),
            key=key
        )
    except IPFSError as e:
        api_logger.error(
            "IPFS error while adding private data",
            error=str(e),
            collection=collection_name
        )
        raise HTTPException(
            status_code=503,
            detail=f"IPFS storage error: {str(e)}"
        ) from e
    except Exception as e:
        api_logger.error(
            "Failed to add private data",
            error=str(e),
            collection=collection_name,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add private data. An internal error has occurred."
        ) from e


@router.post(
    "/contracts",
    response_model=ContractResponse,
    dependencies=[Depends(require_chain_access)]
)
async def create_contract(
    contract_request: ContractCreateRequest,
    background_tasks: BackgroundTasks
):
    """
    Create a new domain contract.

    Supports both on-chain and off-chain (IPFS) contract code storage:
    - On-chain: Provide 'implementation' string in request (for small contracts)
    - Off-chain: Provide 'implementation_cid' and 'implementation_nonce' in request (for large contracts)

    Off-chain storage is recommended for:
    - Large contract implementations
    - Contracts with extensive logic
    - Contracts that may be updated frequently
    """
    try:
        # In a real implementation, this would create an actual DomainContract object
        contract_id = contract_request.contract_id

        # Process contract implementation - handle both on-chain and off-chain
        inline_implementation, cid_info = process_contract_implementation(
            contract_request,
            background_tasks=background_tasks
        )

        # Sanitize metadata
        safe_metadata = sanitize_for_output(
            contract_request.metadata, context="general"
        ) if contract_request.metadata else {}

        # Build contract entry
        contract_entry = {
            "id": contract_id,
            "version": sanitize_string(contract_request.version),
            "metadata": safe_metadata,
            "created_at": time.time()
        }

        if cid_info:
            # Off-chain storage (IPFS) - recommended for large contracts
            contract_entry["implementation_cid"] = cid_info["cid"]
            contract_entry["implementation_nonce"] = cid_info["nonce"]
            if cid_info.get("metadata"):
                contract_entry["implementation_metadata"] = cid_info["metadata"]

            api_logger.info(
                "Contract using off-chain storage",
                contract_id=contract_id,
                cid=cid_info["cid"]
            )
        else:
            # On-chain storage (traditional)
            safe_implementation = sanitize_string(
                inline_implementation, context="general"
            )
            contract_entry["implementation"] = safe_implementation

        _contracts[contract_id] = contract_entry

        api_logger.audit(
            action="create",
            resource="contract",
            success=True,
            contract_id=contract_id,
            storage_type="offchain" if cid_info else "onchain"
        )

        return ContractResponse(
            success=True,
            message=f"Contract '{contract_id}' created successfully" + (
                " (off-chain storage)" if cid_info else ""
            ),
            contract_id=contract_id,
            result=None
        )
    except IPFSError as e:
        api_logger.error(
            "IPFS error while creating contract",
            error=str(e),
            contract_id=contract_request.contract_id
        )
        raise HTTPException(
            status_code=503,
            detail=f"IPFS storage error: {str(e)}"
        ) from e
    except Exception as e:
        api_logger.error(
            "Failed to create contract",
            error=str(e),
            contract_id=contract_request.contract_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create contract. An internal error has occurred."
        )


@router.post(
    "/contracts/execute",
    response_model=ContractResponse,
    dependencies=[Depends(require_chain_access)]
)
async def execute_contract(execution_request: ContractExecuteRequest):
    """Execute a domain contract with a given event"""
    contract_id = execution_request.contract_id
    if contract_id not in _contracts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract '{contract_id}' not found"
        )
    
    try:
        # Simulate contract execution logic
        contract = _contracts[contract_id]
        event = execution_request.event
        
        # In a real implementation, this would be more complex
        # Sanitize all output to prevent stored XSS/template injection
        safe_event = sanitize_string(str(event.get('event', 'unknown')))
        safe_version = sanitize_string(str(contract.get("version", "unknown")))
        safe_entity = sanitize_string(str(event.get("entity_id", "unknown")))
        
        execution_result = {
            "status": "success",
            "output": f"Contract {contract_id} executed with event {safe_event}",
            "details": {
                "contract_version": safe_version,
                "event_entity": safe_entity,
                "execution_timestamp": time.time()
            }
        }
        
        return ContractResponse(
            success=True,
            message=f"Contract '{contract_id}' executed successfully",
            contract_id=contract_id,
            result=execution_result
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to execute contract. An internal error has occurred."
        )


@router.post(
    "/organizations",
    response_model=OrganizationResponse,
    dependencies=[Depends(require_chain_access)]
)
async def register_organization(org_request: OrganizationRequest):
    """Register a new organization with MSP"""
    try:
        # Sanitize organization input before storing
        org_id = sanitize_string(org_request.org_id)
        safe_ca_config = (
            sanitize_dict(org_request.ca_config) if org_request.ca_config else {}
        )

        _organizations[org_id] = {
            "id": org_id,
            "ca_config": safe_ca_config,
            "registered_at": time.time()
        }

        api_logger.audit(
            action="register",
            resource="organization",
            success=True,
            org_id=org_id,
        )
        
        return OrganizationResponse(
            success=True,
            message=f"Organization '{org_id}' registered successfully",
            org_id=org_id
        )
    except Exception as e:
        api_logger.error(
            "Failed to register organization",
            error=str(e),
            org_id=org_request.org_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register organization. An internal error has occurred."
        )


@router.get(
    "/organizations/{org_id}",
    response_model=OrganizationResponse,
    dependencies=[Depends(require_chain_access)]
)
async def get_organization(org_id: str):
    """Get information about a registered organization"""
    if org_id not in _organizations:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization '{org_id}' not found"
        )
    
    return OrganizationResponse(
        success=True,
        message=f"Organization '{org_id}' found",
        org_id=org_id
    )
