"""API v2 — domain contract endpoints.

Create and execute smart contracts with optional off-chain
(IPFS) storage for large implementations.
"""

import time
from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks

from hierachain.api.business.schemas import (
    ContractCreateRequest, ContractExecuteRequest, ContractResponse,
)
from hierachain.security.sanitization import sanitize_string, sanitize_for_output
from hierachain.security.verify.api_key_verifier import require_chain_access
from hierachain.security.secure_logging import SecureLogger
from hierachain.api.storage.endpoint_helpers import process_contract_implementation
from hierachain.api.storage import IPFSError
from hierachain.api.business.state import _contracts

router = APIRouter(tags=["HieraChain-v2"])
api_logger = SecureLogger("hierachain.api.business")


@router.post(
    "/contracts",
    response_model=ContractResponse,
    dependencies=[Depends(require_chain_access)]
)
async def create_contract(
    contract_request: ContractCreateRequest,
    background_tasks: BackgroundTasks
):
    try:
        contract_id = contract_request.contract_id

        inline_implementation, cid_info = process_contract_implementation(
            contract_request,
            background_tasks=background_tasks
        )

        safe_metadata = sanitize_for_output(
            contract_request.metadata, context="general"
        ) if contract_request.metadata else {}

        contract_entry = {
            "id": contract_id,
            "version": sanitize_string(contract_request.version),
            "metadata": safe_metadata,
            "created_at": time.time()
        }

        if cid_info:
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
            if inline_implementation is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Contract implementation is required for on-chain storage"
                )
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
    contract_id = execution_request.contract_id
    if contract_id not in _contracts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract '{contract_id}' not found"
        )

    try:
        contract = _contracts[contract_id]
        event = execution_request.event

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
