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

Các test integration consensus, 2PC, luồng dữ liệu và recovery dùng SQLite và journal trong thư mục tạm riêng cho từng test. Chúng không yêu cầu dịch vụ PostgreSQL trong `.env` của ứng dụng; test live-backend chuyên biệt kiểm tra PostgreSQL.

### Benchmark throughput bền vững bằng Docker

Chạy benchmark từ source hiện tại với PostgreSQL 16, giới hạn 1 CPU, 1 GiB RAM
và bật ghi journal bền vững:

```bash
docker compose -f docker/docker-compose.benchmark.yml up --build --abort-on-container-exit
```

Có thể đổi workload bằng `BENCHMARK_EVENTS`, `BENCHMARK_BATCH_SIZE`,
`BENCHMARK_CPUS` và `BENCHMARK_MEMORY`. Fsync journal luôn được bật.
Hãy chạy `down -v` trước khi cần benchmark với
database sạch; xóa phần còn lại của Compose bằng:

```bash
docker compose -f docker/docker-compose.benchmark.yml down -v
```

### Bộ kiểm thử runtime chuyên biệt cho Docker

Chạy các kiểm tra xác định cho image, dependency native, replay journal và
PostgreSQL adapter mà không cần khởi động cluster bốn node:

```bash
docker compose -f docker/docker-compose.test.yml \
  --profile docker-test run --rm docker-tests
```

Profile này khởi động PostgreSQL 16 riêng và lưu journal append-only tại
`/app/data`. Fsync journal luôn được bật. Có thể đổi giới hạn container bằng
`DOCKER_TEST_CPUS` hoặc `DOCKER_TEST_MEMORY`.

## Kiểm thử Áp lực (Stress Testing)

### Kiểm thử Áp lực với Docker

Stress ở chế độ production cần `HRC_API_KEY` trong `.env` gốc hoặc môi trường, dùng key đã được cấp trong `HRC_API_KEYS_SOURCE_FILE` với quyền `chains`, `events`và `proofs` (hoặc `all`). Không đưa key vào log hay báo cáo. Launcher kiểm tra có cấu hình key trước triển khai; pytest kiểm tra truy cập chain có xác thực trên từng node trước khi chạy test. Thiếu key, phản hồi 401/403/429 hoặc node không kết nối được sẽ dừng phiên test. Client HTTP và WebSocket dùng cùng key và `HRC_API_KEY_NAME` (mặc định `X-API-Key`).

Sau khi sửa source, build lại wheel và image. Lệnh build wheel xóa thư mục sinh tự động `build/` để module đã xóa không còn sót trong cache setuptools:

```bash
bash -c 'source docker/lib/common.sh; build_wheel'
docker build --target production -t hierachain:latest -f docker/Dockerfile .
```

Khi cluster đã dùng image mới, chạy với `--reuse` để giữ deployment và volume. Lệnh stress mặc định triển khai lại và xóa volume. Kiểm tra riêng từng file trước khi chạy toàn bộ suite:

```bash
docker compose --env-file .env -f docker/docker-compose.yml --profile stress-test run --rm stress-tester python -m pytest docker/stress/test_real_network.py -v
bash docker/hierachain.sh stress docker --reuse
```

Fixture crypto ký event/block và cung cấp public key tin cậy. Benchmark assert kết quả xác minh thành công. Khi chỉ kiểm tra crypto cục bộ không cần preflight mạng, đặt `REAL_REQUESTS=false`; kết quả này không xác minh dịch vụ thật.

`--duration` điều khiển các test đọc `TEST_DURATION`; đây không phải giới hạn thời gian của toàn bộ suite. Tsunami flood đầy đủ vẫn yêu cầu 5.000 event. Pha gửi có ngân sách `STRESS_TIMEOUT` riêng (mặc định 120 giây), sau bước chờ node và tạo chain. Worker dừng khi hết giờ, batch còn trong hàng đợi bị hủy và request HTTP đang chạy dùng thời gian còn lại, không retry trong flood. Lần chạy chưa đủ event báo `timed_out` cùng `unattempted_events` và không đạt tiêu chí chấp nhận. Launcher hiển thị kết quả từng test, traceback lỗi ngắn và mười test chậm nhất. Live log, log đã capture trên console và stack thread theo thời gian được ẩn mặc định; log INFO vẫn được capture trong báo cáo HTML, cùng kết quả XML.

```bash
STRESS_TIMEOUT=120 bash docker/hierachain.sh stress docker --reuse --duration 15
```

HTTP 200 từ `/api/ledger/health` xác nhận tiến trình còn hoạt động; `/api/ledger/ready` kiểm tra recovery của hệ phân cấp. Stress dùng `/api/ledger/ready` mà không chuyển sang liveness; bước chờ node chia sẻ timeout cho các request và không tự retry HTTP. Bước tạo chain yêu cầu đủ mọi node đã cấu hình, còn poison setup probe từng node một lần. Bootstrap hệ phân cấp thất bại sẽ đóng storage pool, journal của coordinator và các sub-chain đã khởi động. Request đồng thời với bootstrap nhận HTTP 503 ngay; lần khởi tạo thất bại chờ năm giây trước khi thử lại. Event đã ký cho phép trường `sender` cấp ngoài, trong khi nội dung nghiệp vụ vẫn phải qua kiểm tra thuật ngữ; API admin vẫn bắt buộc xác minh chữ ký. Khi khởi động, orderer kiểm tra liên kết block đã lưu trước khi replay journal. Lỗi `Chain link BROKEN` cần khôi phục từ dữ liệu tin cậy hoặc được chấp thuận rõ ràng để reset dữ liệu test có thể bỏ. Build lại image không sửa block đã lưu. Sub-chain chờ replay journal hoàn tất, không hủy backlog hợp lệ sau mười giây; lỗi processor hoặc shutdown vẫn dừng bootstrap. Rehydration của sub-chain cập nhật trạng thái cục bộ mà không ghi lùi chỉ số block hoặc cache của orderer đang hoạt động.

