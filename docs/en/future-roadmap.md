---
title: "Future Roadmap"
description: "Technology direction: Python Free-threading and Rust Core Acceleration."
icon: material/road-variant
---

# Future Roadmap: Performance & Multi-threading (Python vs Rust)

This document addresses current Python performance issues and HieraChain's future technology direction.

## The Pure Python Problem

HieraChain is designed with a future-oriented architecture to leverage parallel processing. However, we face reality:

* **Python GIL (Global Interpreter Lock)**: Current Python versions are still limited by the GIL, making multi-core CPU utilization suboptimal for CPU-bound tasks like Blockchain Consensus.
* **Python 3.14+ (Free-threading)**: Although Python 3.13/3.14 has begun supporting "no-GIL" (Free-threading), it is **not yet stable enough** for Production in critical financial/data systems.

=> **Consequence**: If you run HieraChain in "Pure Python" mode, performance will be significantly limited under high load.

## High-Performance Solution (Rust Acceleration)

To solve the performance problem immediately without waiting for Python's Free-threading to mature, we provide alternatives based on the **Rust** language:

### Self-Managed Integration

You can use the Consensus library written in Rust:

* **Repository**: [https://github.com/VanDung-dev/HieraChain-Consensus](https://github.com/VanDung-dev/HieraChain-Consensus)
* **Description**: A high-performance Consensus library using PyO3 to communicate with Python.
* **Note**: You will need to **MANUALLY CONFIGURE** and modify code to integrate this library into the current HieraChain.

### hrc-core (Enterprise / Lazy Mode)

* **What is hrc-core?**: This is the HieraChain kernel written in **pure Rust** (Native Rust) while maintaining a Python interface (Python Bindings) for ease of use. It delivers maximum Rust performance with Python convenience.
* **Status**: Currently `hrc-core` is in testing and refinement phase.

---

*This document is intended to guide Developers who want to optimize HieraChain performance beyond current Python limitations.*
