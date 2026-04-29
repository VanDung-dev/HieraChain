#!/bin/bash
# HieraChain Attack Simulation Runner
# Focuses on DDoS, Poison Pill, and Real Network Stress

DURATION=${1:-20}
TARGET="node1:2661,node2:2661,node3:2661,node4:2661"
COMPOSE_FILE="docker/docker-compose.test.yml"
REAL_REQUESTS="true"

echo "========================================"
echo " HieraChain Attack Simulation"
echo "========================================"
echo "Duration: ${DURATION}s"
echo "Target:   ${TARGET}"
echo ""

# Step 1: Check environment
echo "[1/2] Checking Docker Compose cluster..."
if ! docker compose -f "$COMPOSE_FILE" ps | grep -q "Up"; then
    echo "ERROR: Docker Compose cluster is not running!"
    exit 1
fi
echo "  ✅ Cluster is ready"

# Step 2: Run targeted attack tests
echo ""
echo "[2/2] Launching Attack Simulation..."
docker compose -f "$COMPOSE_FILE" run --rm stress-tester \
    bash -c "
        export TARGET_NODES='$TARGET'
        export TEST_DURATION='$DURATION'
        export REAL_REQUESTS='$REAL_REQUESTS'
        uv run pytest tests/stress/ -v \
            --html=/app/log/report/docker_compose_stress_report.html \
            --self-contained-html
    "

echo ""
echo "========================================"
echo " Attack Simulation Complete!"
echo "========================================"
echo "Report: log/report/docker_compose_stress_report.html"
