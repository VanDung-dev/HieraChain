"""
API Key Verification module for HieraChain Ledger.

Implements APIKeyVerifier dependency inspired by Google's Apigee for securing API endpoints.
Ensures only authorized clients with valid, non-revoked API keys can access protected resources.
"""

import time
import sys
import os
from fastapi import Depends, HTTPException, Request
from fastapi.security import APIKeyHeader, APIKeyQuery
from typing import Any

from hierachain.security.key_manager import KeyManager
from hierachain.security.secure_logging import get_security_logger
from hierachain.security.brute_force_protector import BruteForceProtector
from hierachain.config.settings import get_settings

# Add the project root to the path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

logger = get_security_logger()


# Different API key placement options
api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)
api_key_query = APIKeyQuery(name="apikey", auto_error=False)


def _get_system_context() -> dict:
    """Return minimal context when verification is disabled."""
    return {
        "user_id": "system",
        "app_details": {"name": "System Access"}
    }


def _extract_client_ip(request: Request) -> str:
    """Extract client IP from request for brute-force tracking."""
    if request and request.client:
        return request.client.host
    return "unknown"


def _get_key_prefix(api_key: str) -> str:
    """Get key prefix for logging purposes."""
    return api_key[:8] if len(api_key) >= 8 else "short_key"


