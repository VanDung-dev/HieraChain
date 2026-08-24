# Changelog Maintenance Rules

When updating or maintaining project changelogs ([docs/en/changelog.md](/docs/en/changelog.md) & [docs/vi/changelog.md](/docs/vi/changelog.md)):

* **Scope Constraint**: Only include changes made directly to the core `hierachain/` Python library package (API, Consensus, Core, Security, State, Network, Database, Storage, SDK, etc.).
* **Exclude Non-Library Items**: Do **NOT** log changes related to documentation (`docs/`), test files (`tests/`), stress test framework, or container deployment scripts (`docker/`, `k8s/`).
* **1:1 Parity**: Always maintain exact 1:1 structural and entry parity between the English (`docs/en/changelog.md`) and Vietnamese (`docs/vi/changelog.md`) changelogs.
* **Highlight Breaking Changes**: Clearly flag breaking API changes, parameter renames, or backward-incompatible schema modifications under `??? warning "Breaking Changes"`.
