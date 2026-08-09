# Plugin Layer & Architectural Philosophy

HieraChain is designed as a **Plugin Layer** for existing enterprise Web2 infrastructure, not a standalone network application.

## Core Architectural Rules
* **Do NOT implement over-engineered transport security**: Do NOT add internal TLS/SSL handling, WAF, firewalls, network filtering, or transport-level certificate management. These layers already exist in the Web2 enterprise reverse proxy/API Gateway.
* **Focus on Blockchain Core Value**: Focus exclusively on Immutability, Distributed Trust, Tamper Evidence, Non-repudiation, and BFT/PoF Consensus.
* **Python Latency Constraint**: Keep code minimal and fast (~10-20ms base latency). Avoid adding internal encryption layers or mTLS that add unnecessary CPU/latency overhead.
* **Design Patterns**:
  * **Facade Pattern**: Complex subsystems must expose a single coordinator class (e.g., `OrderingService`, `HierarchyManager`).
  * **Strategy Pattern**: Use for swappable algorithms (consensus, caching, splitting).
  * **Repository Pattern**: Never access DB directly from business logic; use storage adapters under `adapters/database/`.
  * **State Machine**: Lifecycle transitions must follow defined allowed states.
