"""
Product configuration template for HieraChain.

This module provides the default Product configuration template as a Python string,
ensuring it works both in development and when installed as a pip package.
"""

# Product configuration template for .env.HRC.example
PRODUCT_CONFIG_TEMPLATE = """# === HieraChain Product Auto-Configuration ===
# Auto-generated for production environment
# Copy this content to .env and customize as needed

# Environment
HRC_ENV=product

# API Settings
HRC_API_HOST=0.0.0.0
HRC_API_PORT=2661

# ==================== DATABASE CONFIGURATION ====================
# Supported backends: sqlite, postgres, redis, memory, parquet_only
# Default: sqlite (for standalone development)
# For cluster/consortium production: postgres
# Note: In docker-compose, node1..node4 automatically connect to their
# respective postgres-node1..node4 sidecars via container environment.

# Database Backend & Connection URL
# HRC_STORAGE_BACKEND=postgres
# DATABASE_URL=postgresql://hiera:hiera_password@localhost:5432/hierachain

# Default fallback (SQLite for standalone development)
HRC_STORAGE_BACKEND=sqlite
DATABASE_URL=sqlite:///hierachain.db
# ==================== END DATABASE CONFIGURATION ====================

# Security - Authentication (MANDATORY in production)
HRC_AUTH_ENABLED=true

# Security - CORS (Restricted in production)
HRC_CORS_ALLOW_ALL=false
HRC_CORS_ORIGINS=

# Security - P2P Network
HRC_P2P_TRUST_POLICY=strict
HRC_P2P_REQUIRE_SIGNATURES=true

# Security - HTTPS/HSTS
HRC_HSTS_ENABLED=true

# Security - Rate Limiting
HRC_RATE_LIMIT=true
HRC_RATE_LIMIT_RPM=100

# Master Key Management (Env-based in production)
HRC_MASTER_KEY_SOURCE=env

# ==================== IPFS STORAGE CONFIGURATION ====================
# Enable IPFS for off-chain storage of large payloads
HRC_IPFS_ENABLED=false

# IPFS Daemon API Address (multiaddr format)
HRC_IPFS_HOST=/ip4/127.0.0.1/tcp/5001

# Automatic Pinning to prevent garbage collection
HRC_IPFS_AUTO_PIN=true

# IPFS Request Timeout (seconds)
HRC_IPFS_TIMEOUT=120

# Encryption Key (32-byte hex) - CRITICAL: Must be the same for all nodes in Channel/Org
# Generate with: python -c "import os; print(os.urandom(32).hex())"
HRC_IPFS_ENCRYPTION_KEY=
# ==================== END IPFS CONFIGURATION ====================

# Logging - Less verbose in production
LOG_LEVEL=WARNING
HRC_LOG_SQL_DETAIL=false
"""
