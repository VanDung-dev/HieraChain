#!/bin/bash
# HieraChain Stress Test Runner - Docker Compose
# Runs stress tests on a Docker Compose cluster

set -e

# Configuration
DURATION=${1:-60}
REAL_REQUESTS="true"
TARGET="node1:2661,node2:2661,node3:2661,node4:2661"
COMPOSE_FILE="docker/docker-compose.test.yml"

echo "========================================"
echo " HieraChain Docker Compose Stress Test"
echo "========================================"
echo "Duration: ${DURATION}s"
echo "Target:   ${TARGET}"
echo ""

# Step 1: Check environment
echo "[1/2] Checking Docker Compose cluster..."
if ! docker compose -f "$COMPOSE_FILE" ps | grep -q "Up"; then
    echo "ERROR: Docker Compose cluster is not running!"
    echo "Start it first with: docker/setup-docker-compose.sh"
    exit 1
fi
echo "  ✅ Cluster is ready"

# Step 2: Run stress test
echo ""
echo "[2/2] Starting stress test..."
docker compose -f "$COMPOSE_FILE" run --rm stress-tester \
    bash -c "
        export TARGET_NODES='$TARGET'
        export TEST_DURATION='$DURATION'
        export REAL_REQUESTS='$REAL_REQUESTS'
        python -m pytest tests/stress/ -v \
            --html=/app/log/report/docker_compose_stress_report.html \
            --self-contained-html
    "

echo ""
echo "========================================"
echo " Stress test complete!"
echo "========================================"
echo "Report: log/report/docker_compose_stress_report.html"
