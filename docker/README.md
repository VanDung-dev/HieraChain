# 📊 HieraChain Stress Testing Infrastructure

HieraChain provides a comprehensive suite of Docker, Kubernetes, and Podman configurations dedicated to high-performance benchmarking (throughput) and stability testing.

> [!IMPORTANT]
> This infrastructure is optimized for **Stress Testing** and performance analysis. It implements "Guaranteed QoS" and "CPU Pinning" to ensure accurate and jitter-free results.

---

## 📁 Infrastructure Overview

```text
docker/
├── setup-docker.sh                 # Docker Compose: build + start 4-node cluster
├── run-stress-docker.sh            # Docker Compose: run stress test
├── setup-docker-k8s.sh             # Docker + Kind: build + deploy K8s cluster
├── run-stress-docker-k8s.sh        # Docker + Kind: run stress test on K8s
├── setup-podman.sh                 # Podman Compose: build + start 4-node cluster
├── run-stress-podman.sh            # Podman Compose: run stress test
├── setup-podman-k8s.sh             # Podman + Kind: build + deploy K8s cluster
├── run-stress-podman-k8s.sh        # Podman + Kind: run stress test on K8s
├── k8s/                            # Kubernetes manifests (CPU Pinned)
├── podman-compose.yml              # Podman-optimized configuration
└── default.podman.conf.template    # Rootless-safe Nginx template
```

---

## 🚀 Deployment Modes

HieraChain supports two container runtimes (**Docker** and **Podman**) across two orchestration modes (**Compose** and **Kubernetes**).

| Mode | Docker | Podman |
|------|--------|--------|
| **Compose** (4-node cluster) | `docker/setup-docker.sh` → `docker/run-stress-docker.sh` | `docker/setup-podman.sh` → `docker/run-stress-podman.sh` |
| **Kubernetes** (Kind, 5-node) | `docker/setup-docker-k8s.sh` → `docker/run-stress-docker-k8s.sh` | `docker/setup-podman-k8s.sh` → `docker/run-stress-podman-k8s.sh` |

### 1. Docker Compose (Classic)

Ideal for testing business logic and basic throughput on a local machine.

```bash
docker/setup-docker.sh
docker/run-stress-docker.sh
```

### 2. Podman Compose (Secure & Rootless)

Designed for enterprise environments with strict security policies.

```bash
docker/setup-podman.sh
docker/run-stress-podman.sh
```

### 3. Kubernetes — Docker (Enterprise Simulation)

Uses [Kind](https://kind.sigs.k8s.io/) with Docker provider. Implements **CPU Pinning** (1 Core per Node) for high-fidelity throughput testing.

```bash
docker/setup-docker-k8s.sh
docker/run-stress-docker-k8s.sh
```

### 4. Kubernetes — Podman (Enterprise Simulation)

Uses [Kind](https://kind.sigs.k8s.io/) with Podman provider.

```bash
docker/setup-podman-k8s.sh
docker/run-stress-podman-k8s.sh
```

---

## Performance Optimization: CPU Pinning

To ensure HieraChain nodes are not affected by CPU context switching or resource contention, we have implemented **Guaranteed QoS**:

* **K8s:** Nodes are configured with `requests == limits` for CPU and RAM using integer values.
*   **Podman:** Uses `cpuset` to bind each node container to a specific physical core ID.
*   **Docker:** Uses `cpus: '1.0'` limit to prevent CPU over-subscription.

---

## Analysis & Reports

Detailed HTML reports are generated in `log/report/` after each run:

*   **EPS (Events Per Second)**: Real-world throughput.
*   **Latency**: Time to reach consensus (BFT/PoA).
*   **Success Rate**: Stability under extreme load.

---

## macOS Only: Colima over Docker Desktop

> **Note:** This section is **macOS only**. Linux users can skip it — Docker Engine runs natively there.
>
> Podman users on macOS: Podman runs via `podman machine` and does not need Colima.

Docker Desktop on macOS runs inside a Linux VM (HyperKit/Virtualization.framework), adding significant overhead. For stress testing, **Colima** (a lightweight container runtime on Lima VM) consistently outperforms Docker Desktop.

### Why Colima?

| Aspect | Docker Desktop | Colima |
|--------|---------------|--------|
| Idle RAM | ~1.5–2.5 GB | ~200–500 MB |
| VM startup | 30–60 sec | ~2 sec |
| Filesystem I/O | Moderate (virtiofs) | Faster (Lima 9p) |
| CPU overhead | Higher (extra layers) | Lower (minimal VM) |
| Stress test throughput | Reference | **15–30% faster** |

### Installation

```bash
brew install colima
```

### Recommended Configurations

#### macOS (Apple Silicon / Intel)

Minimum recommended for HieraChain cluster + stress testing:

```bash
colima start \
  --cpu 8 \
  --memory 16 \
  --disk 60 \
  --vm-type=vz \
  --vz-rosetta \
  --mount-type virtiofs
```

| Flag            | Value | Purpose                                            |
|-----------------|-------|----------------------------------------------------|
| `--cpu`         | 8 | Distribute across 4 HieraChain nodes + gateway + redis |
| `--memory`      | 16 GiB | Sufficient for all containers + OS overhead        |
| `--disk`        | 60 GiB | Docker images, Kind node images, stress test logs  |
| `--vm-type`     | `vz` | Apple Virtualization.framework (faster than QEMU)  |
| `--vz-rosetta`  | enabled | Run AMD64 images via Rosetta 2 if needed           |
| `--mount-type`  | `virtiofs` | Improved filesystem I/O performance on macOS |

### Switching from Docker Desktop to Colima

```bash
# Switch Docker context
docker context use colima

# Verify
docker info | grep "Server Version"

# Build and deploy as usual
bash docker/setup-docker-k8s.sh
```

### Switch back to Docker Desktop

```bash
colima stop
docker context use default
```

### Cleanup

```bash
colima stop
colima delete   # removes the VM, freeing ~60 GB disk
```

---

## ⚙️ Global Configuration

| Variable | Description | Recommendation |
| :--- | :--- | :--- |
| `EXPLORER_TOKEN` | Secure token for monitor access | Auto-generated during setup |
| `HRC_RATE_LIMIT` | API Rate limiting | Set to `false` for stress testing |
| `LOG_LEVEL` | Logging verbosity | Use `WARNING` for max performance |

---

## 🔧 Cleanup Commands

| Container Runtime | Compose Cluster | Kubernetes (Kind) |
|-------------------|----------------|-------------------|
| **Docker** | `docker compose -f docker/docker-compose.test.yml down -v` | `kind delete cluster --name hiera-cluster` |
| **Podman** | `podman compose -f docker/podman-compose.yml down -v` | `kind delete cluster --name hiera-cluster-podman` |
