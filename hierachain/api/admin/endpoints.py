"""
API admin endpoints for System Management
"""

import os
import threading
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from hierachain.api.admin.schemas import (
    NodeStatusResponse,
    SecureEventRequest,
    SecureEventResponse,
    VerifyIdentityRequest,
    VerifyIdentityResponse,
)
from hierachain.api.ledger.access import require_chain_write
from hierachain.api.ledger.depds import get_hierarchy_manager
from hierachain.config.settings import get_settings
from hierachain.config.version import get_version
from hierachain.consensus.ordering.types import OrderingBackpressureError
from hierachain.hierarchical.hierarchy_manager import HierarchyManager
from hierachain.security.key_provider import CryptoError, LocalKeyProvider
from hierachain.security.secure_logging import SecureLogger
from hierachain.security.verify.api_key_verifier import require_chain_access
from hierachain.security.verify.signature_verifier import SignatureVerifier
from hierachain.serialization import loads_json

logger = SecureLogger("hierachain.api.admin")
router = APIRouter(prefix="/api/admin", tags=["HieraChain-admin (System & Admin)"])

verifier = SignatureVerifier()

_VERIFY_IDENTITY_RPM = 10
_VERIFY_WINDOW_SECONDS = 60.0
_NONCE_TTL_SECONDS = 600.0
_verify_attempts: dict[str, list[float]] = {}
_verify_attempts_lock = threading.Lock()
_seen_nonces: dict[str, float] = {}
_nonce_lock = threading.Lock()
_trusted_senders: tuple[str, float, frozenset[str]] | None = None
_trusted_senders_lock = threading.Lock()
_api_state_store: Any = None
_api_state_config: tuple[str, str] | None = None
_api_state_lock = threading.Lock()


def _get_api_state_store() -> Any:
    """Return the configured shared replay/rate-limit store, if any."""
    global _api_state_store, _api_state_config
    settings = get_settings()
    config = (settings.AUTH_STATE_REDIS_URL, settings.API_STATE_DB)
    with _api_state_lock:
        if config != _api_state_config:
            from hierachain.adapters.database.auth_state import (
                RedisApiStateStore,
                SQLiteApiStateStore,
            )

            if config[0]:
                store: Any = RedisApiStateStore(config[0])
            elif config[1]:
                store = SQLiteApiStateStore(config[1])
            else:
                store = None
            _api_state_store = store
            _api_state_config = config
        return _api_state_store


def _consume_nonce(nonce: str) -> None:
    store = _get_api_state_store()
    if store is not None:
        try:
            accepted = store.consume_nonce(nonce, time.time(), _NONCE_TTL_SECONDS)
        except Exception as exc:
            logger.error("Replay protection store is unavailable", error=str(exc))
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Replay protection store is unavailable.",
            ) from exc
        if not accepted:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Event nonce has already been used.",
            )
        return

    now = time.monotonic()
    with _nonce_lock:
        expired = [key for key, seen_at in _seen_nonces.items() if now - seen_at > _NONCE_TTL_SECONDS]
        for key in expired:
            del _seen_nonces[key]
        if nonce in _seen_nonces:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Event nonce has already been used.",
            )
        _seen_nonces[nonce] = now


def _load_trusted_sender_keys() -> frozenset[str] | None:
    global _trusted_senders
    path = get_settings().BLOCK_TRUSTED_KEYS_FILE
    if not path:
        return None
    try:
        modified_at = os.path.getmtime(path)
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Trusted key store is unavailable.",
        ) from exc

    with _trusted_senders_lock:
        if _trusted_senders is not None and _trusted_senders[0] == path and _trusted_senders[1] == modified_at:
            return _trusted_senders[2]
        try:
            with open(path, "rb") as trusted_file:
                raw_keys = loads_json(trusted_file.read())
        except (OSError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Trusted key store is unavailable.",
            ) from exc
        if not isinstance(raw_keys, dict) or not raw_keys:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Trusted key store is unavailable.",
            )
        keys = frozenset(
            value.removeprefix("0x").lower()
            for value in raw_keys.values()
            if isinstance(value, str) and value
        )
        _trusted_senders = (path, modified_at, keys)
        return keys


def _enforce_verify_identity_rate_limit(request: Request) -> None:
    client = request.client.host if request.client is not None else "unknown"
    store = _get_api_state_store()
    if store is not None:
        try:
            allowed = store.allow_request(
                f"verify-identity:{client}",
                time.time(),
                _VERIFY_WINDOW_SECONDS,
                _VERIFY_IDENTITY_RPM,
            )
        except Exception as exc:
            logger.error("Rate limit store is unavailable", error=str(exc))
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Rate limit store is unavailable.",
            ) from exc
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many identity verification attempts. Please try again later.",
            )
        return

    now = time.monotonic()
    with _verify_attempts_lock:
        recent = [seen_at for seen_at in _verify_attempts.get(client, []) if now - seen_at < _VERIFY_WINDOW_SECONDS]
        if len(recent) >= _VERIFY_IDENTITY_RPM:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many identity verification attempts. Please try again later.",
            )
        recent.append(now)
        _verify_attempts[client] = recent


