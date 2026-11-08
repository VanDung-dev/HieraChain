---
title: "API Business"
description: "API business endpoint summary and curl examples — aligned with hierachain/api/business/*."
icon: material/numeric-2-circle
---

# API Business

API Business provides channel, private-collection, and organization endpoints backed by the hierarchical organization service.

## Source Code Components

* Router/Endpoints: `hierachain/api/business/router.py`
* Schemas: `hierachain/api/business/schemas.py`
* Server integration: `hierachain/api/server.py` (registers Business router)

## Main Endpoints

```mermaid
sequenceDiagram
    participant User
    participant API as API business
    participant Channel as Channel

    User->>API: POST /channels
    API->>Channel: Create channel
    API-->>User: Channel ID

    User->>API: POST /channels/{id}/private-collections
    API->>Channel: create_private_collection(...)
    API-->>User: OK

    User->>API: POST /organizations
    API-->>User: Organization ID
```

* `GET  /api/business/health`: service health check.
* `POST /api/business/channels`: create a channel. Requires `chains` and `channels:manage` API key permissions.
* `GET  /api/business/channels/{channel_id}`: get channel info.
* `POST /api/business/channels/{channel_id}/private-collections`: create a private collection in the channel. The request is delegated to `Channel.create_private_collection(...)`; collection members must belong to the channel.
* `POST /api/business/organizations`: register an organization. Requires `chains` and `organizations:manage`; the verified API key user becomes its first administrator.
* `POST /api/business/organizations/{org_id}/members`: an organization administrator registers a member with role `admin` or `member`. The member ID must match that member's API key user ID.
* `GET  /api/business/organizations/{org_id}`: get organization info.

## Provisioning and permissions

Provisioning requires API key authentication to be enabled. A trusted operator assigns `organizations:manage` and `channels:manage` scopes when provisioning API keys; these routes do not issue keys. Organization creation also requires `chains`, and the key's verified user ID becomes the first organization administrator. Member registration requires `chains` and an existing organization administrator. Channel creation requires `chains` and `channels:manage`. Event submission uses the authenticated API key user ID and channel role policy.

The organization, member, and channel registry is saved and restored through configured SQLite, PostgreSQL or `RedisLedgerAdapter` storage. Redis ledger startup requires [durable AOF configuration](../modules/storage.md#redis-ledger). The in-memory backend is process-local. `ca_config` is retained as API-process metadata and is not used to verify member certificates. Direct Python channel and private-collection methods accept organization IDs as endorsements and require a trusted caller; they do not verify endorsement signatures.

```bash
ORG_PROVISIONER_KEY=replace-me
ORG_ADMIN_KEY=replace-me
CHANNEL_PROVISIONER_KEY=replace-me

curl -s -X POST http://localhost:2661/api/business/organizations \
  -H 'X-API-Key: '"$ORG_PROVISIONER_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"org_id": "orgA", "ca_config": {}}'

curl -s -X POST http://localhost:2661/api/business/organizations/orgA/members \
  -H 'X-API-Key: '"$ORG_ADMIN_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"member_id": "userB", "role": "member"}'

curl -s -X POST http://localhost:2661/api/business/channels \
  -H 'X-API-Key: '"$CHANNEL_PROVISIONER_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"channel_id": "test_channel", "organizations": ["orgA"], "policy": {"read": "MEMBER", "write": "ADMIN", "endorsement": "MAJORITY"}}'
```

Event submissions also require the `events` API key permission.

## Curl Examples

```bash
# Health
curl -s http://localhost:2661/api/business/health

# Create channel
curl -s -X POST http://localhost:2661/api/business/channels \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: '"$CHANNEL_PROVISIONER_KEY" \
  -d '{"channel_id": "test_channel", "organizations": ["orgA"], "policy": {"read": "MEMBER", "write": "ADMIN", "endorsement": "MAJORITY"}}'

# Get channel
curl -s http://localhost:2661/api/business/channels/test_channel \
  -H 'X-API-Key: '"$CHANNEL_PROVISIONER_KEY"

# Create private collection for channel
curl -s -X POST \
  http://localhost:2661/api/business/channels/test_channel/private-collections \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: '"$CHANNEL_PROVISIONER_KEY" \
  -d '{"name": "sensitive_docs", "members": ["orgA"], "config": {"block_to_purge": 1000, "endorsement_policy": "MAJORITY"}}'

# Organization
curl -s -X POST http://localhost:2661/api/business/organizations \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: '"$ORG_PROVISIONER_KEY" \
  -d '{"org_id": "orgA", "ca_config": {}}'

# Get organization
curl -s http://localhost:2661/api/business/organizations/orgA \
  -H 'X-API-Key: '"$ORG_PROVISIONER_KEY"
```

If API key authentication is enabled (production), add the header per `settings.API_KEY_NAME` (default `X-API-Key`).

## Security & Configuration

* API key authentication via `security/verify/api_key_verifier.py` (when `AUTH_ENABLED=true`).
* Identity/key/cert behavior: see Security and Modules/Security pages.
* Host/port configuration and security in `hierachain/config/settings.py`.

## Related

* API Ledger: [API Ledger](api-ledger.md)
* Security Architecture: [Security (in-depth)](../architecture/security.md)
* Modules: [API](../modules/api.md)
