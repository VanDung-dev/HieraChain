---
title: "AI Context Definition - HieraChain"
description: "Core instructions (System Instructions) for AI to prevent hallucinations and guide thinking in the HieraChain project."
icon: material/robot
---

# AI Context Definition - HieraChain

!!! abstract "System Prompt for AI Assistants"
    This file contains core instructions (System Instructions) to guide AI thinking when working with HieraChain. For detailed and complete technical guidance for Coding Agents, please refer to **AGENTS.md** (located in the project root).

## Project Nature

**HieraChain IS:**

* An **Enterprise** Blockchain Ledger.
* Focused on **Data Audit**, Traceability, and Integrity.
* Hierarchical architecture (Main Chain - Sub Chain) for Scalability.
* Uses **Apache Arrow** as core data structure.

**HieraChain IS NOT:**

* **NOT** a Cryptocurrency.
* **NO** Token, Coin, Gas Fee, Mining, Wallet, Address.
* **NOT** used for Payment.

## Forbidden Rules

When analyzing source code or writing documentation, AI must **ABSOLUTELY NOT** use or imply the following concepts:

| Forbidden Concept | Replace with | Reason |
|---|---|---|
| Mining | **Ordering / Validation** | HieraChain uses Ordering Service and authorized Node Validators. |
| Gas Fee | **Resource Quota / Throughput** | Enterprise pays infrastructure costs, not per-transaction fees. |
| Wallet / Address | **Identity (MSP ID) / Certificate** | Identity is based on PKI/CA, not anonymous wallet addresses. |
| Token / Coin | **Asset / Record / State** | Data is information assets, not currency. |
| Smart Contract (ETH style) | **Domain Contract / Chaincode** | Business logic (Python class), not EVM virtual machine. |

## Source Code Context

Event validation includes a recursive check for standalone cryptocurrency terms in dictionary keys and values.

* **File**: `hierachain/core/utils.py`
* **Function**: `validate_no_cryptocurrency_terms`
* **Logic**: `validate_no_cryptocurrency_terms()` returns `False` when it finds a forbidden term. `validate_event_structure()` also returns `False` for invalid events; each caller decides how to report rejection.

```python
# Terms matched as standalone words by validate_no_cryptocurrency_terms
crypto_terms = [
    "transaction", "mining", "coin", "token", "wallet", "address",
    "sender", "receiver", "amount", "fee", "reward", "coinbase",
]
```

## Thinking Guidance

When users ask about "Consensus":

* **Don't think of**: Proof of Work (Bitcoin), Proof of Stake (Ethereum).
* **Think of**: Raft, Paxos, PBFT, Proof of Authority (PoA), Proof of Federation (PoF).

When users ask about "Ledger":

* **Don't think of**: Account Balance.
* **Think of**: Event Log, Audit Trail.
