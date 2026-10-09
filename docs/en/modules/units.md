---
title: "Versioning Module"
description: "System version management: PEP 440 compliance, semantic versioning tuples, and version formatting in hierachain/config/version.py."
icon: material/numeric
---

# Versioning Module (`hierachain/config/version.py`)

## 1. Overview

The versioning module defines the release version for HieraChain. It formats a structured version tuple into a standard string following PEP 440 specifications, keeping Core, API, SDK, and CLI components synchronized on release metadata.

## 2. Version tuple structure

HieraChain defines the current system version as a five-element tuple in `hierachain/config/version.py`:

```python
VERSION: tuple[int, int, int, str, int] = (0, 2, 0, "final", 0)
```

The tuple elements represent:

* Major: Increments on backward-incompatible API or architecture changes.
* Minor: Increments when adding backward-compatible features.
* Micro: Increments for backward-compatible bug fixes.
* Release level: Development status indicator (`dev`, `alpha`, `beta`, `rc`, or `final`).
* Serial: Sub-release sequence number for pre-releases.

## 3. Formatting functions

The module provides formatting helpers to convert the tuple into a standard version string:

* `final` releases omit the suffix, producing clean semantic strings such as `0.2.0`.
* Pre-release levels append standard PEP 440 suffixes, such as `-alpha1` or `-beta2`.
* `dev` levels use `.devN` when serial is positive, or `.dev` when serial is zero.

## 4. Usage in code

```python
from hierachain.config.version import get_version, VERSION, __version__

# Current version string
print(f"HieraChain Version: {__version__}")

# Explicit tuple formatting
custom_version = (0, 2, 0, "beta", 1)
print(f"Formatted Version: {get_version(custom_version)}")
```

## Related

* [System Configuration](./config.md)
* [API Administration](./api.md)
* [CLI Tool](./cli.md)
