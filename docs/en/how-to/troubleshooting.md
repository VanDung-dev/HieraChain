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
    python -m hierachain.api.server
    ```

* Default listens on `http://localhost:2661`. Open `http://localhost:2661/docs` to verify.
* If the port has changed: see `hierachain/config/settings.py` (environment variable `HRC_API_PORT`).

## 401/403 when calling API

* Production may enable AUTH: `settings.AUTH_ENABLED`. In that case, you need to send an API key:

    ```bash
    curl -H "X-API-Key: <your-key>" http://localhost:2661/api/v1/health
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

* `details` is a map<string,string>. Non-string values will be converted to strings.
* Timestamps are server-generated; no need to send from the client.

## Cannot create a Sub-Chain

* Chain creation endpoint:

    ```bash
    curl -X POST http://localhost:2661/api/v1/chains/supply_chain/create
    ```

* Chain name must match regex `[a-zA-Z0-9_\-]+` (see validation in `api/v1/endpoints.py`).

## Events not appearing in returned blocks

* Use the block retrieval API:

    ```bash
    curl "http://localhost:2661/api/v1/chains/supply_chain/blocks?limit=5&offset=0"
    ```

* Some chains need to be finalized or have a proof submitted to see new blocks. Try submitting a proof:

    ```bash
    curl -X POST http://localhost:2661/api/v1/chains/supply_chain/submit-proof
    ```

## Poor performance / 503 Service Unavailable

* If `ResourceGuardMiddleware` is integrated, 503 may be due to CPU/RAM exceeding thresholds.
* Check rate limit/HSTS/CORS configuration in `settings.py`.
* Reduce event batch sizes, enable advanced caching if appropriate (`ADVANCED_CACHING_ENABLED`).

## Redis/SQLite not connecting

* Check environment variables:

  * `DATABASE_URL` (SQLite/PostgreSQL)
  * `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`

* Switch `DEFAULT_STORAGE_BACKEND` to `memory` to isolate storage issues.

## V2 endpoints return errors

* Verify that API v2 is loaded (see `hierachain/api/server.py` and `hierachain/api/v2/endpoints.py`).
* Try the v2 health endpoint:

    ```bash
    curl -s http://localhost:2661/api/v2/health
    ```

## Signatures/keys

* Check the public key is 64‑hex (Ed25519) when registering users (`security/identity.py`).
* Use `security/security_utils.py` to generate test key pairs.

## Logging and auditing

* Set the appropriate log level, see `settings.LOG_LEVEL`.
* Use `risk_management/audit_logger.py` for audit trails.
