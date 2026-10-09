---
title: Deployment Architecture
description: HieraChain deployment models, ZMQ network configuration, Kubernetes resources and current operational limitations.
icon: material/server-network
---

# Deployment Architecture

## Runtime boundaries

An API process initializes a `HierarchyManager` with MainChain and registered Sub-Chains. MainChain/Sub-Chain use PoA or PoF; the BFT engine is a separate component requiring explicit integration. Deploying four API replicas alone does not establish PBFT finality or leader failover. See [Consensus scope](../workflows/consensus_mechanisms.md).

## Network and configuration

| Setting | Runtime default | Purpose |
|---------|-----------------|---------|
| `HRC_API_PORT` | `2661` | REST, GraphQL and WebSocket API |
| `HRC_P2P_PORT` | `5555` | ZeroMQ transport; container manifests override it |
| `HRC_PEERS` | Empty | Comma-separated seed peers; `peer-id@host:port` identifies a peer |
| `HRC_P2P_ENABLED` | `true` | Starts the API lifecycle's network layer |

Use `python -m hierachain` or `hrc node start`. Provision distinct identities, trusted block keys, production API keys and SQL credentials before startup. A health response is liveness; readiness uses `/api/ledger/ready`. Keep the database and each node's `data/` journals persistent. Shared SQL registry storage does not remove the ordering journal's writer ownership requirements.

Terminate HTTPS and configure public access limits at the gateway. Restrict P2P access to the intended network. `ProductionSettings` sets `P2P_TRUST_POLICY = "strict"` and `P2P_REQUIRE_SIGNATURES = True`, but the current API P2P startup path passes seed nodes and transport keys to `NetworkClient` without wiring either setting into that runtime. These values alone do not enforce strict peer trust or message-signature verification there. Optional IPFS requires its daemon and a real 32-byte encryption key. See [Secure deployment](../how-to/secure-deployment.md) and [Configuration](../reference/config.md).

## Kubernetes assets

`docker/k8s/` contains Deployment/StatefulSet, service, storage and configuration examples. The base kustomization uses the `hierachain` namespace; `templates/` contains separate Sub-Chain templates. `HierarchyManager` does not create namespaces or pods when a Python Sub-Chain is created. Namespace boundaries alone do not isolate CPU, memory or network traffic; requests/limits and network policy must be configured at deployment.

Resources depend on the manifest: `node-deployment.yaml` uses 1 CPU/1 GiB requests and limits, while `node-statefulset.yaml` requests 500m CPU/1 GiB and limits 2 CPU/2 GiB. These are manifest values, not runtime requirements or tested capacity guarantees.

Review the chosen manifest before deployment. For example, `node-deployment.yaml` currently invokes `hrc start`, while the CLI provides `hrc node start`; it also contains an IPFS encryption-key placeholder. The StatefulSet has separate identity secret mounts. These files are deployment examples, not a complete provisioned production environment. This documentation update does not modify or validate the cluster manifests.

## Related

* [Recovery](../how-to/disaster-recovery.md)
* [Testing and isolated deployment workloads](../dev/testing.md)
