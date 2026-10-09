# HieraChain tests

The tests in this directory cover package behavior, interactions between modules,
and recovery, validation, and risk-management scenarios. Some cases use mocks or
in-process HTTP clients; live backend checks require separate services.

Run the commands below from the repository root, one test file at a time.

## Layout

| Path | Coverage |
| --- | --- |
| `conftest.py` | Shared test configuration, signing identity, storage isolation, and journal cleanup |
| `unit/core/` | Blocks, chains, Merkle trees, Arrow data, hashing, and storage formats |
| `unit/consensus/`, `unit/hierarchical/` | Ordering, consensus components, hierarchy, and recovery |
| `unit/adapters/`, `unit/security/` | Storage adapters, authentication, signatures, keys, and security regressions |
| `unit/api/`, `unit/network/`, `unit/config/`, `unit/risk_management/` | API behavior, networking, configuration, and audit/risk components |
| `unit/test_*.py` | CLI, SDK, serialization, benchmarks, deployment helpers, and other regressions |
| `integration/` | Module interactions, storage contracts, CLI persistence, and cross-chain behavior |
| `integration/api_admin/`, `integration/api_business/`, `integration/api_ledger/` | API tests using FastAPI's in-process test client |
| `scenarios/` | Recovery, quorum/certificate validation, audit logging, and edge cases |

Directory names describe how tests are organized. A test under `unit/` can still
need a live service, and a scenario test can use mocks. Read the selected file's
fixtures before assuming it exercises a deployed cluster.

## Environment preparation

Install the locked development dependencies and activate the repository environment:

```bash
uv sync --frozen --extra dev
source .venv/bin/activate
export HRC_ENV=test
export HRC_AUTH_ENABLED=false
```

If `uv` is unavailable, install the development extra into a virtual environment:

```bash
python -m pip install -e ".[dev]"
```

The development extra includes pytest, pytest-asyncio, Hypothesis,
pytest-benchmark, and pytest-html. `pytest.ini` controls pytest in this repository;
its settings take precedence over the pytest table in `pyproject.toml`. It sets
asyncio mode to `auto` and default discovery paths to `tests/unit`,
`tests/integration`, and `tests/scenarios`. Docker tests are outside those paths
and excluded from recursive discovery.

Use an expendable checkout without application data. The autouse
`clean_journal_data` fixture recursively deletes the repository's entire `data/`
directory at the beginning and end of each executed test session, with
best-effort cleanup on filesystem errors. It does this regardless of which file
or case you select. Other databases and files created outside `data/` are not
covered by that cleanup. Stop processes that use the same data first.

The conftest sets `HRC_ENV=test` only when it is absent, and sets
`HRC_AUTH_ENABLED=false` only when absent in test/testing mode. Exporting them
explicitly prevents an inherited environment from retaining product-mode
settings. Check any inherited database configuration before running tests that
use runtime settings.

## Run selected files and cases

Run these examples separately:

```bash
# Core component tests.
python -m pytest tests/unit/core/test_blockchain.py -v

# Ledger API authentication and permission checks.
python -m pytest tests/integration/api_ledger/test_endpoints.py -v

# Recovery behavior with simulated node health and API-key state.
python -m pytest tests/scenarios/test_recovery.py -v
```

Select a single case by its node ID:

```bash
python -m pytest tests/unit/core/test_utils.py::test_generate_hash -v
```

Inspect collection without executing test bodies:

```bash
python -m pytest tests/integration/test_live_backends.py --collect-only -q
```

Collection imports test modules and conftest, so it is not a dependency-free
check. Run files sequentially: journal state, database state, background workers,
and performance measurements can interfere when files share resources.

Markers registered in `pytest.ini` include `recovery`, `integration`,
`critical`, `high`, `medium`, `low`, `stress`, `security`, `advanced`, `slow`, and
`docker`. Marker coverage varies by file; directory membership does not apply a
marker automatically. For example:

```bash
python -m pytest tests/scenarios/test_recovery.py -m recovery -v
```

## Live PostgreSQL, Redis, and IPFS checks

Several files skip backend cases when their required environment variables are
missing. A run with skips does not verify those backends. Use disposable services
and databases: these tests write records, alter schemas, or retain test data.

