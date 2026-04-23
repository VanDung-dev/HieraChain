# 📊 HieraChain Stress Testing

Docker and Kubernetes configurations dedicated to performance benchmarking (throughput) and stability testing of HieraChain under high load.

> [!IMPORTANT]
> This directory is intended for **Stress Testing** and performance analysis only. It is NOT a production deployment guide.

---

## 📁 Stress Test Tools

```text
docker/
├── setup-docker-compose.sh         # Initialize a 4-node cluster (Docker Compose)
├── run-stress-docker-compose.sh    # Run stress tests on Docker Compose
├── setup-k8s.sh                    # Initialize a 4-node cluster on Kubernetes (Kind)
├── run-stress-k8s.sh               # Run stress tests on Kubernetes
├── docker-compose.test.yml         # Local cluster configuration
└── k8s/                            # Kubernetes manifests for testing
```

---

## 🚀 Getting Started

### 1. Using Docker Compose (Fastest)

Ideal for testing business logic and basic throughput on a local machine.

```bash
# Step 1: Start the 4-node cluster
docker/setup-docker-compose.sh

# Step 2: Run the stress test (default: 60 seconds)
docker/run-stress-docker-compose.sh
```

**Utility Commands:**

* `docker/setup-docker-compose.sh`: Rebuilds and restarts the cluster.
* `docker compose -f docker/docker-compose.test.yml logs -f`: View live logs.
* `docker compose -f docker/docker-compose.test.yml down -v`: Full cleanup.

---

### 2. Using Kubernetes (Realistic Simulation)

Uses [Kind](https://kind.sigs.k8s.io/) to create a local cluster with specific resource limits (**1 CPU / 1GB RAM per node**) for accurate benchmarking.

```bash
# Step 1: Initialize cluster and deploy nodes
docker/setup-k8s.sh

# Step 2: Run the stress test
docker/run-stress-k8s.sh
```

**Cleanup:**

```bash
kind delete cluster --name hiera-cluster
```

---

## 📈 Analysis & Reports

After each test run, a detailed HTML report is generated for performance analysis:

* **Location:** `log/report/`
* **Key Metrics:**

    * **EPS (Events Per Second)**: Throughput of events committed to the chain.
    * **Latency**: Average time for an event to achieve consensus and commit.
    * **Success Rate**: Percentage of successfully processed events under load.

---

## ⚙️ Configuration

Performance can be tuned via environment variables in `docker/k8s/configmap.yaml` or `docker/docker-compose.test.yml`:

| Variable | Description | Recommendation |
| :--- | :--- | :--- |
| `HRC_RATE_LIMIT` | API Rate limiting | Set to `false` for stress testing |
| `LOG_LEVEL` | Logging verbosity | Use `WARNING` for maximum performance |
| `HRC_STORAGE_BACKEND` | Storage engine | `sqlite` (default) or `redis` |

---

## 🔧 Troubleshooting

* **Nodes not ready**: Check connectivity with `curl http://localhost:2661/api/v1/health`.
* **429 Errors**: Ensure `HRC_RATE_LIMIT=false` is set in the node configuration.
* **Resource pressure**: Monitor node CPU/RAM usage with `docker stats`.
