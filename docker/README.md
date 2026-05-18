# HieraChain Stress Testing Infrastructure

HieraChain provides container runtimes dedicated to high-performance benchmarking and stability testing.

---

## Platform Requirements

| Platform | Container Runtime | Notes |
|----------|------------------|-------|
| **macOS** | Docker Desktop / Colima / OrbStack | macOS cannot run Docker natively, requires VM layer |
| **Linux** | Docker / Podman | Native container support, no VM required |

---

## Infrastructure Overview

```
docker/
├── setup-docker.sh           # Docker Compose: 4-node cluster
├── run-stress-docker.sh      # Docker Compose: stress test
│
├── setup-podman.sh           # Podman Compose: 4-node cluster
├── run-stress-podman.sh      # Podman Compose: stress test
│
├── setup-orb-k8s.sh          # OrbStack + Kind: K8s cluster
├── run-stress-orb-k8s.sh     # OrbStack + Kind: stress test
├── docker-compose.k8s-stress.yml
│
├── k8s/                      # Kubernetes manifests
├── kind-config.yaml
├── docker-compose.test.yml
├── podman-compose.yml
└── default.podman.conf.template
```

---

## macOS: Why You Need a VM Layer

**Problem**: macOS does not support running Docker containers natively (Linux-only).  
**Solution**: Use a lightweight virtualization layer to run Linux containers.

| Tool | Type | Best For | Install |
|------|------|----------|---------|
| **Docker Desktop** | Full VM + Docker | Default choice, includes UI | `brew install --cask docker` |
| **Podman** | Rootless (requires VM) | No daemon, rootless by default | `brew install podman` |
| **Colima** | Lightweight VM | Minimal overhead, CLI-only | `brew install colima` |
| **OrbStack** | Lightweight VM + K8s | Fast startup, K8s support | `brew install orbstack` |

### macOS Quick Start

```bash
# Option 1: Docker Desktop (recommended for beginners)
docker context use default
docker/setup-docker.sh
docker/run-stress-docker.sh

# Option 2: Podman Machine (rootless, no daemon)
podman machine init --cpus 8 --memory 16
podman machine start
docker/setup-podman.sh
docker/run-stress-podman.sh

# Option 3 Colima (lightweight, CLI-only)
colima start --cpu 8 --memory 16 --disk 60 --vm-type=vz --vz-rosetta --mount-type virtiofs
docker context use colima
docker/setup-docker.sh
docker/run-stress-docker.sh

# Option 4: OrbStack + Kubernetes (for K8s testing)
docker context use orbstack
docker/setup-orb-k8s.sh
docker/run-stress-orb-k8s.sh
```

---

## Linux: Native Containers

Linux runs Docker/Podman natively without VM overhead.

```bash
# Option 1: Docker
docker/setup-docker.sh
docker/run-stress-docker.sh

# Option 2: Podman (rootless, no daemon required)
docker/setup-podman.sh
docker/run-stress-podman.sh
```

---

## Global Configuration

| Variable | Description | Recommendation |
|----------|-------------|----------------|
| `EXPLORER_TOKEN` | Secure token for monitor | Auto-generated |
| `HRC_RATE_LIMIT` | API rate limiting | `false` for stress testing |

---

## Cleanup Commands

| Runtime | Command |
|---------|---------|
| **Docker** | `docker compose -f docker/docker-compose.test.yml down -v` |
| **Podman** | `podman compose -f docker/podman-compose.yml down -v` |
| **OrbStack K8s** | `kubectl delete namespace hierachain` |
| **Colima** | `colima stop` |
