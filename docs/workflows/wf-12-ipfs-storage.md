# WF-12: IPFS Encrypted Storage

**Group**: E — Operational & Integration Layer
**Trigger**: `IPFSClient.upload_json(data, encrypt=True)` — called when large/sensitive off-chain data must be stored
**Output**: `{ cid, size, encrypted: True, nonce: hex }` — CID stored on-chain, plaintext never leaves encrypted boundary
**Key modules**: `api/storage/ipfs_client.py`, `api/storage/encryption.py`

> [← WF-11: WebSocket Streaming](./wf-11-websocket-streaming.md) · [Back to Overview](../ARCHITECTURE.md) · [WF-13: Risk Alerts →](./wf-13-risk-alerts.md)

---

## Overview

Large or sensitive off-chain data (e.g., document attachments, audit evidence, binary assets) is stored on a private IPFS swarm with **mandatory AES-256-GCM encryption**. Only nodes sharing the same encryption key can decrypt. The CID returned by IPFS is stored on-chain as a reference; the plaintext never leaves the encrypted boundary.

**Key property**: Even if IPFS storage is compromised, data is unreadable without the AES-256-GCM key.

---

## Flow Diagram — Upload (Encrypt → Store → Pin)

```mermaid
sequenceDiagram
    autonumber
    participant Caller as 🖥️ API / SubChain
    participant IC as 🗄️ IPFSClient
    participant AES as 🔐 AESEncryption
    participant IPFS as 🌐 IPFS Daemon

    Caller->>IC: upload_json(data, encrypt=True, metadata)

    IC->>IC: json.dumps(data) → raw_bytes
    IC->>AES: encrypt(raw_bytes, aad=json(metadata))
    Note right of AES: AES-256-GCM<br/>nonce = random 96-bit (secrets.token_bytes(12))<br/>ciphertext = AESGCM.encrypt(nonce, plaintext, aad)<br/>output = nonce || ciphertext
    AES-->>IC: ciphertext, nonce

    IC->>IPFS: add_bytes(ciphertext)
    IPFS-->>IC: CID (Content Identifier)

    alt auto_pin=True (default)
        IC->>IPFS: pin.add(CID)
        Note right of IPFS: Prevents garbage collection
    end

    IC-->>Caller: { cid, size, encrypted: True, nonce: hex(nonce) }
    Note over Caller: Store CID + nonce on-chain for later retrieval
```

---

## Flow Diagram — Download (Retrieve → Decrypt)

```mermaid
sequenceDiagram
    autonumber
    participant Caller as 🖥️ API / SubChain
    participant IC as 🗄️ IPFSClient
    participant AES as 🔐 AESEncryption
    participant IPFS as 🌐 IPFS Daemon

    Caller->>IC: download_json(cid, encrypted=True, nonce=hex, metadata)
    IC->>IPFS: cat(cid) → ciphertext bytes
    IPFS-->>IC: ciphertext

    IC->>AES: decrypt(ciphertext, nonce_bytes, aad=json(metadata))
    Note right of AES: Verify GCM authentication tag first<br/>If tag invalid → raise DecryptionError
    AES-->>IC: plaintext bytes

    IC->>IC: json.loads(plaintext) → dict
    IC-->>Caller: Decrypted data ✅
```

---

## Error Handling — IPFS Unavailable

```mermaid
flowchart LR
    CALL["upload_json(data)"]
    CONN["Connect to IPFS daemon\n(HRC_IPFS_HOST)"]
    FAIL["❌ Connection refused\nor timeout"]
    RETRY["Retry with backoff\n(max 3 attempts)"]
    ERR["Raise IPFSConnectionError\nLog + Alert via WF-13"]
    OK["✅ CID returned"]

    CALL --> CONN
    CONN -->|Success| OK
    CONN -->|Fail| FAIL --> RETRY
    RETRY -->|Max retries| ERR
    RETRY -->|Reconnected| OK
```

---

## Step-by-Step Breakdown

| Step | Description |
|:-----|:------------|
| **1. Serialize** | `json.dumps(data)` → raw bytes |
| **2. Encrypt** | AES-256-GCM with random 96-bit nonce. AAD (additional authenticated data) = JSON-serialized metadata |
| **3. Upload** | Raw ciphertext bytes sent to IPFS daemon via `ipfshttpclient` |
| **4. Pin** | `pin.add(CID)` prevents garbage collection by IPFS GC daemon |
| **5. Return** | Caller receives `{ cid, nonce }` — both must be stored on-chain for retrieval |
| **6. Retrieve** | `cat(cid)` fetches ciphertext; `decrypt()` verifies GCM authentication tag before decrypting |

---

## Security Properties

| Property | Mechanism |
|:---------|:----------|
| Confidentiality | AES-256-GCM encryption |
| Integrity | GCM authentication tag (authenticated encryption) |
| Replay protection | Unique random 96-bit nonce per upload |
| Key management | `HRC_IPFS_ENCRYPTION_KEY` env var; auto-generated if missing |
| Access control | Policy Engine (WF-10) gates upload/download API calls |

---

## Key Classes & Methods

| Step | Class / Method | File |
|:-----|:--------------|:-----|
| Upload entry | `IPFSClient.upload_json()` | `api/storage/ipfs_client.py` |
| Encrypt | `AESEncryption.encrypt()` | `api/storage/encryption.py` |
| Upload raw bytes | `IPFSClient.upload_bytes()` | `api/storage/ipfs_client.py` |
| Pin | `IPFSClient.pin()` | `api/storage/ipfs_client.py` |
| Download & decrypt | `IPFSClient.download_json()` | `api/storage/ipfs_client.py` |
| Factory | `create_ipfs_client_from_env()` | `api/storage/ipfs_client.py` |

---

## See Also

- [WF-10: Policy Enforcement](./wf-10-policy-enforcement.md) — gates upload/download authorization
- [WF-13: Risk Analysis & Alerts](./wf-13-risk-alerts.md) — IPFS connection failure triggers alerts
- [WF-16: Key Backup](./wf-16-key-backup.md) — same AES-256-GCM pattern used for key backup encryption
