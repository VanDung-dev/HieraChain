"""
Security module for HieraChain.

Provides identity management, access control, key management,
and verification services for the HieraChain Ledger.
"""

# Identity Management
from hierachain.security.identity import IdentityManager, IdentityError
from hierachain.security.identity_loader import load_node_identity
from hierachain.security.msp import (
    Certificate,
    CertificateAuthority,
    OrganizationPolicies,
    HierarchicalMSP,
)

# Key Management
from hierachain.security.key_manager import KeyManager, initialize_default_keys
from hierachain.security.key_provider import KeyProvider, LocalKeyProvider, FileVaultProvider

# Access Control & Protection
from hierachain.security.brute_force_protector import BruteForceProtector
from hierachain.security.policy_engine import Policy, PolicyType, PolicyEffect, PolicyEngine
from hierachain.security.sanitization import (
    sanitize_string,
    sanitize_dict,
    sanitize_list,
    sanitize_for_output,
    sanitize_error_message,
    is_safe_input,
    safe_format,
    ValidationError,
)

# Verification
from hierachain.security.verify import (
    BlockVerifier,
    VerificationStatus,
    VerificationResult,
    BlockVerificationError,
    APIKeyVerifier,
    ResourcePermissionChecker,
    create_verify_api_key,
    get_auth_dependency,
    require_event_access,
    require_chain_access,
    require_proof_access,
    ZKPublicInputs,
    ZKVerifier,
    get_zk_verifier,
    verify_zk_proof,
    reset_zk_verifier,
    ZKVerificationError,
    SignatureVerifier,
)

# Security Utilities & Logging
from hierachain.security.secure_logging import (
    SecureLogger,
    get_security_logger,
    get_storage_logger,
)
from hierachain.security.security_utils import (
    KeyPair,
    CryptoError,
    verify_signature,
    generate_key_pair_hex,
)

# Zero Knowledge Proving
from hierachain.security.zk_prover import (
    ZKProver,
    ZKProofResult,
    ZKProvingError,
    get_zk_prover,
    generate_zk_proof,
    reset_zk_prover,
)

# Policy Engine
from hierachain.security.policy_engine import (
    PolicyCondition,
    ComparisonOperator,
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
    "PolicyEngine",
]
