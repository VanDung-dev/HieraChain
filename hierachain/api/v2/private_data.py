"""API v2 — private data endpoints.

Store and retrieve private data within collections,
with optional off-chain (IPFS) storage.
"""

import time
from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks

from hierachain.api.v2.schemas import PrivateDataRequest, PrivateDataResponse
from hierachain.api.v2.state import _private_collections
from hierachain.security.sanitization import sanitize_string
from hierachain.security.verify.api_key_verifier import require_chain_access
from hierachain.security.secure_logging import SecureLogger
from hierachain.api.storage.endpoint_helpers import process_private_data_value
from hierachain.api.storage import IPFSError

router = APIRouter(tags=["HieraChain-v2"])
api_logger = SecureLogger("hierachain.api.v2")


@router.post(
    "/private-data",
    response_model=PrivateDataResponse,
    dependencies=[Depends(require_chain_access)]
)
async def add_private_data(
    data_request: PrivateDataRequest,
    background_tasks: BackgroundTasks
):
    collection_name = data_request.collection
    if collection_name not in _private_collections:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Private collection '{collection_name}' not found"
        )

    try:
        key = sanitize_string(data_request.key)

        inline_value, cid_info = process_private_data_value(
            data_request,
            background_tasks=background_tasks
        )

        private_data_entry = {
            "key": key,
            "collection": collection_name,
            "event_metadata": data_request.event_metadata,
            "created_at": time.time()
        }

        if cid_info:
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
            private_data_entry["value"] = inline_value

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
