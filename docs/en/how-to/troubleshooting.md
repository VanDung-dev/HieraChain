---
title: "Troubleshooting"
description: "Quick diagnostic checklist for common errors: port/API, dependencies, schema mismatch, API key, Redis/SQLite, performance."
icon: material/wrench
---

# Troubleshooting

This page provides a checklist and quick diagnostic steps for common errors when deploying and operating HieraChain.

## API not responding or 404

* Check the server process:

    ```bash
    python -m hierachain
    ```

* Default listens on `http://localhost:2661`. Open `http://localhost:2661/docs` to verify.
* If the port has changed: see `hierachain/config/settings.py` (environment variable `HRC_API_PORT`).

## 401/403 when calling API

* Production requires `settings.AUTH_ENABLED=True`. Protected routes need an API key with the required scope; health/status routes may be exempt. Check a protected route:

    ```bash
    curl -H "X-API-Key: <your-key>" http://localhost:2661/api/ledger/chains
    ```

* Header name depends on `settings.API_KEY_NAME` (default `X-API-Key`).

## Error when adding events (schema mismatch)

* Ensure the payload includes the required fields:

    ```json
    {
      "entity_id": "...",
      "event_type": "...",
      "details": {"k": "v"}
    }
    ```

* REST `details` is a JSON object and preserves supported typed values in the canonical event payload. Arrow's `details` metadata column is a string projection; it does not replace the original payload.
* The API request model has no timestamp field, and the event builder sets the timestamp from server time. A client-supplied timestamp is not used.

## Cannot create a Sub-Chain

* Chain creation endpoint:

    ```bash
    curl -X POST http://localhost:2661/api/ledger/chains/supply_chain/create
    ```

* Chain name must match regex `[a-zA-Z0-9_\-]+` (see validation in `hierachain/api/ledger/chains.py`).

## Events not appearing in returned blocks

* Use the block retrieval API:

    ```bash
    curl "http://localhost:2661/api/ledger/chains/supply_chain/blocks?limit=5&offset=0"
    ```

* Submission acknowledges ordering acceptance. Wait for batch size/timeout and the commit consumer, then read blocks again. Inspect the orderer status and storage/finalization errors if the event remains absent. MainChain proof submission is separate; it does not force a pending Sub-Chain batch to commit.

## Poor performance / 503 Service Unavailable

* Inspect API payload/rate limits, Redis failures, ordering event-pool/RAM limits and storage error logs. The API has no CPU/RAM `ResourceGuardMiddleware`.
* Check API rate limits and CORS in `settings.py`; configure HSTS at the HTTPS proxy.
* Reduce event batch sizes; tune existing cache instances only after profiling their usage.

## Redis/SQLite not connecting

* Check environment variables:

  * `DATABASE_URL` (SQLite/PostgreSQL)
  * `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`

* Set `HRC_STORAGE_BACKEND=memory` only for isolated tests; it does not retain ledger data. Use `sqlite` or `postgres` for durable signed-block storage.

## business endpoints return errors

* Verify that API business is loaded (see `hierachain/api/server.py` and `hierachain/api/business/router.py`).
* Try the business health endpoint:

    ```bash
    curl -s http://localhost:2661/api/business/health
    ```

## Signatures/keys

* Check the public key is 64‑hex (Ed25519) when registering users (`security/identity.py`).
* Use `security/security_utils.py` to generate test key pairs.

## Logging and auditing

* Set the appropriate log level, see `settings.LOG_LEVEL`.
* Use `risk_management/audit_logger.py` for audit trails.
