#!/bin/bash
# HieraChain Stress Test Runner - OrbStack K8s

set -e

DURATION=${1:-60}
TARGET="host.docker.internal:32661"
NAMESPACE="hierachain"
COMPOSE_FILE="docker/docker-compose.k8s-stress.yml"

echo "========================================"
echo " HieraChain OrbStack K8s Stress Test"
echo "========================================"
echo "Duration: ${DURATION}s"
echo "Target:   ${TARGET}"
echo ""

echo "[1/2] Checking Kubernetes environment..."
if ! kubectl get pods -n "$NAMESPACE" -l app=hierachain 2>/dev/null | grep -q "Running"; then
    echo "ERROR: HieraChain pods not running. Deploy first: docker/setup-orb-k8s.sh"
    exit 1
fi
echo "  Kubernetes cluster is ready"

echo ""
echo "[2/2] Starting stress test..."
docker --context=orbstack compose -f "$COMPOSE_FILE" run --rm --build stress-tester \
    bash -c "
        mkdir -p /app/log/report
        export TARGET_NODES='$TARGET'
        export TEST_DURATION='$DURATION'
        export K8S_NAMESPACE='$NAMESPACE'
        uv run pytest tests/stress/ -v \
            --html=/app/log/report/orb_k8s_stress_report.html \
            --self-contained-html
    "

echo ""
echo "========================================"
echo " Stress test complete!"
echo "========================================"
echo "Report: log/report/orb_k8s_stress_report.html"