Block của sub-chain được hoàn tất consensus, tuân thủ khoảng thời gian tối thiểu của consensus và ký header bằng khóa tin cậy trước khi orderer lưu. Consumer xác minh và áp dụng block đã commit mà không đổi index, hash, event hay chữ ký, và không ghi lại block. Lỗi consensus hoặc storage không được tăng chỉ số block hoặc đưa block vào commit queue. Consumer và lệnh flush đồng thời lấy block theo đúng thứ tự. Test throughput consensus qua HTTP chờ tối đa 120 giây để mọi event nghiệp vụ đã nhận được commit, loại event consensus PoA trong mỗi block mới khỏi số đếm. Throughput tính cả thời gian chờ commit, nên test restart tiếp theo không nhận backlog từ test throughput đã pass. Recovery vẫn yêu cầu primary vừa restart phải ledger-ready trong 60 giây; các test này dùng chain PoA generic và không chứng minh view change của giao thức BFT.

Setup stress IPFS tạo chain generic qua ledger client dùng chung và yêu cầu thành công trên mọi node đích. Event truyền `entity_id` trực tiếp vào `POST /api/ledger/chains/{chain_name}/events`; không cần endpoint đăng ký entity riêng.

Chạy kiểm thử áp lực trong các container Docker với cấu hình gồm 4 node HieraChain (mỗi node giới hạn 1 CPU, 1GiB RAM):

* Xây dựng cấu hình và chạy stress test với báo cáo định dạng HTML:

    ```bash
    docker compose -f docker/docker-compose.yml --profile stress-test run --rm stress-tester python -m pytest docker/stress/ -v --html=/app/log/report/stress_test_report.html --self-contained-html
    ```

* Chạy stress test trên mạng thực tế (gửi các yêu cầu HTTP thực tế tới các node):

    ```bash
    docker compose -f docker/docker-compose.yml --profile stress-test run --rm stress-tester python -m pytest docker/stress/test_real_network.py -v -s
    ```

* Chạy không cần xuất báo cáo HTML:

    ```bash
    docker compose -f docker/docker-compose.yml --profile stress-test run --rm stress-tester
    ```

* Dừng và dọn dẹp các container:

    ```bash
    docker compose -f docker/docker-compose.yml down --remove-orphans
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
curl http://localhost:2661/api/ledger/health

# Chạy stress test
docker compose -f docker/docker-compose.k8s-stress.yml --profile stress-test run --build stress-tester python -m pytest docker/stress/ -v --html=/app/log/report/stress_test_report.html --self-contained-html

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

### Rà quét & Kiểm tra Bảo mật (Security Auditing)

Rà quét mã nguồn và các thư viện phụ thuộc bằng các công cụ chuyên dụng:

* **Bandit** (Phân tích bảo mật mã nguồn tĩnh SAST cho Python):

    ```bash
    # Quét toàn bộ các mức độ cảnh báo
    uv run bandit -r hierachain/

    # Chỉ quét cảnh báo mức Medium và High
    uv run bandit -r hierachain/ -ll
    ```

* **pip-audit** (Rà quét lỗ hổng CVE trong các thư viện phụ thuộc):

    ```bash
    # Quét toàn bộ thư viện đã cài đặt trong .venv
    uv run pip-audit

    # Chế độ nghiêm ngặt (Strict mode)
    uv run pip-audit --strict
    ```

* **Semgrep** (Phân tích ngữ nghĩa & quy tắc bảo mật API):

    ```bash
    # Tự động nhận diện quy tắc phù hợp
    uv run semgrep --config=auto hierachain/

    # Chạy bộ quy tắc OWASP Top 10
    uv run semgrep --config=p/owasp-top-ten hierachain/
    ```

### Kiểm thử Hiệu năng (Benchmarking)

* **Hiệu năng Băm** (So sánh băm cây Merkle vs băm JSON):

    ```bash
    python scripts/benchmark_hashing.py
    ```

* **Đo lường Băng thông** (Đo tốc độ xử lý sự kiện):

    ```bash
    python scripts/benchmark_throughput.py --events 1000 --batch-size 100
    ```

### Xác minh Lưu trữ (Storage Verification)

* **Xác minh tính Bền vững Lưu trữ** (Kiểm tra độ bền lưu trữ cục bộ):

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
* Integration: kiểm thử các luồng hoàn chỉnh đầu-cuối qua API Ledger/business.
* Scenarios: các kịch bản nghiệp vụ thực tế (ví dụ: tạo sub-chain → ghi sự kiện → gửi proof → truy vết thực thể).
