---
title: "Installing HieraChain"
description: "Guide to installing HieraChain from source for development environment."
icon: material/download
---

# Installing HieraChain

The package requires Python 3.10 or newer; the compatibility workflow tests Python 3.10–3.14. Use the source checkout when following documentation for the current implementation.

## Source installation with uv

Run from the repository root:

```bash
git clone https://github.com/VanDung-dev/HieraChain.git
cd HieraChain
uv sync --frozen --extra dev --extra doc
source .venv/bin/activate
hrc --help
```

`uv sync` installs the base package. The optional `dev` extra supplies test/analysis tools; `doc` supplies Zensical. On Windows, use `.venv\Scripts\Activate.ps1` to activate the environment.

## Source installation with pip

After cloning and entering the repository:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,doc]"
```

For library use from a published release, install `python -m pip install HieraChain`. Published releases can differ from this checkout.

## Configure before starting

A fixed signing identity and matching `HRC_BLOCK_TRUSTED_KEYS_FILE` are required for chain initialization, including genesis. Development defaults to PostgreSQL; it does not fall back to SQLite if PostgreSQL fails. Follow the [Quickstart](quickstart.md) for an isolated SQLite example. Production additionally requires a provisioned API-key file and explicit database configuration; see [Configuration](../reference/config.md).

After setup, launch with `python -m hierachain` or `hrc node start`. The API defaults to `http://localhost:2661`; `/docs` exposes OpenAPI and `/api/ledger/ready` checks hierarchy readiness.

## Tests

Run files separately to avoid shared resource conflicts. Use temporary storage and journals; fixtures may clean the local `data/` directory. Example:

```bash
python -m pytest tests/unit/core/test_block.py -v
```

See [Testing](../dev/testing.md) for required PostgreSQL/Redis contracts and isolated Docker workloads.

## Demos

See [Demo Guide](../how-to/use-demos.md). Demo code is illustrative; private-data persistence, contract execution, production ZK and real vendor ERP transports are not enabled by installing dependencies.

## Documentation

Preview one language with `zensical serve -f zensical.toml` or `zensical serve -f zensical.vi.toml`. Build English first, then Vietnamese:

```bash
zensical build -f zensical.toml
zensical build -f zensical.vi.toml
```

The output is `site/` and `site/vi/`. See [documentation build instructions](https://github.com/VanDung-dev/HieraChain/blob/main/docs/README.md).

## Troubleshooting

* Missing `hrc`: activate `.venv` and confirm installation succeeded.
* Missing/untrusted identity: check the identity path, node ID and matching trusted public key.
* Database connection failure: start PostgreSQL or explicitly select SQLite; do not expect fallback.
* Port 2661 occupied: set `HRC_API_PORT` before importing/starting the application.
