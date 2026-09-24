"""
Security module for HieraChain.

Provides identity management, access control, key management,
and verification services for the HieraChain Ledger.
"""

# Identity Management
# Access Control & Protection
from hierachain.security.brute_force_protector import BruteForceProtector
from hierachain.security.identity import IdentityError, IdentityManager
from hierachain.security.identity_loader import load_node_identity

# Key Management
from hierachain.security.key_manager import KeyManager, initialize_default_keys
from hierachain.security.key_provider import (
    FileVaultProvider,
    KeyProvider,
    LocalKeyProvider,
)
from hierachain.security.msp import (
    Certificate,
    CertificateAuthority,
    HierarchicalMSP,
    OrganizationPolicies,
)

# Policy Engine
from hierachain.security.policy_engine import (
    ComparisonOperator,
    Policy,
    PolicyCondition,
    PolicyEffect,
    PolicyEngine,
    PolicyType,
)
from hierachain.security.sanitization import (
    ValidationError,
    is_safe_input,
    safe_format,
    sanitize_dict,
    sanitize_error_message,
    sanitize_for_output,
    sanitize_list,
    sanitize_string,
)

# Security Utilities & Logging
from hierachain.security.secure_logging import (
    SecureLogger,
    get_security_logger,
    get_storage_logger,
)
from hierachain.security.security_utils import (
    CryptoError,
    KeyPair,
    generate_key_pair_hex,
    verify_signature,
)

# Verification
from hierachain.security.verify import (
    APIKeyVerifier,
    BlockVerificationError,
    BlockVerifier,
    ResourcePermissionChecker,
    SignatureVerifier,
    VerificationResult,
    VerificationStatus,
    ZKPublicInputs,
    ZKVerificationError,
    ZKVerifier,
    create_verify_api_key,
    get_auth_dependency,
    get_zk_verifier,
    require_chain_access,
    require_event_access,
    require_proof_access,
    reset_zk_verifier,
    verify_zk_proof,
)

# Zero Knowledge Proving
from hierachain.security.zk_prover import (
    ZKProofResult,
    ZKProver,
    ZKProvingError,
    generate_zk_proof,
    get_zk_prover,
    reset_zk_prover,
)

__all__ = [
    # Identity Management
    "IdentityManager",
    "IdentityError",
    "load_node_identity",
    "Certificate",
    "CertificateAuthority",
    "OrganizationPolicies",
    "HierarchicalMSP",

    # Key Management
    "KeyManager",
    "initialize_default_keys",
    "KeyProvider",
    "LocalKeyProvider",
    "FileVaultProvider",

    # Access Control & Protection
    "BruteForceProtector",
    "Policy",
    "PolicyType",
    "PolicyEffect",
    "PolicyEngine",
    "sanitize_string",
    "sanitize_dict",
    "sanitize_list",
    "sanitize_for_output",
    "sanitize_error_message",
    "is_safe_input",
    "safe_format",
    "ValidationError",

    # Verification
    "BlockVerifier",
    "VerificationStatus",
    "VerificationResult",
    "BlockVerificationError",
    "APIKeyVerifier",
    "ResourcePermissionChecker",
    "create_verify_api_key",
    "get_auth_dependency",
    "require_event_access",
    "require_chain_access",
    "require_proof_access",
    "ZKPublicInputs",
    "ZKVerifier",
    "get_zk_verifier",
    "verify_zk_proof",
    "reset_zk_verifier",
    "ZKVerificationError",
    "SignatureVerifier",

    # Security Utilities & Logging
    "SecureLogger",
    "get_security_logger",
    "KeyPair",
    "CryptoError",
    "verify_signature",
    "generate_key_pair_hex",

    # Zero Knowledge Proving
    "ZKProver",
    "ZKProofResult",
    "ZKProvingError",
    "get_zk_prover",
    "generate_zk_proof",
    "reset_zk_prover",

    # Policy Engine
    "PolicyCondition",
    "ComparisonOperator",
]
