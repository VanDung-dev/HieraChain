---
title: "Testing Guide"
description: "Guide to running tests, markers/paths per pyproject, examples, and testing principles."
icon: material/test-tube
---

# Testing Guide

## Running Tests

!!! warning "Warning"
    Running all tests simultaneously may cause errors due to resource constraints. It is recommended to run per file or small groups.

### Running Unit Tests

```bash
python -m pytest tests/unit -v
```

### Running Integration Tests

```bash
python -m pytest tests/integration -v
```

### Running Scenario Tests

```bash
python -m pytest tests/scenarios -v
```

### Running Benchmark Tests

```bash
python -m pytest tests --benchmark-only -v --benchmark-save=benchmark_report
python -m pytest tests --benchmark-only -v --benchmark-histogram=benchmark_report
```

### Running All Tests

```bash
python -m pytest tests -v
```

### Durable Throughput Benchmark in Docker

Run the benchmark from the current source tree with PostgreSQL 16, 1 CPU,
1 GiB RAM, and durable journal writes enabled:

```bash
docker compose -f docker/docker-compose.benchmark.yml up --build --abort-on-container-exit
```

Override the workload with `BENCHMARK_EVENTS`, `BENCHMARK_BATCH_SIZE`,
`BENCHMARK_CPUS`, and `BENCHMARK_MEMORY`. Journal fsync always stays enabled.
Run `down -v` before a clean-database comparison;
clean any Compose leftovers with:

```bash
docker compose -f docker/docker-compose.benchmark.yml down -v
```

### Docker-specific Runtime Tests

Run deterministic checks for the image, native dependencies, journal replay,
and PostgreSQL adapter wiring without starting the four-node cluster:

```bash
docker compose -f docker/docker-compose.test.yml \
  --profile docker-test run --rm docker-tests
```

The profile starts an isolated PostgreSQL 16 service and stores the append-only
journal under `/app/data`. Journal fsync is always enabled. Override
`DOCKER_TEST_CPUS` or
`DOCKER_TEST_MEMORY` to change the container limit.

## Stress Testing

### Docker Stress Testing

Production stress requires `HRC_API_KEY` in the root `.env` or environment, using a key already provisioned in `HRC_API_KEYS_SOURCE_FILE` with `chains`, `events`, and `proofs` permissions (or `all`). Never paste the key into logs or reports. The launcher checks that a key is configured before deployment; pytest checks authenticated chain access on every node before running tests. Missing keys, 401/403/429 responses, and unreachable nodes stop the session. HTTP and WebSocket clients use the same key and `HRC_API_KEY_NAME` (default `X-API-Key`).

After source changes, rebuild the wheel and image. The wheel build clears generated `build/` so deleted modules cannot survive in setuptools' cache:

```bash
bash -c 'source docker/lib/common.sh; build_wheel'
docker build --target production -t hierachain:latest -f docker/Dockerfile .
```

Once the cluster uses the new image, run with `--reuse` to preserve its deployment and volumes. The default stress command redeploys and removes volumes. Check an individual file before running the full suite:

```bash
docker compose --env-file .env -f docker/docker-compose.yml --profile stress-test run --rm stress-tester python -m pytest docker/stress/test_real_network.py -v
bash docker/hierachain.sh stress docker --reuse
```

Crypto fixtures sign events and blocks and provide a trusted public key. Their benchmarks assert verification succeeds. For local crypto-only checks without network preflight, set `REAL_REQUESTS=false`; this does not validate live services.

`--duration` controls tests that read `TEST_DURATION`; it is not a time limit for the entire suite. The full tsunami flood still requests 5,000 events. Its send phase has a separate `STRESS_TIMEOUT` budget (default 120 seconds), after node readiness and chain creation. Workers stop at the deadline, queued batches are cancelled, and active HTTP calls use the remaining budget without flood retries. Incomplete runs report `timed_out` and `unattempted_events` and fail acceptance. The launcher shows each test result, short failure tracebacks, and the ten slowest tests. Live logs, captured console logs, and timed thread stack dumps are hidden by default; INFO logs remain captured for the HTML report, alongside the XML results.

```bash
STRESS_TIMEOUT=120 bash docker/hierachain.sh stress docker --reuse --duration 15
```

An HTTP 200 from `/api/ledger/health` confirms liveness; `/api/ledger/ready` checks hierarchy recovery. Stress readiness uses `/api/ledger/ready` without falling back to liveness; node polling shares its timeout across requests, without automatic HTTP retries. Chain setup requires every configured node, and poison setup probes each node once. Failed hierarchy bootstrap closes its storage pool, coordinator journal, and any started sub-chains. Concurrent bootstrap requests receive HTTP 503 immediately; failed attempts have a five-second retry cooldown. The signed event envelope permits its top-level `sender` field while business content still follows terminology checks; signature validation remains required by the admin API. Ordering startup validates persisted block links before replaying the journal. A `Chain link BROKEN` error requires recovery from trusted data or an explicitly approved reset of disposable test data. Rebuilding an image does not repair persisted blocks. Sub-chain startup waits for journal replay to finish, without cancelling a valid backlog after ten seconds; processor failure or shutdown still aborts bootstrap. Sub-chain rehydration updates local state without rewinding the active orderer's block index or cache.

