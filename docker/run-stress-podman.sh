#!/bin/bash
# HieraChain Stress Test Runner - Podman Compose
# Runs stress tests on a Podman Compose cluster

set -e

# Configuration
DURATION=${1:-60}
REAL_REQUESTS="true"
TARGET="gateway:8080,node1:2661,node2:2661,node3:2661,node4:2661"
COMPOSE_FILE="docker/podman-compose.yml"

echo "========================================"
echo " HieraChain Podman Compose Stress Test"
echo "========================================"
echo "Duration: ${DURATION}s"
echo "Target:   ${TARGET}"
echo ""

# Step 1: Check environment
echo "[1/2] Checking Podman Compose cluster..."
if ! podman compose -f "$COMPOSE_FILE" ps | grep -q "Up"; then
    echo "ERROR: Podman Compose cluster is not running!"
    echo "Start it first with: bash docker/setup-podman.sh"
    exit 1
fi
echo "  ✅ Cluster is ready"

# Step 2: Run stress test
echo ""
echo "[2/2] Starting stress test..."
podman compose -f "$COMPOSE_FILE" run --rm stress-tester \
    bash -c "
        mkdir -p /app/log/report
        export TARGET_NODES='$TARGET'
        export TEST_DURATION='$DURATION'
        export REAL_REQUESTS='$REAL_REQUESTS'
        uv run python -m pytest tests/stress/ -v \
            --html=/app/log/report/podman_stress_report.html \
            --self-contained-html
    "

echo ""
echo "========================================"
echo " Stress test complete!"
echo "========================================"
echo "Report: log/report/podman_stress_report.html"

