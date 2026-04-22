---
title: "Hướng dẫn kiểm thử"
description: "Hướng dẫn chạy test, markers/paths theo pyproject, ví dụ, và nguyên tắc viết test."
icon: material/test-tube
---

# Hướng dẫn kiểm thử

## Chạy test

!!! warning "Cảnh báo"
    Chạy toàn bộ test cùng lúc có thể gây lỗi do giới hạn tài nguyên. Khuyến nghị chạy theo từng file hoặc nhóm nhỏ.

### Chạy Unit Tests

```bash
python -m pytest tests/unit -v
```

### Chạy Integration Tests

```bash
python -m pytest tests/integration -v
```

### Chạy Scenario Tests

```bash
python -m pytest tests/scenarios -v
```

### Chạy Benchmark Tests

```bash
python -m pytest tests --benchmark-only -v --benchmark-save=benchmark_report
python -m pytest tests --benchmark-only -v --benchmark-histogram=benchmark_report
```

### Chạy Toàn bộ (All)

```bash
python -m pytest tests -v
```

## Kiểm thử chịu tải (Stress Testing)

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

## Công cụ phát triển (Developer Scripts)

Thư mục `scripts/` chứa các tiện ích bổ trợ.

### Phân tích tĩnh (Static Analysis)

```bash
# Chạy mặc định
python -m scripts.static_analysis

# Xuất kết quả ra file
python -m scripts.static_analysis --output analysis_report.json
```

### Benchmarking (Hiệu năng)

* **Hashing Performance** (So sánh Merkle tree hash vs JSON):

    ```bash
    python scripts/benchmark_hashing.py
    ```

* **Throughput Benchmark** (Đo thông lượng xử lý sự kiện):

    ```bash
    python scripts/benchmark_throughput.py --events 1000 --workers 4 --batch-size 100
    ```

### Kiểm tra lưu trữ (Storage Verification)

* **Verify Storage Persistence** (Kiểm tra tính bền vững của SQLite):

    ```bash
    python scripts/verify_storage.py
    ```

## Cấu hình pytest (trích `pyproject.toml`)

* `testpaths = ["tests/unit", "tests/integration", "tests/scenarios"]`
* `python_files = "test_*.py"`
* `python_classes = "Test*"`
* `python_functions = "test_*"`
* Markers:

    * `critical`, `high`, `medium`, `low`
    * `integration`, `recovery`, `stress`

## Ví dụ chạy theo marker

```bash
pytest -v -m critical
pytest -v -m integration
```

## Nguyên tắc viết test

* Tập trung vào hành vi API công khai (public API) của module.
* Test dữ liệu biên và tình huống lỗi (EDGE CASES trong docs).
* Giữ test độc lập, có thể chạy theo marker.

## Gợi ý bố trí test

* Unit: kiểm tra lớp/hàm đơn lẻ (core, security, storage...).
* Integration: kiểm tra luồng end‑to‑end qua API v1/v2.
* Scenarios: kịch bản nghiệp vụ (ví dụ tạo sub‑chain → ghi event → submit proof → truy vết entity).
