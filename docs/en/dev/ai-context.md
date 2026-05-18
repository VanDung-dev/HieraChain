---
title: "AI Context Definition - HieraChain"
description: "Core instructions (System Instructions) for AI to prevent hallucinations and guide thinking in the HieraChain project."
icon: material/robot
---

# AI Context Definition - HieraChain

!!! abstract "System Prompt for AI Assistants"
    This file contains core instructions (System Instructions) to guide AI thinking when working with HieraChain. For detailed and complete technical guidance for Coding Agents, please refer to **[AGENTS.md](../../../AGENTS.md)**.

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

The system has **Hard Enforcement** mechanisms in code to block cryptocurrency terms.

* **File**: `hierachain/core/utils.py`
* **Function**: `validate_no_cryptocurrency_terms`
* **Logic**: If an Event contains keywords like `coin`, `token`, `wallet` -> The system will refuse processing (Raise Error).

```python
# Actual excerpt from hierachain/core/utils.py
crypto_terms = [
    "mining", "coin", "token", "wallet", "address",
    "fee", "reward", "coinbase" 
    # Note: "transaction" may be used in the context of "Database Transaction",
    # but context must be carefully considered.
]
```

## Thinking Guidance

When users ask about "Consensus":

* **Don't think of**: Proof of Work (Bitcoin), Proof of Stake (Ethereum).
* **Think of**: Raft, Paxos, PBFT, Proof of Authority (PoA), Proof of Federation (PoF).

When users ask about "Ledger":

* **Don't think of**: Account Balance.
* **Think of**: Event Log, Audit Trail.