| Variable | Consumers and prerequisites |
| --- | --- |
| `HRC_TEST_POSTGRES_URL` | PostgreSQL cases in `test_bulk_storage.py`, `test_registry_multiworker.py`, `unit/core/test_block_event_ownership.py`, and `test_cli_postgres.py`; use a separate empty database for the CLI file |
| `HRC_P2_TEST_POSTGRES_URL` | `test_live_backends.py`; the account needs permission to create and drop test databases through `/postgres` |
| `HRC_P2_TEST_REDIS_URL` | `test_live_backends.py`, `test_redis_adapter_integration.py`, and `unit/security/test_shared_redis_state.py`; use a disposable Redis database |
| `HRC_TEST_REDIS_PORT` | Redis cases in `test_registry_multiworker.py`; connects to localhost and uses Redis database 14 with a generated key prefix |
| `HRC_TEST_AUDIT_MANIFEST_URL` | `test_audit_manifest_postgres.py`; requires a pre-provisioned audit manifest table |
| `HRC_P2_TEST_MANIFEST_WRITE_URL`, `HRC_P2_TEST_MANIFEST_READ_URL` | `test_audit_manifest_roles.py`; both point to the same empty manifest, using separate INSERT-only and SELECT-only roles |

The manifest table is `public.audit_event_digests`, with `event_id TEXT PRIMARY
KEY` and `digest TEXT NOT NULL`. The role-separation test also requires schema
usage and verifies that the writer cannot SELECT or DELETE and the reader cannot
INSERT. The backend job in
[`.github/workflows/test.yml`](../.github/workflows/test.yml) contains the database
and role initialization used by CI.

After provisioning services and setting the variables for the selected file, run:

```bash
python -m pytest tests/integration/test_live_backends.py -v --fail-on-skip
```

`--fail-on-skip` is a repository option defined in `tests/conftest.py`. It makes
any reported skip fail the session, so use it when the selected backend coverage
is required. `test_registry_multiworker.py` includes SQLite, PostgreSQL, and Redis
cases; all its backend variables must be configured for a complete run with this
option.

`tests/unit/api/test_ipfs.py::test_ipfs_client` contacts an IPFS daemon through
`IPFSClient`, uploads and pins test content, and skips when the daemon version
request is unavailable. The encryption case in that file runs locally. See the
[IPFS configuration reference](../docs/en/reference/config.md) for client settings.

## Benchmarks

Run an actual pytest-benchmark case in isolation:

```bash
python -m pytest tests/unit/core/test_utils.py::test_generate_hash_performance \
  --benchmark-only --benchmark-save=hash-generation -v
```

The plugin saves benchmark data under `.benchmarks/` by default. Results depend
on the host and test workload. Some performance cases also assert elapsed-time
limits, so sharing CPU with other workloads can affect their outcome.

`tests/unit/test_benchmark_throughput.py` is a regression test for signed workloads
and committed-event accounting. The standalone ordering benchmark lives in
[`scripts/benchmark_throughput.py`](../scripts/benchmark_throughput.py); its CLI
accepts `--events` and `--batch-size`. It requires a signing identity and trusted
block keys. Follow the mounted-identity example in
[`docker/README.md`](../docker/README.md) for the PostgreSQL-backed container run.

## Reports and CI

Write a JUnit report for one file:

```bash
mkdir -p log/report
python -m pytest tests/scenarios/test_recovery.py -v \
  --junitxml=log/report/recovery.xml
```

The compatibility workflow currently tests Python 3.10 through 3.14, invoking
pytest separately for each file in the three test directories. A separate
required backend job starts PostgreSQL 16 and Redis 7.4, provisions audit roles,
and uses `--fail-on-skip`. Inspect individual file outcomes and skips when
assessing coverage; passing local component tests does not establish live
backend or deployed-cluster behavior.

## Container and stress tests

The [Docker README](../docker/README.md) documents `docker/tests/`, the ordering
benchmark, and `docker/stress/`. These suites have their own Compose profiles and
runtime requirements.

For an already prepared four-node Docker test cluster, with the external API-key
file and a provisioned `HRC_API_KEY` configured:

```bash
bash docker/hierachain.sh stress docker --reuse
```

The Docker wrapper's reports are `log/report/docker_stress_report.html` and
`log/report/docker_stress_report.xml`. Stress cases can alter containers or
network conditions. Review the Docker README before using setup or cleanup;
those wrapper commands remove existing volumes. The Kubernetes path has
configuration gaps documented there, including missing trusted key maps and
stress Job tooling.

## Additional tools

[`scripts/`](../scripts/) contains static analysis and benchmark helpers:

```bash
python -m scripts.static_analysis
```

Static analysis does not execute the test suite. `scripts/verify_storage.py`
currently imports the absent `hierachain.storage.sql_backend` module, so it is
not a working persistence verification command. Use the relevant storage test
file above for the backend being checked.
