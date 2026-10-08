"""API business — private data endpoint placeholder."""

from fastapi import APIRouter, Depends, HTTPException, status

from hierachain.api.business.schemas import PrivateDataRequest
from hierachain.api.business.state import _private_collections
from hierachain.security.verify.api_key_verifier import require_chain_access

router = APIRouter(tags=["HieraChain-business"])


@router.post(
    "/private-data",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    dependencies=[Depends(require_chain_access)]
)
async def add_private_data(
    data_request: PrivateDataRequest,
) -> None:
    collection_name = data_request.collection
    if collection_name not in _private_collections:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Private collection '{collection_name}' not found"
        )

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Private-data storage is not implemented.",
    )
