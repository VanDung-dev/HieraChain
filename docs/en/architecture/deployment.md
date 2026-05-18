---
title: Deployment Architecture
description: HieraChain deployment models, ZMQ network configuration, and Kubernetes operations guide for High Availability.
icon: material/server-network
---

# Deployment Architecture

This document describes HieraChain deployment models in detail, how to configure the network, and system operations guidance on Kubernetes to ensure High Availability and enterprise-level scalability.

---

## 1. Multi-Node Deployment Model (BFT Topology)

HieraChain supports the BFT (Byzantine Fault Tolerance) consensus protocol to ensure the system continues operating correctly even when some nodes fail or behave maliciously.

### Standard BFT Configuration (Example: 4 Nodes)

The minimum deployment model for BFT to withstand 1 faulty node (***f=1***) requires at least ***3f + 1 = 4*** nodes.

Topology structure for a Sub-Chain:

* **Node 0 (Initial Leader)**: Receives transactions, closes blocks, and initiates consensus steps (Pre-prepare).
* **Node 1, Node 2, Node 3 (Validators)**: Participate in Prepare and Commit rounds to validate blocks.

During deployment, configure the peer list (via the `PEERS` environment variable) on each node so they form a P2P Mesh Network.

---

## 2. Network Configuration

For nodes in the network to communicate, the system uses **ZeroMQ TCP transport** and **HTTP REST API** via `FastAPI` (or manual configuration of separate API ports).

* **Default standard ports**:

    * **API Port** (`2661`): Used for GraphQL API, REST API, and external clients (SDK/CLI) to submit events to the chain. (Reference `api_port: int = 2661`).
    * **Node Port** (`5001` - `50xx`): Internal ZeroMQ (ZMQ) port for consensus (P2P), signature message exchange, and block sharing between validators. (Reference `node_port: int = 5001`).

* **Ingress / Egress Rules (Firewall Rules)**:

  * **Ingress**: Only open port `2661` to the Internet or Load Balancer if a public API is needed. Port `5001` should only be configured within the internal cloud mesh network (VPC/Subnet).
  * **Egress**: Allow nodes to make HTTP(s) calls (port `443/80`) if ERP integration is needed, and call internal ZeroMQ ports (`5001` - `50xx`) of other Nodes.

---

## 3. Kubernetes Deployment (K8s Orchestration)

For HieraChain, the Kubernetes environment is the top choice for Sub-chain management. The system integrates the **`K8sNamespaceManager`** component to provide:

* **Isolation Principle**: Each Sub-chain is allocated a separate **Namespace**. Memory leaks or resource overload in one Sub-chain will not spread to others.
* **Microservice Lifecycle**: Uses K8s Deployment to manage Pods.

### Namespace & Resource Limits Management

When creating a new Sub-chain through `HierarchyManager`, the system automatically sends a request to `K8sNamespaceManager` to allocate a Deployment with the following configuration limits (Quotas):

* **Resource Requests:**

    * **CPU:** `500m` (Ensures minimum core count needed for Arrow event processing).
    * **Memory:** `512Mi`.

* **Resource Limits:**

    * **CPU:** `1000m` (1 vCPU). Leverages `parallel_engine.py` module for multi-threading.
    * **Memory:** `1Gi` (Prevents Out-of-Memory due to In-memory Storage overflow).

### Lifecycle Management

Through the API or SDK, administrators can:

1. **Provisioning**: Call `K8sNamespaceManager.provision_sub_chain_deployment(deploy_config)` passing the number of `replicas`.
2. **Monitoring**: Monitor `ACTIVE` Pod count, retrieve `resource_quotas` via `get_namespace_resources`.
3. **Termination**: When a Sub-chain stops operating, `delete_namespace` will be called to clean up all Pods and Volumes (if any) without affecting the Main-chain.
