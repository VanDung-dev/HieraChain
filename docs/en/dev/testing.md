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

## Stress Testing

### Docker Stress Testing

Run stress tests in Docker containers with 4 HieraChain nodes (1 CPU, 1GiB RAM each):

* Build and run stress tests with HTML report:

    ```bash
    docker compose -f docker/docker-compose.test.yml --profile stress-test run stress-tester python -m pytest tests/stress/ -v --html=/app/log/report/stress_test_report.html --self-contained-html
    ```

* Run real network stress tests (sends actual HTTP requests to nodes):

    ```bash
    docker compose -f docker/docker-compose.test.yml --profile stress-test run stress-tester python -m pytest tests/stress/test_real_network.py -v -s
    ```

* Run without HTML report:

    ```bash
    docker compose -f docker/docker-compose.test.yml --profile stress-test run stress-tester
    ```

* Stop and clean up containers:

    ```bash
    docker compose -f docker/docker-compose.test.yml down --remove-orphans
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
curl http://localhost:2661/api/v1/health

# Run stress test
docker compose -f docker/docker-compose.k8s-stress.yml --profile stress-test run --build stress-tester python -m pytest tests/stress/ -v --html=/app/log/report/stress_test_report.html --self-contained-html

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

### Benchmarking

* **Hashing Performance** (Compare Merkle tree hash vs JSON):

    ```bash
    python scripts/benchmark_hashing.py
    ```

* **Throughput Benchmark** (Measure event processing throughput):

    ```bash
    python scripts/benchmark_throughput.py --events 1000 --workers 4 --batch-size 100
    ```

### Storage Verification

* **Verify Storage Persistence** (Test SQLite durability):

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
* Integration: test end-to-end flows via API v1/v2.
* Scenarios: business scenarios (e.g. create sub-chain → write event → submit proof → trace entity).
