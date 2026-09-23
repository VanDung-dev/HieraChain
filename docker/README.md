# HieraChain Stress Testing Infrastructure

HieraChain provides container runtimes dedicated to high-performance benchmarking and stability testing.

---

## File Layout

```
docker/
├── docker-compose.yml                 # Compose definition (multi-region + WireGuard)
├── docker-compose.test.yml            # Isolated Docker runtime tests
├── docker-compose.k8s-stress.yml      # Kubernetes stress test
├── Dockerfile                         # production, test, and benchmark stages
├── hierachain.sh                      # Unified CLI (recommended)
├── lib/                               # Shared deployment & provider libraries
└── scripts/                           # Helper scripts (identity gen, network tc)
```

---

## Usage

### Via hierachain.sh (recommended)

```bash
# Docker Compose
bash docker/hierachain.sh setup docker
bash docker/hierachain.sh stress docker --reuse
bash docker/hierachain.sh down docker

# Kubernetes
bash docker/hierachain.sh setup k8s
bash docker/hierachain.sh stress k8s --reuse
bash docker/hierachain.sh down k8s
```

The Docker stress command defaults to 15 seconds per network-condition,
network-simulation, and failure-scenario case. Use `--duration 60` for a
longer run; the Kubernetes default remains 60 seconds. Other tests with
explicit measurement windows keep their own durations.

### Via compose directly

```bash
# Docker Compose
docker compose -f docker/docker-compose.yml up -d
docker compose -f docker/docker-compose.yml down -v
```

### Docker-specific tests

Run deterministic container checks without starting the four-node cluster:

```bash
docker compose -f docker/docker-compose.test.yml \
  --profile docker-test run --rm docker-tests
```

The test profile starts an isolated PostgreSQL 16 service and checks the
PostgreSQL adapter, journal replay, and native dependencies. It keeps the
append-only journal under `/app/data` and sets `HRC_JOURNAL_FSYNC=true`.
Override `DOCKER_TEST_CPUS` or
`DOCKER_TEST_MEMORY` to reproduce a different container limit.

The test and benchmark Compose files use the `test` and `benchmark` stages
from `docker/Dockerfile`; the product image uses the `production` stage.

### Throughput benchmark

Run the durable single-container benchmark with the current source tree:

```bash
docker compose -f docker/docker-compose.benchmark.yml up --build --abort-on-container-exit
```

Override the workload or durability mode when needed:

```bash
BENCHMARK_EVENTS=20000 BENCHMARK_BATCH_SIZE=500 \
docker compose -f docker/docker-compose.benchmark.yml run --rm throughput

HRC_JOURNAL_FSYNC=false \
docker compose -f docker/docker-compose.benchmark.yml run --rm throughput
```

The benchmark uses PostgreSQL 16, a 1 CPU / 1 GiB application limit, and an
append-only journal. Remove Compose services and anonymous volumes with:

```bash
docker compose -f docker/docker-compose.benchmark.yml down -v
```

---

## Platform Requirements

| Platform | Container Runtime | Notes |
|----------|------------------|-------|
| **macOS / Linux** | Docker Desktop / OrbStack / Docker Engine | Local development, multi-region simulation, and stress testing |
| **Kubernetes Cluster** | K8s / OrbStack / EKS / GKE | Enterprise cloud-native deployment |

---

## Quick Start

```bash
# 1. Deploy 4-node HieraChain cluster + Redis + Gateway + IPFS Swarm
bash docker/hierachain.sh setup docker

# 2. Execute stress test suite
bash docker/hierachain.sh stress docker --reuse

# 3. Clean up cluster and containers
bash docker/hierachain.sh down docker
```
