---
title: API Admin
description: "HieraChain REST API Admin documentation: System administration, node authentication, and status checks."
icon: material/numeric-3-circle
---

# API Admin

## Endpoints and access

The router is defined in `hierachain/api/admin/endpoints.py` with request/response models in `schemas.py`.

| Endpoint | Access and behavior |
|:---------|:--------------------|
| `POST /api/admin/verify-identity` | Requires `chains` scope when API-key authentication is enabled; signs a domain-prefixed challenge |
| `GET /api/admin/status` | Exempt from global API-key authentication; reports node status when the hierarchy manager is available |
| `POST /api/admin/chains/{chain_name}/secure-events` | Requires `chains` scope when authenticated; verifies the event signature before submitting it to the chain |

Protect public status access at the reverse proxy if the deployment requires it. The status route has no `require_chain_access` dependency.

## Verify node identity

`VerifyIdentityRequest` contains a `challenge` string. The handler signs these bytes:

```python
payload = b"HRC_IDENTITY_CHALLENGE:" + challenge.encode("utf-8")
```

It does not decode the challenge as hexadecimal bytes. The response contains `status`, `node_id`, `signature` and the original `challenge`. Verify the signature over the same prefixed UTF-8 payload using the node's approved public key. Choose a fresh challenge and track it in the client if replay protection is required.

```bash
curl -X POST http://localhost:2661/api/admin/verify-identity \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your-key>" \
  -d '{"challenge": "abcd1234"}'
```

The dependency loads `LocalKeyProvider.from_file()` from `HRC_VALIDATOR_IDENTITY`. That provider reads the `private_key` field. The block-signing loader instead expects the complete node identity fields described in [Key Backup](../workflows/key-backup.md). If both loaders use one file, it must satisfy both formats and use the same signing key. A missing or unreadable key file returns HTTP 401; this endpoint does not generate temporary keys.

## Node status

```bash
curl -s http://localhost:2661/api/admin/status
```

`NodeStatusResponse` contains `status`, `version`, `chains_active`, `license_active` and `uptime`. Version comes from `hierachain/config/version.py`; uptime is formatted from the manager's start time. `license_active` is currently hardcoded to `True`, not the result of a license verification service.

## Secure event submission

`SecureEventRequest` requires `entity_id`, `event_type`, `sender` and `signature`; `details` defaults to an empty object. `sender` and `signature` must contain hexadecimal data with a `0x` prefix. Optional fields are `nonce`, `timestamp` and `chain_id`; unknown fields are rejected. Details are limited to 1 MiB of serialized JSON and depth 10.

The handler rejects a supplied `chain_id` that differs from the path, and a supplied timestamp more than 300 seconds from server time. It calls `SignatureVerifier.verify_event_signature()` before `chain.add_event()`.

`SecureEventResponse` contains `status`, `event_hash` and server `timestamp`. Although the literal status is `committed`, the handler calls the asynchronous Sub-Chain ingestion path. `event_hash` is the returned submission identifier; read finalized blocks to establish durable commitment. A signature accepted at this route does not make block creation synchronous.

## Status codes

| Code | Meaning |
|:-----|:--------|
| 200 | Successful handler response |
| 401 | API-key authentication fails or the identity provider cannot load its key |
| 403 | Authenticated key lacks the required scope |
| 404 | Secure-event target chain does not exist |
| 422 | Invalid request model, chain mismatch, timestamp window or event signature |
| 500 | Signing, status computation or event submission raises an internal error |

## Related

* [Config](config.md)
* [Security](../modules/security.md)
* [Event Submission](../workflows/event-submission.md)
