# HieraChain Test Suite

This directory contains the comprehensive test suite for the HieraChain Ledger.

---

## Test Structure

```
tests/
├── conftest.py          # Pytest configuration and shared fixtures
├── unit/                # Unit tests for individual components
├── integration/         # Integration tests for module interactions
└── scenarios/           # End-to-end scenario tests
```

---

## Prerequisites

Before running tests, ensure you have installed the package in development mode along with testing dependencies:

```bash
pip install -e ".[dev]"
```

---

## Running Tests

> **WARNING**: Running all tests simultaneously may cause failures due to resource constraints. It is recommended to run tests **per test file** instead of grouping them by directories to ensure more accurate and reliable results.

### Unit Tests

Run unit tests to verify individual component functionality:

```bash
python -m pytest tests/unit -v
```

### Integration Tests

Run integration tests to verify module interactions:

```bash
python -m pytest tests/integration -v
```

### Scenario Tests

Run scenario tests for end-to-end functionality:

```bash
python -m pytest tests/scenarios -v
```

### Benchmark Tests

Run benchmark tests to measure performance:

```bash
python -m pytest tests --benchmark-only -v --benchmark-save=benchmark_report
python -m pytest tests --benchmark-only -v --benchmark-histogram=benchmark_report
```

### Run All Tests

To run all tests (use with caution):

```bash
python -m pytest tests -v
```

---

## Stress Testing

For detailed stress testing instructions (Docker & Kubernetes), please refer to:

**File:** [`docker/README.md`](../docker/README.md)

This covers:

* Docker Compose setup (4-node cluster, 1 CPU / 1GiB RAM per node)
* Kubernetes (Kind) setup with resource limits
* Stress test execution and HTML reports
* Configuration tuning (rate limiting, log level, storage backend)
* Troubleshooting common issues

**Quick start (Docker Compose):**

```bash
docker/setup-docker-compose.sh
docker/run-stress-docker-compose.sh
```

**Quick start (Kubernetes):**

```bash
docker/setup-k8s.sh
docker/run-stress-k8s.sh
```

Reports are saved to `log/report/` directory.

---

## Test Fixtures

The [`conftest.py`](conftest.py) file provides shared pytest fixtures:

* **clean_journal_data**: Automatically cleans the `data/` directory at the start and end of each test session to prevent state pollution.
* **Project root path**: Ensures project modules are correctly imported during test collection.

---

## Running Individual Test Files

For more reliable results, run individual test files instead of entire directories:

```bash
# Run a specific unit test file
python -m pytest tests/unit/test_blockchain.py -v

# Run a specific integration test file
python -m pytest tests/integration/test_api.py -v
```

---

## Additional Testing Resources

For benchmark and performance testing scripts, see the [`scripts/`](scripts/) directory in the project root:

* **Static Analysis**: `python -m scripts.static_analysis`
* **Throughput Benchmark**: `python scripts/benchmark_throughput.py --events 1000 --workers 4 --batch-size 100`
* **Storage Verification**: `python scripts/verify_storage.py`