Sub-chain blocks complete consensus, respect its minimum block interval, and receive the trusted header signature before the orderer saves them. The consumer validates and applies these committed blocks without changing their index, hash, events or signature, and never writes them again. Consensus or storage failure cannot advance the commit queue or block index. Concurrent consumer and flush calls drain the queue in order. HTTP consensus throughput checks wait up to 120 seconds for every accepted business event to commit, excluding the PoA consensus event in each new block. Throughput includes this drain time, so subsequent restart tests inherit no backlog from a passing throughput test. Recovery still requires the restarted primary to become ledger-ready within 60 seconds; they exercise a generic PoA chain and do not prove BFT protocol view changes.

IPFS stress setup creates the generic chain through the shared ledger client and requires success on every target node. Events supply `entity_id` directly to `POST /api/ledger/chains/{chain_name}/events`; no separate entity registration endpoint is required.

Run stress tests in Docker containers with 4 HieraChain nodes (1 CPU, 1GiB RAM each):

* Build and run stress tests with HTML report:

    ```bash
    docker compose -f docker/docker-compose.yml --profile stress-test run --rm stress-tester python -m pytest docker/stress/ -v --html=/app/log/report/stress_test_report.html --self-contained-html
    ```

* Run real network stress tests (sends actual HTTP requests to nodes):

    ```bash
    docker compose -f docker/docker-compose.yml --profile stress-test run --rm stress-tester python -m pytest docker/stress/test_real_network.py -v -s
    ```

* Run without HTML report:

    ```bash
    docker compose -f docker/docker-compose.yml --profile stress-test run --rm stress-tester
    ```

* Stop and clean up containers:

    ```bash
    docker compose -f docker/docker-compose.yml down --remove-orphans
    ```

Reports are saved to `log/report/` directory.

### Kubernetes Stress Testing

Run stress tests in Kubernetes

> **Recommendation:** Use Docker Compose for local dev. Use Kubernetes when you need a production-like environment.

**Quick Start:**

```bash
# Build image
docker build --no-cache -t hierachain:latest -f docker/Dockerfile .

# Create Kind cluster
kind create cluster --config docker/kind-config.yaml

# Resource limit for each Node of K8s (1 CPU, 1GiB RAM)
docker update --cpus 1 --memory 1g --memory-swap 1g hiera-cluster-control-plane
docker update --cpus 1 --memory 1g --memory-swap 1g hiera-cluster-worker
docker update --cpus 1 --memory 1g --memory-swap 1g hiera-cluster-worker2
docker update --cpus 1 --memory 1g --memory-swap 1g hiera-cluster-worker3

# Load image into cluster
kind load docker-image hierachain:latest --name hiera-cluster
kubectl apply -k docker/k8s/

# Wait for pods to be ready
kubectl wait --for=condition=ready pod -l app=hierachain -n hierachain --timeout=120s

# Expose the API to local host
kubectl port-forward service/hierachain-api 2661:2661 -n hierachain --address 0.0.0.0

# Test API  
curl http://localhost:2661/api/ledger/health

# Run stress test
docker compose -f docker/docker-compose.k8s-stress.yml --profile stress-test run --build stress-tester python -m pytest docker/stress/ -v --html=/app/log/report/stress_test_report.html --self-contained-html

# Cleanup
kubectl delete -k docker/k8s/
kind delete cluster --name hiera-cluster
```

## Developer Scripts

The `scripts/` directory contains utility tools.

### Static Analysis

```bash
# Run default
python -m scripts.static_analysis

# Export results to file
python -m scripts.static_analysis --output analysis_report.json
```

### Security Auditing & Code Scanning

Automated security checks across codebase and dependencies:

* **Bandit** (SAST security analysis for Python code):

    ```bash
    # Full security scan across all severity levels
    uv run bandit -r hierachain/

    # Scan Medium and High severity issues only
    uv run bandit -r hierachain/ -ll
    ```

* **pip-audit** (Vulnerability & CVE scanner for packages):

    ```bash
    # Scan all installed dependencies
    uv run pip-audit

    # Strict mode (fail on any vulnerability)
    uv run pip-audit --strict
    ```

* **Semgrep** (Semantic API security & taint analysis):

    ```bash
    # Auto-detect relevant rules
    uv run semgrep --config=auto hierachain/

    # Run OWASP Top 10 ruleset
    uv run semgrep --config=p/owasp-top-ten hierachain/
    ```

### Benchmarking

* **Hashing Performance** (Compare Merkle tree hash vs JSON):

    ```bash
    python scripts/benchmark_hashing.py
    ```

* **Throughput Benchmark** (Measure event processing throughput):

    ```bash
    python scripts/benchmark_throughput.py --events 1000 --batch-size 100
    ```

### Storage Verification

* **Verify Storage Persistence** (Test local storage durability):

    ```bash
    python scripts/verify_storage.py
    ```

## Pytest Configuration (excerpt from `pyproject.toml`)

* `testpaths = ["tests/unit", "tests/integration", "tests/scenarios"]`
* `python_files = "test_*.py"`
* `python_classes = "Test*"`
* `python_functions = "test_*"`
* Markers:

    * `critical`, `high`, `medium`, `low`
    * `integration`, `recovery`, `stress`

## Running by Marker Example

```bash
pytest -v -m critical
pytest -v -m integration
```

## Testing Principles

* Focus on public API behavior of the module.
* Test edge cases and error scenarios.
* Keep tests independent, runnable by marker.

## Test Layout Suggestions

* Unit: test individual classes/functions (core, security, storage...).
* Integration: test end-to-end flows via API Ledger/business.
* Scenarios: business scenarios (e.g. create sub-chain → write event → submit proof → trace entity).
