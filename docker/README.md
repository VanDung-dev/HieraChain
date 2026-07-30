# HieraChain Stress Testing Infrastructure

HieraChain provides container runtimes dedicated to high-performance benchmarking and stability testing.

---

## File Layout

```
docker/
├── docker-compose.yml                 # Compose definition (multi-region + WireGuard)
├── docker-compose.podman.yml          # Podman overlay (TUN device passthrough)
├── docker-compose.k8s-stress.yml      # Kubernetes stress test
├── hierachain.sh                      # Unified CLI (recommended)
├── lib/                               # Shared deployment & provider libraries
└── scripts/                           # Helper scripts (identity gen, network tc, lxd setup)
```

---

## Usage

### Via hierachain.sh (recommended)

```bash
# Docker
bash docker/hierachain.sh setup docker
bash docker/hierachain.sh stress docker --reuse
bash docker/hierachain.sh down docker

# Podman (requires pip install podman-compose)
bash docker/hierachain.sh setup podman
bash docker/hierachain.sh stress podman --reuse
bash docker/hierachain.sh down podman

# LXD Containers (only Linux)
bash docker/hierachain.sh setup lxd
bash docker/hierachain.sh stress lxd --reuse
bash docker/hierachain.sh down lxd

# Kubernetes
bash docker/hierachain.sh setup k8s
bash docker/hierachain.sh stress k8s --reuse
bash docker/hierachain.sh down k8s
```

### Via compose directly

```bash
# Docker
docker compose -f docker/docker-compose.yml up -d
docker compose -f docker/docker-compose.yml down -v

# Podman
podman-compose -f docker/docker-compose.yml -f docker/docker-compose.podman.yml up -d
podman-compose -f docker/docker-compose.yml -f docker/docker-compose.podman.yml down -v
```

---

## Platform Requirements

| Platform | Container Runtime | Notes |
|----------|------------------|-------|
| **macOS** | Docker Desktop / Colima / OrbStack | Requires VM container layer (Docker, Podman, K8s) |
| **Linux (Ubuntu/Debian)** | Docker / Podman / LXD | Native support. LXD offers high-density LXC container isolation |

---

## Environment Setup

### 1. LXD Setup (Ubuntu/Linux Only)

LXD provides native system container virtualization for running a full HieraChain cluster in isolated LXC environments without VM overhead.

#### Step 1: Prepare System & Prerequisites
Run the setup script **without `sudo`** (it will request `sudo` permissions when needed):

```bash
bash docker/scripts/setup-ubuntu-lxd.sh
```

#### Step 2: Apply Group Permissions
After setup completes, reload environment and group permissions:

```bash
source ~/.bashrc
newgrp lxd
```

#### Step 3: Deploy & Test Cluster
Now run the unified CLI without `sudo`:

```bash
# 1. Deploy 4-node HieraChain cluster + Redis + Gateway + IPFS Swarm
bash docker/hierachain.sh setup lxd

# 2. Execute stress test suite
bash docker/hierachain.sh stress lxd --reuse

# 3. Clean up cluster and containers
bash docker/hierachain.sh down lxd
```

---

### 2. Docker & Podman Setup

#### macOS Quick Start

```bash
# Docker Desktop
docker context use default
bash docker/hierachain.sh setup docker

# Colima
colima start --cpu 8 --memory 16 --disk 60
docker context use colima
bash docker/hierachain.sh setup docker

# Podman Machine
podman machine init --cpus 8 --memory 16
podman machine start
pip install podman-compose
bash docker/hierachain.sh setup podman

# OrbStack + Kubernetes
orb start
bash docker/hierachain.sh setup k8s
```

#### Linux Quick Start (Docker / Podman)

```bash
# Docker
bash docker/hierachain.sh setup docker

# Podman
pip install podman-compose
bash docker/hierachain.sh setup podman
```
