#!/bin/bash
# HieraChain Stress Test Runner - Kubernetes (Podman Optimized)
# Runs stress tests on a Kubernetes cluster using Podman
# Targets K8s nodes via NodePort through Podman's host bridge

set -e

# Configuration
DURATION=${1:-60}
REAL_REQUESTS="true"
# Podman's equivalent to host.docker.internal is host.containers.internal
TARGET="host.containers.internal:32661"
NAMESPACE="hierachain"
# Ensure local tools are in PATH
export PATH="$PWD/docker/bin:$PATH"

COMPOSE_FILE="docker/podman-compose.k8s-stress.yml"
WEB2_TARGET="localhost:32660" # NodePort for web2-node

echo "========================================"
echo " HieraChain K8s Stress Test (Podman)"
echo "========================================"
echo "Duration: ${DURATION}s"
echo "Target:   ${TARGET}"
echo "Web2 Target: ${WEB2_TARGET}"
echo ""

# Step 1: Check environment
echo "[1/2] Checking Kubernetes environment..."
if ! kubectl get pods -n "$NAMESPACE" -l app=hierachain | grep -q "Running"; then
    echo "ERROR: HieraChain pods are not running in namespace: $NAMESPACE"
    echo "Deploy first with: bash docker/setup-podman-k8s.sh"
    exit 1
fi
echo "  ✅ Kubernetes cluster is ready"

# Step 2: Run stress test
echo ""
echo "[2/2] Starting stress test via Podman..."
podman compose -f "$COMPOSE_FILE" run --rm stress-tester \
    bash -c "
        mkdir -p /app/log/report
        export TARGET_NODES='$TARGET'
        export TEST_DURATION='$DURATION'
        export REAL_REQUESTS='$REAL_REQUESTS'
        export K8S_NAMESPACE='$NAMESPACE'
        uv run python -m pytest tests/stress/ -v \
            --html=/app/log/report/podman_k8s_stress_report.html \
            --self-contained-html
    "

echo ""
echo "========================================"
echo " Stress test complete!"
echo "========================================"
echo "Report: log/report/podman_k8s_stress_report.html"

