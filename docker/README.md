# 📊 HieraChain Stress Testing Infrastructure

HieraChain provides a comprehensive suite of Docker, Kubernetes, and Podman configurations dedicated to high-performance benchmarking (throughput) and stability testing.

> [!IMPORTANT]
> This infrastructure is optimized for **Stress Testing** and performance analysis. It implements "Guaranteed QoS" and "CPU Pinning" to ensure accurate and jitter-free results.

---

## 📁 Infrastructure Overview

```text
docker/
├── setup-docker-compose.sh         # Initialize Docker Compose cluster
├── run-stress-docker-compose.sh    # Run stress tests on Docker
├── setup-k8s.sh                    # Initialize K8s cluster (Kind)
├── run-stress-k8s.sh               # Run stress tests on Kubernetes
├── setup-podman.sh                 # Initialize Pure Podman cluster
├── run-stress-podman.sh            # Run stress tests on Podman
├── setup-podman-k8s.sh             # Initialize Podman K8s (Play Kube)
├── run-stress-podman-k8s.sh        # Run stress tests on Podman K8s
├── k8s/                            # Kubernetes manifests (CPU Pinned)
├── podman-compose.yml              # Podman-optimized configuration
└── default.podman.conf.template    # Rootless-safe Nginx template
```

---

## 🚀 Deployment Modes

### 1. Docker Compose (Classic)
Ideal for testing business logic and basic throughput on a local machine.
```bash
docker/setup-docker-compose.sh
docker/run-stress-docker-compose.sh
```

### 2. Kubernetes (Enterprise Simulation)
Uses [Kind](https://kind.sigs.k8s.io/) or a real cluster. Implements **CPU Pinning** (1 Core per Node) for high-fidelity throughput testing.
```bash
docker/setup-k8s.sh
docker/run-stress-k8s.sh
```

### 3. Podman (Secure & Rootless)
Designed for enterprise environments with strict security policies. Supports both Compose and Native K8s manifests.
```bash
# Pure Podman (Compose)
docker/setup-podman.sh
docker/run-stress-podman.sh

# Podman K8s (Play Kube)
docker/setup-podman-k8s.sh
docker/run-stress-podman-k8s.sh
```

---

## ⚡ Performance Optimization: CPU Pinning

To ensure HieraChain nodes are not affected by CPU context switching or resource contention, we have implemented **Guaranteed QoS**:
*   **K8s:** Nodes are configured with `requests == limits` for CPU and RAM using integer values.
*   **Podman:** Uses `cpuset` to bind each node container to a specific physical core ID.
*   **Docker:** Uses `cpus: '1.0'` limit to prevent CPU over-subscription.

---

## 📈 Analysis & Reports

Detailed HTML reports are generated in `log/report/` after each run:
*   **EPS (Events Per Second)**: Real-world throughput.
*   **Latency**: Time to reach consensus (BFT/PoA).
*   **Success Rate**: Stability under extreme load.

---

## ⚙️ Global Configuration

| Variable | Description | Recommendation |
| :--- | :--- | :--- |
| `EXPLORER_TOKEN` | Secure token for monitor access | Auto-generated during setup |
| `HRC_RATE_LIMIT` | API Rate limiting | Set to `false` for stress testing |
| `LOG_LEVEL` | Logging verbosity | Use `WARNING` for max performance |

---

## 🔧 Cleanup Commands

*   **Docker:** `docker compose -f docker/docker-compose.test.yml down -v`
*   **K8s:** `kind delete cluster --name hiera-cluster`
*   **Podman:** `podman compose -f docker/podman-compose.yml down -v`
*   **Podman K8s:** `podman pod rm -f $(podman pod ps -q)`
