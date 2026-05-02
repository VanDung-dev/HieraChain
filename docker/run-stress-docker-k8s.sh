#!/bin/bash
# HieraChain Stress Test Runner - Kubernetes
# Runs stress tests on a Kubernetes cluster

set -e

# Configuration
DURATION=${1:-60}
REAL_REQUESTS="true"
TARGET="host.docker.internal:32661"
NAMESPACE="hierachain"
COMPOSE_FILE="docker/docker-compose.k8s-stress.yml"
WEB2_TARGET="localhost:32660" # NodePort for web2-node

echo "========================================"
echo " HieraChain K8s Stress Test"
echo "========================================"
echo "Duration: ${DURATION}s"
echo "Target:   ${TARGET}"
echo "Web2 Target: ${WEB2_TARGET}"
echo ""

# Step 1: Check environment
echo "[1/2] Checking Kubernetes environment..."
if ! kubectl get pods -n "$NAMESPACE" -l app=hierachain | grep -q "Running"; then
    echo "ERROR: HieraChain pods are not running in namespace: $NAMESPACE"
    echo "Deploy first with: docker/setup-k8s.sh"
    exit 1
fi
echo "  ✅ Kubernetes cluster is ready"

# Step 2: Run stress test
echo ""
echo "[2/2] Starting stress test..."
docker compose -f "$COMPOSE_FILE" run --rm --build stress-tester \
    bash -c "
        export TARGET_NODES='$TARGET'
        export TEST_DURATION='$DURATION'
        export REAL_REQUESTS='$REAL_REQUESTS'
        export K8S_NAMESPACE='$NAMESPACE'
        python -m pytest tests/stress/ -v \
            --html=/app/log/report/k8s_stress_report.html \
            --self-contained-html
    "

echo ""
echo "========================================"
echo " Stress test complete!"
echo "========================================"
echo "Report: log/report/k8s_stress_report.html"
