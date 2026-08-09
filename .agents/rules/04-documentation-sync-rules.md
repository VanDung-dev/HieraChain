# Documentation Synchronization & Accuracy Rules

When updating or auditing documentation under `docs/en/` and `docs/vi/`:

## 1. Truth in Source Code (`hierachain/`)
* **Source of Truth**: The core Python package [`hierachain/`](file:///Users/vandungdev/Documents/GitHub/HieraChain/hierachain) is the absolute authoritative reference for all API signatures, module paths, default settings, and architectural workflows.
* **No Speculative Documentation**: Never document features, endpoints, configuration keys, or parameter names without verifying their exact implementation in `hierachain/`.

## 2. Dual Language Parity (`docs/en/` <-> `docs/vi/`)
* **1:1 Structural Parity**: Any file, endpoint description, or architectural update made in English (`docs/en/`) MUST be mirrored accurately in Vietnamese (`docs/vi/`).
* **Symmetrical Code Snippets**: Code examples, JSON schemas, parameter names, and file paths inside code blocks must remain 100% identical across both languages.

## 3. Path & Signature Verification
* **File Path Accuracy**: Always verify and update referenced module paths against the actual layout of `hierachain/` (e.g. `main_chain/base.py` instead of `main_chain.py`).
* **Environment Variable Alignment**: Ensure all documented env vars (e.g., `HRC_MAINCHAIN_CONSENSUS`, `HRC_BLOCK_INTERVAL`) match the keys evaluated in `hierachain/config/`.
