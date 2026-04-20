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

### Docker

Chạy stress tests trong container (4 node, 1 CPU, 1GiB RAM):

1. **Build & Chạy (có báo cáo HTML):**

    ```bash
    docker compose -f docker/docker-compose.test.yml --profile stress-test run stress-tester python -m pytest tests/stress/ -v --html=/app/log/report/stress_test_report.html --self-contained-html
    ```

2. **Chạy test mạng thực (gửi request HTTP):**

    ```bash
    docker compose -f docker/docker-compose.test.yml --profile stress-test run stress-tester python -m pytest tests/stress/test_real_network.py -v -s
    ```

3. **Dọn dẹp:**

    ```bash
    docker compose -f docker/docker-compose.test.yml down --remove-orphans
    ```

Báo cáo được lưu tại `log/report/`.

### Kubernetes

!!! tip "Khuyến nghị"
    Dùng Kubernetes cho môi trường giống production.

**Quick Start:**

1. **Build & Deploy**

    ```bash
    docker build --no-cache -t hierachain:latest -f docker/Dockerfile .
    kind create cluster --name hiera-cluster
    kind load docker-image hierachain:latest --name hiera-cluster
    kubectl apply -k docker/k8s/
    ```

2. **Đợi pods sẵn sàng**

    ```bash
    kubectl wait --for=condition=ready pod -l app=hierachain -n hierachain --timeout=120s
    ```

3. **Expose API** (nếu cần test manual)

    ```bash
    kubectl port-forward service/hierachain-api 32661:2661 -n hierachain --address 0.0.0.0
    ```

4. **Chạy stress test**

    ```bash
    docker compose -f docker/docker-compose.k8s-stress.yml --profile stress-test run --build stress-tester python -m pytest tests/stress/ -v --html=/app/log/report/stress_test_report.html --self-contained-html
    ```

5. **Dọn dẹp**

    ```bash
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
