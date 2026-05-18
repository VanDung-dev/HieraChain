---
title: "Frequently Asked Questions"
description: "FAQ about installation, configuration, API, security, performance, and storage for HieraChain."
icon: material/frequently-asked-questions
---

# Frequently Asked Questions (FAQ)

!!! question "What port does the API run on by default?"
    Default is 2661 (see `hierachain/config/settings.py`).

!!! question "How do I enable API key authentication?"
    Set `HRC_AUTH_ENABLED=true` and send the `X-API-Key` header (or custom name per `API_KEY_NAME`).

!!! question "What's the difference between Main Chain and Sub-Chain?"
    Main Chain stores proofs; Sub-Chain stores detailed domain event data.

!!! question "Why doesn't the event have a client-sent timestamp?"
    The server generates the timestamp upon receipt for time source consistency.

!!! question "What type should `details` be?"
    Map<string,string>; non-string values will be converted to strings.

!!! question "Creating a Sub-Chain reports invalid name?"
    Names can only contain `[a-zA-Z0-9_\-]` (see validation in `api/v1/endpoints.py`).

!!! question "Why is the block from my Sub-Chain not visible after proof submission?"
    Check block finalization conditions, time/batch event thresholds; try resubmitting or check logs.

!!! question "Poor performance or 503 errors?"
    Check `ResourceGuardMiddleware`, enable advanced caching, optimize batch size, check CPU/RAM.

!!! question "Is there an API v2 and what is it for?"
    Yes; for managing channels, private data, contracts, organizations. See `docs/en/reference/api-v2.md`.

!!! question "Where is the CLI and how do I use it?"
    The `hrc` command (registered in `pyproject.toml`). See `docs/en/modules/cli.md`.

!!! question "Can I use Redis/SQLite as a backend?"
    Yes; configure via `DEFAULT_STORAGE_BACKEND`, `DATABASE_URL`, `REDIS_*`.

!!! question "How do I contribute source code?"
    See `docs/en/dev/contributing.md`.

!!! question "How are tests organized and run?"
    Markers/paths in `pyproject.toml`. See `docs/en/dev/testing.md`.

!!! question "Release process?"
    Based on `setuptools_scm`; see `docs/en/dev/release-process.md`.
