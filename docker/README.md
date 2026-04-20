# HieraChain Docker Configuration

This directory contains Docker and Kubernetes configurations for deploying and testing HieraChain.

---

## Directory Structure

```
docker/
├── Dockerfile                     # HieraChain Docker image definition
├── docker-compose.test.yml       # Docker Compose for stress testing (4 nodes)
├── docker-compose.k8s-stress.yml # Docker Compose for Kubernetes stress testing
├── kind-config.yaml              # Kind (Kubernetes in Docker) cluster config
├── nginx-example.conf            # Nginx reverse proxy with SSL/HTTP3
└── k8s/                          # Kubernetes manifests
    ├── kustomization.yaml
    ├── namespace.yaml
    ├── node-deployment.yaml
    ├── node-service.yaml
    ├── persistent-volumes.yaml
    └── templates/
```

---

## Prerequisites

* Docker 20.10+
* Docker Compose v2+
* (For Kubernetes) kubectl, kind, kustomize

---

## Building the Docker Image

Build the HieraChain Docker image:

```bash
docker build --no-cache -t hierachain:latest -f docker/Dockerfile .
```

---

## Docker Compose

### Stress Testing (4 Nodes)

Run stress tests with 4 HieraChain nodes (1 CPU, 1GiB RAM each):

**Build and run stress tests with HTML report:**

```bash
docker compose -f docker/docker-compose.test.yml --profile stress-test run stress-tester python -m pytest tests/stress/ -v --html=/app/log/report/stress_test_report.html --self-contained-html
```

**Run real network stress tests:**

```bash
docker compose -f docker/docker-compose.test.yml --profile stress-test run stress-tester python -m pytest tests/stress/test_real_network.py -v -s
```

**Run without HTML report:**

```bash
docker compose -f docker/docker-compose.test.yml --profile stress-test run stress-tester
```

**Start all nodes for testing:**

```bash
docker compose -f docker/docker-compose.test.yml up -d
```

**View logs:**

```bash
docker compose -f docker/docker-compose.test.yml logs -f
```

**Stop and clean up:**

```bash
docker compose -f docker/docker-compose.test.yml down --remove-orphans
```

---

## Kubernetes Deployment

> **Recommendation:** Use Docker Compose for local development. Use Kubernetes when you need a production-like environment.

### Quick Start

```bash
# Build image
docker build --no-cache -t hierachain:latest -f docker/Dockerfile .

# Create Kind cluster
kind create cluster --config docker/kind-config.yaml

# Resource limit for each Node of K8s (1 CPU, 1GiB RAM)
docker update --cpus 1 --memory 1g --memory-swap 1g hiera-cluster-control-plane
docker update --cpus 1 --memory 1g --memory-swap 1g hiera-cluster-worker
docker update --cpus 1 --memory 1g --memory-swap 1g hiera-cluster-worker2
docker update --cpus 1 --memory 1g --memory-swap 1g hiera-cluster-worker3

# Load image into cluster
kind load docker-image hierachain:latest --name hiera-cluster

# Deploy to Kubernetes
kubectl apply -k docker/k8s/

# Wait for pods to be ready
kubectl wait --for=condition=ready pod -l app=hierachain -n hierachain --timeout=120s

# Expose the API to local host
kubectl port-forward service/hierachain-api 2661:2661 -n hierachain --address 0.0.0.0

# Test API
curl http://localhost:2661/api/v1/health
```

### Kubernetes Stress Testing

Run stress tests targeting K8s nodes:

```bash
docker compose -f docker/docker-compose.k8s-stress.yml --profile stress-test run --build stress-tester python -m pytest tests/stress/ -v --html=/app/log/report/k8s_stress_test_report.html --self-contained-html
```

### Cleanup Kubernetes

```bash
kubectl delete -k docker/k8s/
kind delete cluster --name hiera-cluster
```

---

## Kind Configuration

The [`kind-config.yaml`](kind-config.yaml) defines a local Kubernetes cluster with:

* 1 control-plane node
* 3 worker nodes

This is useful for testing Kubernetes manifests locally before deploying to a real cluster.

---

## Nginx Reverse Proxy

The [`nginx-example.conf`](nginx-example.conf) provides an example Nginx configuration with:

* **SSL/TLS** with modern protocols (TLSv1.2, TLSv1.3)
* **HTTP/3 (QUIC)** support
* **WebSocket** proxy support
* **Security headers** (HSTS, X-Frame-Options, X-Content-Type-Options)
* **Client max body size**: 5MB

To use this configuration:

1. Generate SSL certificates:
   ```bash
   # Using Let's Encrypt (example)
   certbot certonly --nginx -d api.hierachain.io
   ```

2. Update the certificate paths in the config:
   ```nginx
   ssl_certificate /etc/letsencrypt/live/api.hierachain.io/fullchain.pem;
   ssl_certificate_key /etc/letsencrypt/live/api.hierachain.io/privkey.pem;
   ```

3. Update the server name:
   ```nginx
   server_name api.hierachain.io;
   ```

4. Start Nginx:
   ```bash
   nginx -c /path/to/docker/nginx-example.conf
   ```

---

## Environment Variables

Key environment variables used in the containers:

| Variable | Description | Default |
|----------|-------------|---------|
| `NODE_ID` | Unique node identifier | - |
| `NODE_PORT` | P2P communication port | 5001 |
| `PEERS` | Comma-separated list of peer addresses | - |
| `LOG_LEVEL` | Logging level | INFO |
| `DATABASE_PATH` | Path to SQLite database | /app/data/hierachain.db |
| `HRC_API_HOST` | API server host | 0.0.0.0 |
| `TARGET_NODES` | Target nodes for stress testing | - |

---

## Ports

| Port | Service |
|------|---------|
| 5001-5004 | P2P node communication |
| 2661-2664 | API server |
| 443 | Nginx HTTPS (example) |

---

## Additional Resources

* **Tests**: See [`tests/README.md`](../tests/README.md) for test execution details
* **Documentation**: See [`docs/DEV_GUIDE.md`](../docs/DEV_GUIDE.md) for full development guide
* **Kubernetes Manifests**: See [`docker/k8s/`](k8s/) directory for K8s configurations