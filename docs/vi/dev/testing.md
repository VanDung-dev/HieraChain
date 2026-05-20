---
title: "Hướng dẫn Kiểm thử"
description: "Hướng dẫn chi tiết chạy kiểm thử, định nghĩa marker/path theo tệp cấu hình pyproject, các ví dụ và nguyên tắc kiểm thử lõi."
icon: material/test-tube
---

# Hướng dẫn Kiểm thử

## Chạy kiểm thử

!!! warning "Cảnh báo"
    Chạy tất cả các bài kiểm thử đồng thời có thể gây lỗi do giới hạn về tài nguyên hệ thống. Khuyên dùng chạy theo từng file hoặc các nhóm nhỏ độc lập.

### Chạy Unit Test (Kiểm thử Đơn vị)

```bash
python -m pytest tests/unit -v
```

### Chạy Integration Test (Kiểm thử Tích hợp)

```bash
python -m pytest tests/integration -v
```

### Chạy Scenario Test (Kiểm thử Kịch bản)

```bash
python -m pytest tests/scenarios -v
```

### Chạy Benchmark Test (Kiểm thử Hiệu năng)

```bash
python -m pytest tests --benchmark-only -v --benchmark-save=benchmark_report
python -m pytest tests --benchmark-only -v --benchmark-histogram=benchmark_report
```

### Chạy Tất cả Kiểm thử

```bash
python -m pytest tests -v
```

## Kiểm thử Áp lực (Stress Testing)

### Kiểm thử Áp lực với Docker

Chạy kiểm thử áp lực trong các container Docker với cấu hình gồm 4 node HieraChain (mỗi node giới hạn 1 CPU, 1GiB RAM):

* Xây dựng cấu hình và chạy stress test với báo cáo định dạng HTML:

    ```bash
    docker compose -f docker/docker-compose.test.yml --profile stress-test run stress-tester python -m pytest tests/stress/ -v --html=/app/log/report/stress_test_report.html --self-contained-html
    ```

* Chạy stress test trên mạng thực tế (gửi các yêu cầu HTTP thực tế tới các node):

    ```bash
    docker compose -f docker/docker-compose.test.yml --profile stress-test run stress-tester python -m pytest tests/stress/test_real_network.py -v -s
    ```

* Chạy không cần xuất báo cáo HTML:

    ```bash
    docker compose -f docker/docker-compose.test.yml --profile stress-test run stress-tester
    ```

* Dừng và dọn dẹp các container:

    ```bash
    docker compose -f docker/docker-compose.test.yml down --remove-orphans
    ```

Các báo cáo kết quả được lưu tại thư mục `log/report/`.

### Kiểm thử Áp lực với Kubernetes

Chạy kiểm thử áp lực trên môi trường Kubernetes.

> **Khuyên dùng:** Sử dụng Docker Compose cho việc phát triển cục bộ. Chỉ sử dụng Kubernetes khi bạn cần mô phỏng một môi trường gần giống với sản xuất thực tế.

**Bắt đầu nhanh:**

```bash
# Build image
docker build --no-cache -t hierachain:latest -f docker/Dockerfile .

# Tạo cluster Kind
kind create cluster --config docker/kind-config.yaml

# Giới hạn tài nguyên cho mỗi Node K8s (1 CPU, 1GiB RAM)
docker update --cpus 1 --memory 1g --memory-swap 1g hiera-cluster-control-plane
docker update --cpus 1 --memory 1g --memory-swap 1g hiera-cluster-worker
docker update --cpus 1 --memory 1g --memory-swap 1g hiera-cluster-worker2
docker update --cpus 1 --memory 1g --memory-swap 1g hiera-cluster-worker3

# Tải image vào trong cluster
kind load docker-image hierachain:latest --name hiera-cluster
kubectl apply -k docker/k8s/

# Chờ các pod sẵn sàng
kubectl wait --for=condition=ready pod -l app=hierachain -n hierachain --timeout=120s

# Ánh xạ cổng API ra máy cục bộ (localhost)
kubectl port-forward service/hierachain-api 2661:2661 -n hierachain --address 0.0.0.0

# Kiểm tra API hoạt động  
curl http://localhost:2661/api/v1/health

# Chạy stress test
docker compose -f docker/docker-compose.k8s-stress.yml --profile stress-test run --build stress-tester python -m pytest tests/stress/ -v --html=/app/log/report/stress_test_report.html --self-contained-html

# Dọn dẹp
kubectl delete -k docker/k8s/
kind delete cluster --name hiera-cluster
```

## Các Kịch bản Hỗ trợ Developer (Developer Scripts)

Thư mục `scripts/` chứa các công cụ tiện ích hỗ trợ nhà phát triển.

### Phân tích Tĩnh (Static Analysis)

```bash
# Chạy mặc định
python -m scripts.static_analysis

# Xuất kết quả phân tích ra file
python -m scripts.static_analysis --output analysis_report.json
```

### Kiểm thử Hiệu năng (Benchmarking)

* **Hiệu năng Băm** (So sánh băm cây Merkle vs băm JSON):

    ```bash
    python scripts/benchmark_hashing.py
    ```

* **Đo lường Băng thông** (Đo tốc độ xử lý sự kiện):

    ```bash
    python scripts/benchmark_throughput.py --events 1000 --workers 4 --batch-size 100
    ```

### Xác minh Lưu trữ (Storage Verification)

* **Xác minh tính Bền vững Lưu trữ** (Kiểm tra độ bền SQLite):

    ```bash
    python scripts/verify_storage.py
    ```

## Cấu hình Pytest (trích xuất từ `pyproject.toml`)

* `testpaths = ["tests/unit", "tests/integration", "tests/scenarios"]`
* `python_files = "test_*.py"`
* `python_classes = "Test*"`
* `python_functions = "test_*"`
* Các Marker:

    * `critical`, `high`, `medium`, `low`
    * `integration`, `recovery`, `stress`

## Ví dụ chạy kiểm thử theo Marker

```bash
pytest -v -m critical
pytest -v -m integration
```

## Các Nguyên tắc Kiểm thử

* Tập trung vào hành vi API công khai của từng mô-đun.
* Kiểm thử tất cả các trường hợp biên (edge cases) và kịch bản lỗi.
* Đảm bảo các bài kiểm thử độc lập và có thể chạy theo marker.

## Định hướng Phân bổ Kiểm thử

* Unit: kiểm thử các lớp/hàm độc lập (core, security, storage...).
* Integration: kiểm thử các luồng hoàn chỉnh đầu-cuối qua API v1/v2.
* Scenarios: các kịch bản nghiệp vụ thực tế (ví dụ: tạo sub-chain → ghi sự kiện → gửi proof → truy vết thực thể).
