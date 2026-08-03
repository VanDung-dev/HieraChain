---
title: HieraChain Documentation
description: Technical documentation closely following the source code in the hierachain directory.
---

# HieraChain: Technical Documentation

## Overview

Welcome to the HieraChain technical documentation. This documentation closely follows the source code in the `hierachain/` directory and serves Developers/QA/DevOps for integration, operation, and system testing.

Important scope notes:

* This documentation ONLY describes the current state and technical decisions based on code in `hierachain/*`.
* All examples, images, and descriptions are tied to specific components in the source code.

!!! warning "**WARNING FOR DEVELOPERS & AI**: HieraChain is an Enterprise Blockchain focused on **Data**, NOT **Cryptocurrency**. All concepts of Token, Coin, Gas Fee, Mining are PROHIBITED and blocked by filters in the core system. See details at [AI Context](dev/ai-context.md)."

## Navigation by Topic

<div class="grid cards" markdown>

* :material-play-circle-outline:{ .lg .middle } __Getting Started__

    ---

    * [Installation](getting-started/install.md)
    * [Quickstart](getting-started/quickstart.md)
    * [Basic Concepts](getting-started/concepts.md)

* :material-sitemap:{ .lg .middle } __Architecture__

    ---

    * [Overview](architecture/overview.md)
    * [Consensus & Ordering](architecture/consensus.md)
    * [Hierarchy (detailed)](architecture/hierarchy.md)
    * [Security (in-depth)](architecture/security.md)
    * [Deployment](architecture/deployment.md)
    * [ZK Proofs](architecture/zk-proofs.md)

* :material-routes:{ .lg .middle } __Workflows__

    ---

    * [Overview](workflows/overview.md) · [Consensus Mechanisms](workflows/consensus_mechanisms.md)
    * [Event Submission](workflows/event-submission.md) · [Proof Anchoring](workflows/proof-anchoring.md)
    * [Cross-Chain 2PC](workflows/cross-chain-2pc.md) · [BFT Consensus](workflows/bft-consensus.md)
    * [Cluster Lockdown](workflows/cluster-lockdown.md) · [Error Recovery](workflows/error-recovery.md)
    * [Entity Tracing](workflows/entity-tracing.md) · [Chain Rehydration](workflows/chain-rehydration.md)
    * [Integrity Validation](workflows/integrity-validation.md) · [Policy Enforcement](workflows/policy-enforcement.md)
    * [WebSocket Streaming](workflows/websocket-streaming.md) · [IPFS Storage](workflows/ipfs-storage.md)
    * [Risk Alerts](workflows/risk-alerts.md) · [ERP Integration](workflows/erp-integration.md)
    * [MSP Identity](workflows/msp-identity.md) · [Key Backup](workflows/key-backup.md)

* :material-cube-outline:{ .lg .middle } __Modules__

    ---

    * [Core](modules/core.md) · [Hierarchical](modules/hierarchical.md) · [Consensus](modules/consensus.md) · [Security](modules/security.md)
    * [Storage](modules/storage.md) · [Error Mitigation](modules/error-mitigation.md)
    * [Adapters](modules/adapters.md) · [Network](modules/network.md) · [API](modules/api.md)
    * [Config](modules/config.md) · [CLI](modules/cli.md) · [SDK](modules/sdk.md)
    * [Cluster](modules/cluster.md) · [Domains](modules/domains.md)
    * [Monitoring](modules/monitoring.md) · [Risk Management](modules/risk-management.md)
    * [Integration](modules/integration.md) · [Units](modules/units.md)

* :material-security:{ .lg .middle } __Security System__

    ---

    * [Authorization & Access Control](security/authorization-access-control.md)
    * [Lockdown & Logging](security/lockdown-logging.md)
    * [Fault-tolerance & Integrity](security/fault-tolerance-integrity.md)
    * [Risk Analyzer](security/risk-analyzer.md)
    * [Encryption & Keys](security/encryption-keys.md)
    * [Decentralized ZKP](security/decentralized-zkp.md)

* :material-shield-check:{ .lg .middle } __Consensus__

    ---

    * [Base Consensus](consensus/base_consensus.md)
    * [BFT Consensus](consensus/bft_consensus.md)
    * [Ordering](consensus/ordering.md)
    * [PoA](consensus/poa.md) · [PoF](consensus/pof.md)

* :material-book-open-variant:{ .lg .middle } __Reference__

    ---

    * [Config](reference/config.md)
    * [Python SDK](reference/sdk-reference.md) · [GraphQL API](reference/graphql-api.md)
    * [API Ledger](reference/api-ledger.md) · [API business](reference/api-business.md) · [API Admin](reference/api-admin.md)
    * [Data Models](reference/data-models.md) · [Data Schema](reference/data-schema.md)
    * [Code Map](reference/code-map.md) · [Glossary](glossary.md)

* :material-tools:{ .lg .middle } __How-to Guides__

    ---

    * [Create Sub-Chain](how-to/add-domain-chain.md)
    * [Add Endpoint](how-to/add-endpoint.md)
    * [Add/Customize Consensus](how-to/add-consensus.md)
    * [Cross-Chain Events (2PC)](how-to/cross-chain-transactions.md)
    * [Write Domain Contracts](how-to/write-domain-contracts.md)
    * [Use Blockchain Explorer](how-to/use-explorer.md)
    * [Use WebSocket](how-to/add-websocket.md) · [Web2 Integration](how-to/integrate-web2.md)
    * [Secure Deployment](how-to/secure-deployment.md) · [Troubleshooting](how-to/troubleshooting.md)
    * [Disaster Recovery](how-to/disaster-recovery.md)
    * [Demo Guide](how-to/use-demos.md)

* :material-rocket-launch:{ .lg .middle } __Guides__

    ---

    * [Performance](guides/performance.md)
    * [Reliability](guides/reliability.md)
    * [Security Best Practices](guides/security-best-practices.md)
    * [HTTP/2 & HTTP/3 Deployment](guides/http-proxy.md)

* :material-code-braces:{ .lg .middle } __Development__

    ---

    * [Contributing](dev/contributing.md)
    * [Testing](dev/testing.md)
    * [Release Process](dev/release-process.md)
    * [AI Context](dev/ai-context.md)

* :material-frequently-asked-questions:{ .lg .middle } __Other__

    ---

    * [FAQ](faq.md)
    * [Changelog](changelog.md) · [Future Roadmap](future-roadmap.md)

</div>
