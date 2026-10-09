# Developer guide

Run the commands in this guide from the repository root unless a linked procedure specifies a separate working directory. Runtime behavior and signatures come from `hierachain/`; see the [codebase reference](CODEBASE_REFERENCE.md) and paired [English](en/) / [Vietnamese](vi/) documentation.

## Install the development environment

The Python CI matrix covers 3.10, 3.11, 3.12, 3.13 and 3.14 on Ubuntu. The commands below use a Linux/macOS shell. Native Windows server startup is not covered by that matrix; `python -m hierachain` imports `uvloop` unconditionally.

From a source checkout, use the locked dependencies:

```bash
uv sync --frozen --extra dev
source .venv/bin/activate
python --version
```

`uv sync` creates or reuses `.venv`. The `dev` extra supplies pytest, Bandit, pip-audit, Semgrep, Ruff and packaging tools. The `doc` extra supplies Zensical:

```bash
uv sync --frozen --extra dev --extra doc
```

Without uv, create a virtual environment and install the package and extras:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,doc]"
```

This pip installation resolves dependency constraints from `pyproject.toml`; it does not install from `uv.lock`. Keep the environment activated for the following `python`, `hrc` and `zensical` commands. See [Installation](en/getting-started/install.md) · [Cài đặt](vi/getting-started/install.md).

## Configure signing and storage before starting the server

Complete the [local signing identity and SQLite setup](en/getting-started/quickstart.md) · [thiết lập cục bộ](vi/getting-started/quickstart.md) first. Run its identity setup and ledger example in the same empty working directory. It provisions a stable signing/transport identity, trusted public-key map and environment variables before importing HieraChain.

SQLite/PostgreSQL are the durable hierarchy backends. Keep both the database and per-chain ordering journals for recovery. CLI chain/event commands require durable storage. Redis cannot serve as the hierarchical signed-block backend.

With that environment configured:

```bash
python -m hierachain
```

The default API URL is `http://localhost:2661`; interactive API documentation is at `/docs`. `/api/ledger/health` checks liveness, while `/api/ledger/ready` initializes/checks hierarchy recovery. Event acceptance acknowledges ordering; query finalized blocks before relying on a proof anchor.

The isolated quickstart disables API-key authentication and P2P. Production requires authentication, provisioned API keys and signing identities. See [Configuration](en/reference/config.md) · [Cấu hình](vi/reference/config.md).

## Import the package and inspect CLI commands

```python
from hierachain.core.block import Block
from hierachain.core.blockchain import Blockchain
```

Importing these classes does not provision an identity or create a usable ledger. Use the configured quickstart when constructing a chain.

```bash
hrc --help
hrc chain --help
hrc event --help
hrc node --help
hrc verify --help
```

The CLI uses the configured SQLite/PostgreSQL hierarchy rather than a separate JSON history cache. `chain create` supports `--parent main`; nested parents are unsupported. See [CLI](en/modules/cli.md) · [CLI tiếng Việt](vi/modules/cli.md).

## Run focused tests

Install the `dev` extra, then run one test file at a time:

```bash
python -m pytest tests/unit/core/test_block.py -v
```

The suite is organized under `tests/unit/`, `tests/integration/` and `tests/scenarios/`; deployment stress tests live under `docker/stress/`. Some tests require external services or isolated storage. Follow [Testing](en/dev/testing.md) · [Kiểm thử](vi/dev/testing.md) for fixture requirements and supported commands.

## Run analysis tools

These tools inspect different parts of the project; their output does not establish that runtime behavior or deployment security is correct.

### Repository checks and benchmarks

```bash
python -m scripts.static_analysis
python scripts/benchmark_hashing.py
```

`scripts.static_analysis` runs the repository's source-analysis checks. The hashing benchmark compares hashing work; use the [performance guide](en/guides/performance.md) · [hướng dẫn hiệu năng](vi/guides/performance.md) to measure committed-event throughput and latency.

### Bandit

```bash
python -m bandit -r hierachain/
python -m bandit -r hierachain/ -ll
python -m bandit -r hierachain/ -f json -o bandit_report.json
```

`-ll` restricts findings to medium/high severity. The JSON command writes a generated report; keep it out of commits.

### Dependency audit

```bash
python -m pip_audit
python -m pip_audit --strict
```

pip-audit checks installed dependencies against the selected advisory service. `--strict` also fails if dependency collection fails; it is not a switch that enables vulnerability detection. These commands use an external advisory service.

### Semgrep

```bash
semgrep --config=auto hierachain/
semgrep --config=p/owasp-top-ten hierachain/
```

The selected rules determine the source checks; remote registry configurations require network access. Review findings against the code and its callers.

Security probes in `scripts/security/` send requests to a running server. Run them only against an isolated local server. See [developer scripts](../scripts/README.md).

## Build and preview documentation

Install the `doc` extra and run from the repository root:

```bash
zensical serve -f zensical.toml
```

Build English first, then Vietnamese, because the English build owns the parent `site/` directory:

```bash
zensical build -f zensical.toml --strict
zensical build -f zensical.vi.toml --strict
```

The configured sources are `docs/en/` and `docs/vi/`; outputs are `site/` and `site/vi/`. This developer guide, `CODEBASE_REFERENCE.md` and `ARCHITECTURE.md` sit outside those locale source directories. A successful locale build does not validate their contents.

Preserve EN/VI front matter and mirror source paths, API fields, examples and diagrams when updating the locale pages. See [documentation build guide](README.md).

## Demos and deployment utilities

The current `demo/` scripts are `demo.py`, `demo_explorer.py`, `demo_ipfs.py` and `demo_zmq_consensus.py`. Read [demo prerequisites](../demo/README.md) before running them. Private-collection models and BFT demos do not enable REST private-data storage or make BFT the hierarchical consensus backend.

The unified deployment script provides Docker Compose and Kubernetes setup/stress workflows. Use an isolated deployment and inspect the [Docker guide](../docker/README.md) before running:

```bash
bash docker/hierachain.sh setup docker
bash docker/hierachain.sh stress docker --reuse
```

The Kubernetes environment in this wrapper targets OrbStack; it is not an application-managed namespace-per-Sub-Chain feature.

## Build packages

```bash
uv build
python -m twine check dist/*
```

Package artifacts are generated under `dist/`; do not commit them. Publishing is a separate action using the configured PyPI credentials:

```bash
python -m twine upload dist/*
```

## Quick reference

| Task | Command |
| --- | --- |
| Install locked development dependencies | `uv sync --frozen --extra dev` |
| Add documentation tools | `uv sync --frozen --extra dev --extra doc` |
| Run API after provisioning | `python -m hierachain` |
| Inspect CLI | `hrc --help` |
| Run one unit-test file | `python -m pytest tests/unit/core/test_block.py -v` |
| Source analysis | `python -m scripts.static_analysis` |
| Dependency audit | `python -m pip_audit` |
| Build English docs | `zensical build -f zensical.toml --strict` |
| Build Vietnamese docs | `zensical build -f zensical.vi.toml --strict` |
| Build and check package | `uv build`, then `python -m twine check dist/*` |
