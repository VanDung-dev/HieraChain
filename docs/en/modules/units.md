---
title: "Units & Versioning Module"
description: "System version management: PEP 440 compliance, Semantic Versioning, and Project development status."
icon: material/numeric
---

# Units Module (`hierachain/units/*`)

## Overview

The **Units** module is responsible for managing the HieraChain versioning system. It ensures the entire system (from Core, API to CLI) is always version-synchronized and compliant with modern software packaging standards such as **PEP 440**.

---

## Version Structure (Version Tuple)

HieraChain uses a 5-component Tuple to define versions in detail:
`VERSION = (major, minor, micro, releaselevel, serial)`

*   **Major**: Major version, changes with significant architecture updates.
*   **Minor**: Minor version, changes when new features are added.
*   **Micro**: Bug fix version.
*   **Release Level**: Development status (`dev`, `alpha`, `beta`, `rc`, `final`).
*   **Serial**: Release sequence number within the same level.

---

## Key Features

<div class="grid cards" markdown>

*   :material-check-decagram:{ .lg .middle } __PEP 440 Compliance__

    ---

    Automatically converts the Version Tuple to a standard Python version string (e.g., `0.0.2-beta1` or `0.0.2` for final release).

*   :material-compare-remove:{ .lg .middle } __Version Comparison__

    ---

    Provides the `compare_versions` function supporting comparison of both strings and tuples, helping the system check compatibility between components.

*   :material-book-information-variant:{ .lg .middle } __Documentation Status__

    ---

    Determines the project status (Stable, Under Development, Release Candidate) based on the current version level.

</div>

---

## Usage Examples

### 1. Get Current Version Information
```python
from hierachain.units.version import get_version, VERSION

# Returns PEP 440 string (e.g., "0.0.2")
print(f"HieraChain Version: {get_version()}")

# Get abbreviated version (Major.Minor)
from hierachain.units.version import get_major_version
print(f"Base Version: {get_major_version()}")
```

### 2. Check Compatibility
```python
from hierachain.units.version import compare_versions

required = "0.0.1"
current = get_version()

if compare_versions(current, required) >= 0:
    print("System is compatible.")
else:
    print("Version upgrade required!")
```

---

## Release Level Hierarchy

When comparing versions, HieraChain follows this priority order (lowest to highest):
1.  `dev` (Development)
2.  `alpha` (Alpha testing)
3.  `beta` (Beta testing)
4.  `rc` (Release Candidate)
5.  `final` (Stable Release)

---

## Related

*   [System Configuration](./config.md)
*   [API Status admin (uses versioning)](./api.md)
*   [CLI (displays version)](./cli.md)
