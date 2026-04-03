# HieraChain Test Suite

This directory contains the comprehensive test suite for the HieraChain Ledger.

---

## Test Structure

```
tests/
├── conftest.py          # Pytest configuration and shared fixtures
├── unit/                # Unit tests for individual components
├── integration/         # Integration tests for module interactions
├── scenarios/          # End-to-end scenario tests
└── stress/             # Stress and performance tests
```

---

## Prerequisites

Before running tests, ensure you have installed all dependencies:

```bash
# Install core dependencies
pip install -r requirements.txt

# Install development & testing dependencies
pip install -r requirements_dev.txt

# Install the package in development mode
pip install -e .
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

### Docker Stress Testing

Run stress tests in Docker containers with 4 HieraChain nodes (1 CPU, 1GiB RAM each):

**Build and run stress tests with HTML report:**

```bash
docker compose -f docker/docker-compose.test.yml --profile stress-test run stress-tester python -m pytest tests/stress/ -v --html=/app/log/report/stress_test_report.html --self-contained-html
```

**Run real network stress tests (sends actual HTTP requests to nodes):**

```bash
docker compose -f docker/docker-compose.test.yml --profile stress-test run stress-tester python -m pytest tests/stress/test_real_network.py -v -s
```

**Run without HTML report:**

```bash
docker compose -f docker/docker-compose.test.yml --profile stress-test run stress-tester
```

**Stop and clean up containers:**

```bash
docker compose -f docker/docker-compose.test.yml down --remove-orphans
```

Reports are saved to `log/report/` directory.

---

### Kubernetes Stress Testing

Run stress tests in Kubernetes. **Recommendation:** Use Docker Compose for local development. Use Kubernetes when you need a production-like environment.

**Quick Start:**

```bash
# Build image & deploy
docker build --no-cache -t hierachain:latest -f docker/Dockerfile .
kind create cluster --config docker/kind-config.yaml
kind load docker-image hierachain:latest --name hiera-cluster
kubectl apply -k docker/k8s/

# Wait for pods to be ready
kubectl wait --for=condition=ready pod -l app=hierachain -n hierachain --timeout=120s

# Expose the API to local host
kubectl port-forward service/hierachain-api 2661:2661 -n hierachain --address 0.0.0.0

# Test API  
curl http://localhost:2661/api/v1/health

# Run stress test
docker compose -f docker/docker-compose.k8s-stress.yml --profile stress-test run --build stress-tester python -m pytest tests/stress/ -v --html=/app/log/report/stress_test_report.html --self-contained-html

# Cleanup
kubectl delete -k docker/k8s/
kind delete cluster --name hiera-cluster
```

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