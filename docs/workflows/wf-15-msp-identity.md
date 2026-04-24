# WF-15: MSP Identity & Authorization

**Group**: F — Security Identity & Key Management
**Trigger**: Entity onboarding (registration), runtime API calls requiring authorization, or certificate lifecycle management
**Output**: `True` (identity confirmed + action authorized) or `False` / exception (rejected)
**Key modules**: `security/msp.py`, `security/identity.py`

> [← WF-14: ERP Integration](./wf-14-erp-integration.md) · [Back to Overview](../ARCHITECTURE.md) · [WF-16: Key Backup →](./wf-16-key-backup.md)

---

## Overview

HieraChain uses two identity layers:

| Layer | Class | Use Case |
|:------|:------|:---------|
| **Simple RBAC** | `IdentityManager` | Single-org deployments; role-based permission checks |
| **Enterprise MSP** | `HierarchicalMSP` | Multi-org consortiums; X.509 certificate hierarchy with `CertificateAuthority` |

Every entity must be registered and have its identity validated before being permitted to call `PolicyEngine` (WF-10) or submit events (WF-1).

---

## Flow Diagram — Entity Onboarding (Enterprise MSP)

```mermaid
sequenceDiagram
    autonumber
    participant Admin as 🏢 Enterprise Admin
    participant MSP as 🏛️ HierarchicalMSP
    participant CA as 📜 CertificateAuthority
    participant PE as ⚖️ PolicyEngine (WF-10)

    Note over Admin: Phase 1 — Define roles

    Admin->>MSP: define_role(role_name, permissions, policy_ids)
    MSP->>MSP: OrganizationPolicies.assign_role_permissions(role, perms)

    Note over Admin: Phase 2 — Register entity

    Admin->>MSP: register_entity(entity_id, credentials, role, attributes)
    MSP->>CA: issue_certificate(entity_id, public_key, attributes, valid_days)
    CA->>CA: _generate_cert_id(entity_id, public_key)
    CA->>CA: _sign_certificate(cert_id, subject, public_key, ca_key)
    CA-->>MSP: Certificate { cert_id, valid_until, status=ACTIVE }
    MSP->>MSP: entities[entity_id] = { certificate, role, status: active }
    MSP-->>Admin: True ✅
```

---

## Flow Diagram — Runtime Authorization

```mermaid
sequenceDiagram
    autonumber
    participant Caller as 🖥️ API Client
    participant MSP as 🏛️ HierarchicalMSP
    participant CA as 📜 CertificateAuthority
    participant PE as ⚖️ PolicyEngine (WF-10)

    Caller->>MSP: validate_identity(entity_id, credentials)
    MSP->>CA: verify_certificate(cert_id)
    CA->>CA: Check: cert not revoked AND is_valid() (within time window)
    CA-->>MSP: True / False
    MSP->>MSP: Match credentials.public_key vs stored certificate
    MSP-->>Caller: True ✅ (identity confirmed)

    Caller->>MSP: authorize_action(entity_id, action, resource)
    MSP->>MSP: check_permission(role, action)
    MSP->>MSP: evaluate_policy(policy_id, context) for each role policy
    MSP-->>Caller: True / False

    alt Action authorized
        Caller->>PE: evaluate_policy(policy_id, context_with_role)
        Note right of PE: WF-10 flow continues here
    end
```

---

## Flow Diagram — Certificate Revocation

```mermaid
sequenceDiagram
    autonumber
    participant Admin as 🏢 Enterprise Admin
    participant MSP as 🏛️ HierarchicalMSP
    participant CA as 📜 CertificateAuthority

    Admin->>MSP: revoke_entity(entity_id, reason)
    MSP->>CA: revoke_certificate(cert_id, reason)
    CA->>CA: revoked_certificates.add(cert_id)
    CA->>CA: cert.status = REVOKED
    MSP->>MSP: entity[status] = revoked
    MSP-->>Admin: True ✅

    Note over CA: All future validate_identity() calls for this entity<br/>will fail at CA.verify_certificate()
```

---

## Default Roles

| Role | Permissions |
|:-----|:------------|
| `admin` | manage_entities, view_audit_log, define_policies, create_channels, manage_certificates, submit_events, view_channels, query_data |
| `operator` | submit_events, view_channels, query_data |
| `viewer` | view_data, query_data |

---

## Step-by-Step Breakdown

| Step | Description |
|:-----|:------------|
| **1. Define role** | Admin defines role + permission set + linked policy IDs |
| **2. Register entity** | MSP requests X.509 certificate from CA for the entity's public key |
| **3. CA issue** | CA generates `cert_id`, signs certificate, stores with `status=ACTIVE` |
| **4. Validate identity** | CA checks: cert not revoked AND current time within `[issued_at, valid_until]` |
| **5. Credential match** | MSP verifies `credentials.public_key == certificate.public_key` |
| **6. Authorize action** | `check_permission(role, action)` + evaluate all role-linked policies |
| **7. Policy gate** | If authorized, PolicyEngine (WF-10) evaluates further context-based rules |
| **8. Revoke** | Sets `cert.status = REVOKED`; all future `validate_identity()` calls fail at step 4 |

---

## Error Handling

| Condition | Behavior |
|:----------|:---------|
| Entity not registered | `validate_identity()` returns `False` immediately |
| Certificate expired | `CA.is_valid()` returns `False`; identity rejected |
| Certificate revoked | `CA.verify_certificate()` fails; identity rejected |
| Public key mismatch | `validate_identity()` returns `False` |
| Role has no matching permission | `authorize_action()` returns `False` |

---

## Key Classes & Methods

| Step | Class / Method | File |
|:-----|:--------------|:-----|
| Simple RBAC register | `IdentityManager.register_user()` | `security/identity.py` |
| Simple RBAC validate | `IdentityManager.validate_identity()` | `security/identity.py` |
| Signature verify | `IdentityManager.verify_user_signature()` | `security/identity.py` |
| Enterprise register | `HierarchicalMSP.register_entity()` | `security/msp.py` |
| Issue certificate | `CertificateAuthority.issue_certificate()` | `security/msp.py` |
| Validate identity | `HierarchicalMSP.validate_identity()` | `security/msp.py` |
| Authorize action | `HierarchicalMSP.authorize_action()` | `security/msp.py` |
| Revoke entity | `HierarchicalMSP.revoke_entity()` | `security/msp.py` |

---

## See Also

- [WF-10: Policy Enforcement](./wf-10-policy-enforcement.md) — called after MSP authorization succeeds
- [WF-1: Event Submission](./wf-01-event-submission.md) — `authorize_action()` gates access before `add_event()`
- [WF-16: Key Backup](./wf-16-key-backup.md) — new certificate issuance triggers key backup
