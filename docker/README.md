# HieraChain Stress Testing Infrastructure

HieraChain provides container runtimes dedicated to high-performance benchmarking and stability testing.

---

## File Layout

```
docker/
├── docker-compose.yml                 # Compose definition (multi-region + WireGuard)
├── docker-compose.k8s-stress.yml      # Kubernetes stress test
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

### Via compose directly

```bash
# Docker Compose
docker compose -f docker/docker-compose.yml up -d
docker compose -f docker/docker-compose.yml down -v
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
