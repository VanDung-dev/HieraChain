"""API Ledger — proof submission endpoint.

Submit cryptographic proofs from a sub-chain to the main chain.
"""

from fastapi import APIRouter, Depends, HTTPException

from hierachain.api.ledger.depds import get_hierarchy_manager
from hierachain.api.ledger.schemas import ProofSubmissionResponse
from hierachain.hierarchical.hierarchy_manager import HierarchyManager
from hierachain.security.secure_logging import SecureLogger
from hierachain.security.verify.api_key_verifier import require_proof_access

router = APIRouter(tags=["HieraChain"])
api_logger = SecureLogger("hierachain.api.ledger")


@router.post(
    "/chains/{chain_name}/submit-proof",
    response_model=ProofSubmissionResponse,
    dependencies=[Depends(require_proof_access)]
)
async def submit_proof(
    chain_name: str, manager: HierarchyManager = Depends(get_hierarchy_manager)
):
    try:
        sub_chain = manager.get_sub_chain(chain_name)
        if not sub_chain:
            raise HTTPException(
                status_code=404, detail=f"Sub-chain '{chain_name}' not found"
            )

        main_chain = manager.get_main_chain()
        if not main_chain:
            raise HTTPException(
                status_code=500, detail="Main chain not available"
            )

        if manager.submit_proof_to_main_chain(chain_name) is not True:
            raise HTTPException(
                status_code=500, detail="Failed to submit proof to main chain"
            )

        return ProofSubmissionResponse(
            success=True,
            message=f"Proof submitted from '{chain_name}' to main chain",
            proof_id=f"{chain_name}_{len(sub_chain.chain)}" if sub_chain.chain else None
        )
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error("Failed to submit proof", error=str(e), chain_name=chain_name)
        raise HTTPException(
            status_code=500,
            detail="Failed to submit proof. An internal error has occurred."
        ) from e