class APIKeyVerifier:
    """
    Verify API key dependency inspired by Google's Apigee APIKeyVerifier policy.
    
    This class provides runtime API key verification for HieraChain
    Ledger endpoints, ensuring secure access control without cryptocurrency concepts.
    
    Features:
    - Runtime key validation and revocation checking
    - Flexible key placement (header, query, form)
    - Permission-based access control
    - Caching for performance
    - Context variable population
    - Comprehensive error handling and auditing
    """

    def __init__(self, config: dict):
        """
        Initialize APIKeyVerifier with configuration.
        
        Args:
            config: Configuration dictionary containing:
                - enabled: Whether verification is enabled
                - key_location: Where to find the key (header, query, form)
                - key_name: Name of the key parameter
                - cache_ttl: Cache time-to-live in seconds
                - revocation_check: How often to check revocation
        """
        self.config = config
        self.key_manager = KeyManager()  # Handles key storage, revocation checks
        self.enabled = config.get('enabled', True)
        self.key_location = config.get('key_location', 'header')
        self.key_name = config.get('key_name', 'x-api-key')
        self.cache_ttl = config.get('cache_ttl', 300)
        
        # Set up appropriate security dependency based on location
        if self.key_location == 'header':
            self.api_key_dependency = APIKeyHeader(name=self.key_name, auto_error=False)
        elif self.key_location == 'query':
            self.api_key_dependency = APIKeyQuery(name=self.key_name, auto_error=False)
        else:
            self.api_key_dependency = api_key_header

        # Initialize brute-force protection
        bf_config = config.get('brute_force', {})
        self.brute_force_protector = BruteForceProtector(bf_config)
    
    async def __call__(self, request: Request, api_key: str | None = None) -> dict:
        """
        Verify API key from the incoming request.
        
        This method is called as a FastAPI dependency to verify API keys
        for protected endpoints in the HieraChain Ledger.
        
        Args:
            request: The FastAPI Request object
            api_key: The API key from the configured location
            
        Returns:
            Dict: Context variables including user_id and app_details
            
        Raises:
            HTTPException: 401 for missing/invalid keys, 403 for insufficient permissions
        """
        if not self.enabled:
            return _get_system_context()

        client_ip = _extract_client_ip(request)
        await self._check_brute_force_protection(client_ip)
        
        api_key = await self._extract_api_key(request, api_key)
        self._validate_api_key_present(api_key, client_ip)
        
        key_prefix = _get_key_prefix(api_key)
        await self._verify_key_validity(api_key, key_prefix, client_ip)
        
        return self._build_success_context(api_key, key_prefix)

    async def _check_brute_force_protection(self, client_ip: str) -> None:
        """Check if IP is locked out due to brute-force attempts."""
        if not self.brute_force_protector.is_locked_out(client_ip):
            return
            
        remaining = self.brute_force_protector.get_remaining_lockout(client_ip)
        self._log_security_event("ip_locked_out", {
            "ip": client_ip,
            "remaining_seconds": round(remaining),
            "timestamp": time.time()
        })
        raise HTTPException(
            status_code=429,
            detail="Too many failed authentication attempts. Please try again later."
        )

    async def _extract_api_key(self, request: Request, api_key: str | None) -> str | None:
        """Extract API key from request if not provided directly."""
        if api_key or not request:
            return api_key
        return await self.api_key_dependency(request)

    def _validate_api_key_present(self, api_key: str | None, client_ip: str) -> None:
        """Validate that API key is provided."""
        if api_key:
            return
            
        self.brute_force_protector.record_failure(client_ip, "no_key")
        self._log_security_event("missing_api_key", {"timestamp": time.time()})
        raise HTTPException(
            status_code=401,
            detail="API key missing. Please provide a valid API key."
        )

    async def _verify_key_validity(self, api_key: str, key_prefix: str, client_ip: str) -> None:
        """Verify API key validity and revocation status."""
        if not self.key_manager.is_valid(api_key):
            await self._handle_invalid_key(key_prefix, client_ip)
            
        if self.key_manager.is_revoked(api_key):
            await self._handle_revoked_key(key_prefix, client_ip)

    async def _handle_invalid_key(self, key_prefix: str, client_ip: str) -> None:
        """Handle invalid API key case."""
        self.brute_force_protector.record_failure(client_ip, key_prefix)
        self._log_security_event("invalid_api_key", {
            "key_prefix": key_prefix,
            "timestamp": time.time()
        })
        raise HTTPException(
            status_code=401,
            detail="Invalid API key. The provided key is not valid or has expired."
        )

    async def _handle_revoked_key(self, key_prefix: str, client_ip: str) -> None:
        """Handle revoked API key case."""
        self.brute_force_protector.record_failure(client_ip, key_prefix)
        self._log_security_event("revoked_api_key", {
            "key_prefix": key_prefix,
            "timestamp": time.time()
        })
        raise HTTPException(
            status_code=401,
            detail="API key revoked. The provided key has been revoked."
        )

    def _build_success_context(self, api_key: str, key_prefix: str) -> dict:
        """Build success context after verification."""
        if self.cache_ttl > 0:
            self.key_manager.cache_key(api_key, ttl=self.cache_ttl)

        user_id = self.key_manager.get_user(api_key)
        app_details = self.key_manager.get_app_details(api_key)

        context = {
            "user_id": user_id,
            "app_details": app_details,
            "api_key_prefix": key_prefix,
            "verified_at": time.time(),
            "_api_key": api_key
        }

        self._log_security_event("successful_verification", {
            "user_id": user_id,
            "app_name": app_details.get('name', 'Unknown') if app_details else 'Unknown',
            "timestamp": time.time()
        })

        return context
    
    def check_resource_permission(self, api_key: str, resource: str) -> bool:
        """
        Check if API key has permission for a specific resource.
        
        Args:
            api_key: The API key to check
            resource: The resource/operation to check permission for
            
        Returns:
            bool: True if key has permission, False otherwise
        """
        return self.key_manager.has_permission(api_key, resource)
    
    def require_permission(self, resource: str):
        """
        Decorator factory for requiring specific permissions.
        
        Args:
            resource: The resource that requires permission
            
        Returns:
            Decorator function that checks permissions
        """
        def permission_dependency(context: dict = Depends(self)) -> dict:
            # Extract API key from context (would need to be passed differently in real implementation)
            api_key = getattr(context, '_api_key', None)
            
            if api_key and not self.check_resource_permission(api_key, resource):
                raise HTTPException(
                    status_code=403,
                    detail=f"Insufficient permissions. Access to '{resource}' requires additional permissions."
                )
            
            return context
        
        return permission_dependency

    @staticmethod
    def _log_security_event(event_type: str, details: dict):
        """
        Log security events for auditing.

        Args:
            event_type: Type of security event
            details: Event details
        """
        logger.info(
            f"Security event: {event_type}",
            event_type=event_type,
            details=details,
            source="APIKeyVerifier",
            Ledger="hierachain"
        )


def get_auth_dependency() -> Any:
    """
    Factory to get the configured APIKeyVerifier instance based on app settings.
    If auth is disabled, returns a dummy dependency.
    """
    settings = get_settings()
    if settings.AUTH_ENABLED:
        return APIKeyVerifier(settings.get_auth_config())
    return None

