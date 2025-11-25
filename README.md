# HieraChain Framework

![Python Versions](https://img.shields.io/badge/python-3.10%20|%203.11%20|%203.12%20|%203.13-blue)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

A general-purpose HieraChain framework designed for enterprise applications without any cryptocurrency concepts.

---

## Overview

This framework implements a multi-layer blockchain architecture where Main Chains supervise Sub-Chains, enabling scalable and secure business process management. All operations are called "events" rather than "transactions", emphasizing the business application focus.

---

## Key Features

- **Hierarchical Structure**: Main Chain supervises multiple Sub-Chains
- **Event-Based Model**: Business operations as events, not cryptocurrency transactions
- **Proof Submission**: Sub-Chains submit cryptographic proofs to Main Chain
- **Enterprise Security**: Advanced identity management and data isolation
- **Multi-Organization Support**: Secure collaboration between organizations
- **Privacy Controls**: Private data collections with access policies

---

## Architecture

```
Main Chain (Supervisor)
├── Sub-Chain 1 (Domain A)
├── Sub-Chain 2 (Domain B)
└── Sub-Chain 3 (Domain C)
```

- Main Chain stores only cryptographic proofs from Sub-Chains
- Sub-Chains handle domain-specific operations and data
- Entity identification through metadata fields, not as identifiers

---

## License

This project is licensed under the Apache License, Version 2.0 - see the [LICENSE](LICENSE) file for details.

---