def get_current_key_provider() -> LocalKeyProvider:
    """
    Dependency to get the active key provider with loaded identity.
    
    Raises:
        HTTPException(401): If identity file is missing or fails to load
    """
    settings = get_settings()
    identity_path = settings.VALIDATOR_IDENTITY_PATH
    
    if not os.path.exists(identity_path):
        logger.error(
            "Identity file not found, access denied",
            path=identity_path
        )
        raise HTTPException(
            status_code=401,
            detail="Node identity not configured. Please provide valid identity file."
        )
    
    try:
        logger.info("Loading node identity", path=identity_path)
        return LocalKeyProvider.from_file(identity_path)
    except CryptoError as e:
        logger.error("Failed to load node identity", error=str(e))
        raise HTTPException(
            status_code=401,
            detail=f"Failed to load node identity: {e!s}"
        )


@router.post(
    "/verify-identity",
    response_model=VerifyIdentityResponse,
    dependencies=[Depends(require_chain_access), Depends(_enforce_verify_identity_rate_limit)],
)
async def verify_identity(
    request: VerifyIdentityRequest,
    key_provider: LocalKeyProvider = Depends(get_current_key_provider)
):
    """
    Verify node identity by signing a challenge.
    Used by management tools to confirm this node is a legitimate member of the network.
    """
    try:
        challenge_bytes = b"HRC_IDENTITY_CHALLENGE:" + request.challenge.encode()
        signature = key_provider.sign(challenge_bytes)
        settings = get_settings()
        return VerifyIdentityResponse(
            status="success",
            node_id=settings.NODE_ID,
            signature=signature,
            challenge=request.challenge
        )
    except Exception as e:
        logger.error("Identity verification failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Identity verification failed. An internal error has occurred."
        )


@router.get(
    "/status",
    response_model=NodeStatusResponse,
)
async def get_status(manager: HierarchyManager = Depends(get_hierarchy_manager)):
    """
    Get detailed node status report.
    """

    # Get active chains count from hierarchy manager
    chains_active = len(manager.get_all_sub_chains())

    # Calculate uptime
    uptime_seconds = time.time() - manager.system_started_at
    days, rem = divmod(int(uptime_seconds), 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)

    if days > 0:
        uptime_str = f"{days}d {hours}h {minutes}m"
    else:
        uptime_str = f"{hours}h {minutes}m {seconds}s"

    # Check license status (mocked as true)
    license_active = True

    return NodeStatusResponse(
        status="active",
        version=get_version(),
        chains_active=chains_active,
        license_active=license_active,
        uptime=uptime_str
    )


@router.post(
    "/chains/{chain_name}/secure-events",
    response_model=SecureEventResponse,
    dependencies=[Depends(require_chain_access), Depends(require_chain_write)]
)
async def add_secure_event(
    chain_name: str,
    request: SecureEventRequest,
    manager: HierarchyManager = Depends(get_hierarchy_manager)
):
    """
    High-integrity event submission.
    Mandates synchronous validation of signatures and data integrity.
    """
    try:
        # Get target chain
        chain = manager.get_sub_chain(chain_name)
        if not chain:
            raise HTTPException(status_code=404, detail=f"Chain '{chain_name}' not found")
        
        # Add event to chain
        event_data = request.model_dump(exclude_unset=True)

        target_chain_id = request.chain_id
        if target_chain_id is not None and target_chain_id != chain_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Target chain mismatch: event specifies '{target_chain_id}' but endpoint is '{chain_name}'."
            )
        if request.timestamp is not None and abs(time.time() - request.timestamp) > 300:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Event timestamp has expired or is too far in the future."
            )
        
        # 1. Cryptographic validation using SignatureVerifier
        # This performs canonicalization and Ed25519/ECDSA verification
        if not verifier.verify_event_signature(event_data, request.sender):
            logger.warning(
                "Secure event signature verification failed",
                chain=chain_name,
                sender=request.sender,
                entity_id=request.entity_id
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cryptographic signature verification failed. Event integrity cannot be guaranteed."
            )

        trusted_senders = _load_trusted_sender_keys()
        if trusted_senders is not None and request.sender.removeprefix("0x").lower() not in trusted_senders:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Event signer is not a trusted member of this network.",
            )

        _consume_nonce(request.nonce)

        # Retain the signed content so ordering and journal replay can verify it again.
        event_data["signature_content"] = {
            key: value for key, value in event_data.items()
            if key not in {"sender", "signature"}
        }
        event_data["event"] = request.event_type
        if request.timestamp is None:
            event_data["timestamp"] = time.time()

        # 2. Journal and queue the verified event for asynchronous ordering.
        event_hash = chain.add_event(event_data)

        logger.audit(
            action="submit_secure",
            resource="event",
            success=True,
            chain=chain_name,
            entity_id=request.entity_id
        )

        return SecureEventResponse(
            status="queued", event_hash=event_hash, timestamp=time.time()
        )
    except HTTPException:
        raise
    except OrderingBackpressureError as exc:
        raise HTTPException(status_code=503, detail={
            "message": str(exc), "event_id": exc.event_id, "journaled": exc.journaled,
        }) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as e:
        logger.error("Secure event submission failed", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")