def _get_active_verifier() -> Any:
    """Helper to get an instance for Depends"""
    return get_auth_dependency()

async def require_event_access(
    request: Request,
    context: dict | None = Depends(_get_active_verifier)
) -> dict:
    """
    Require permission to access event-related endpoints.
    """
    if context is None:
        return {} # Auth disabled
    
    # We must explicitly call the verifier if it wasn't resolved fully
    if callable(context) and isinstance(context, APIKeyVerifier):
        context = await context(request)

    if not ResourcePermissionChecker.has_permission(context, 'events'):
        raise HTTPException(
            status_code=403,
            detail="Access to event operations requires 'events' permission."
        )
    return context


async def require_chain_access(
    request: Request,
    context: dict | None = Depends(_get_active_verifier)
) -> dict:
    """
    Require permission to access chain-related endpoints.
    """
    if context is None:
        return {} # Auth disabled
        
    if callable(context) and isinstance(context, APIKeyVerifier):
        context = await context(request)

    if not ResourcePermissionChecker.has_permission(context, 'chains'):
        raise HTTPException(
            status_code=403,
            detail="Access to chain operations requires 'chains' permission."
        )
    return context


async def require_proof_access(
    request: Request,
    context: dict | None = Depends(_get_active_verifier)
) -> dict:
    """
    Require permission to access proof submission endpoints.
    """
    if context is None:
        return {} # Auth disabled
        
    if callable(context) and isinstance(context, APIKeyVerifier):
        context = await context(request)

    if not ResourcePermissionChecker.has_permission(context, 'proofs'):
        raise HTTPException(
            status_code=403,
            detail="Access to proof operations requires 'proofs' permission."
        )
    return context


def _has_event_permission(context: dict) -> bool:
    """Check if context has event permissions."""
    return ResourcePermissionChecker.has_permission(context, 'events')


def _has_chain_permission(context: dict) -> bool:
    """Check if context has chain permissions."""
    return ResourcePermissionChecker.has_permission(context, 'chains')


def _has_proof_permission(context: dict) -> bool:
    """Check if context has proof permissions."""
    return ResourcePermissionChecker.has_permission(context, 'proofs')


class ResourcePermissionChecker:
    """
    Helper class for checking resource-specific permissions.
    Used with APIKeyVerifier for granular access control.
    """
    
    @staticmethod
    def _has_permission(context: dict, permission_type: str) -> bool:
        """
        Check if context has specific permission.

        Args:
            context: The context containing app details
            permission_type: The permission type to check for (events, chains, proofs)

        Returns:
            bool: True if context has the required permission, False otherwise
        """
        app_details = context.get('app_details', {})
        permissions = app_details.get('permissions', [])
        return permission_type in permissions or 'all' in permissions

    @staticmethod
    def has_permission(context: dict, permission_type: str) -> bool:
        """
        Public wrapper for checking context permissions without accessing
        the protected _has_permission method from outside the class.

        Args:
            context: The context containing app details
            permission_type: The permission type to check for (events, chains, proofs)

        Returns:
            bool: True if context has the required permission, False otherwise
        """
        return ResourcePermissionChecker._has_permission(context, permission_type)

    def __init__(self, verify_api_key: APIKeyVerifier):
        """
        Initialize with APIKeyVerifier instance.
        
        Args:
            verify_api_key: APIKeyVerifier instance to use for permission checking
        """
        self.verify_api_key = verify_api_key


#Factoryfunction for creating configured APIKeyVerifier instances
def create_verify_api_key(config: dict) -> APIKeyVerifier:
    """
    Factory function to create configured VerifyAPIKey instance.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        APIKeyVerifier: Configured instance
    """
    return APIKeyVerifier(config)


# Example configurations for different use cases
DEFAULT_CONFIG = {
    "enabled": True,
    "key_location": "header",
    "key_name": "x-api-key", 
    "cache_ttl": 300,
    "revocation_check": "daily"
}

QUERY_PARAM_CONFIG = {
    "enabled": True,
    "key_location": "query",
    "key_name": "apikey",
    "cache_ttl": 300,
    "revocation_check": "daily"
}

FORM_PARAM_CONFIG = {
    "enabled": True,
    "key_location": "form",
    "key_name": "api_key",
    "cache_ttl": 300,
    "revocation_check": "daily"
}
