# Critical Guardrails & Terminology Rules

HieraChain is an **enterprise-grade hierarchical blockchain ledger** built in Python for business processes — **NOT cryptocurrency**.

## Term Censorship
* **Never introduce cryptocurrency terminology** into any event data, variable names, API endpoints, function signatures, or comments.
* **Forbidden terms**: `transaction`, `mining`, `coin`, `token`, `wallet`, `address`, `sender`, `receiver`, `amount`, `fee`.
* **Required terms**: Use `event` (instead of transaction), `node`, `msp_id`, `entity_id`, `details`, etc.
* *Note*: The `CrossChainValidator` scans and flags forbidden terms on commit/validation.

## Coding Conventions & Forbidden Patterns
* **Strict Type Hints**: Required on all function signatures across the codebase.
* **No `print()` Statements**: Do not use `print()` in library code (use logging or `SecureLogger`).
* **No Direct Storage Calls**: Do not make direct `sqlite3` or `redis` calls outside of `adapters/database/`.
* **No Bulk Test Execution**: Do not run all tests at once to avoid resource conflicts; run per-file.
* **No Hardcoded Secrets**: Do not store secrets in code; use environment variables.
* **No Skipping Event Journal**: Do not skip the `TransactionJournal` (`EventJournal`) durability step when implementing ordering flows.
* **No Bypassing Policy Engine**: Do not bypass `PolicyEngine` for access-sensitive operations.
