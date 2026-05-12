#!/bin/bash
# HieraChain Stress Test Runner - Docker Compose
# Runs stress tests on a Docker Compose cluster

set -e

# Configuration
DURATION=${1:-60}
REAL_REQUESTS="true"
TARGET="gateway:80,node1:2661,node2:2661,node3:2661,node4:2661"
COMPOSE_FILE="docker/docker-compose.test.yml"

echo "========================================"
echo " HieraChain Docker Compose Stress Test"
echo "========================================"
echo "Duration: ${DURATION}s"
echo "Target:   ${TARGET}"
echo ""

# Step 1: Rebuild images with latest code, then restart cluster
echo "[1/4] Building Docker images..."
docker compose -f "$COMPOSE_FILE" build
echo "  ✅ Build complete"

echo "[2/4] Restarting cluster..."
docker compose -f "$COMPOSE_FILE" up -d --force-recreate

# Wait for cluster health
echo "[3/4] Waiting for cluster to be healthy..."
MAX_RETRIES=30
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if docker compose -f "$COMPOSE_FILE" ps | grep -q "Up"; then
        HEALTHY=0
        for node in node1 node2 node3 node4; do
            if docker compose -f "$COMPOSE_FILE" exec -T "$node" \
                python -c "import urllib.request; urllib.request.urlopen('http://localhost:2661/api/v1/health', timeout=5)" 2>/dev/null; then
                HEALTHY=$((HEALTHY + 1))
            fi
        done
        if [ "$HEALTHY" -ge 4 ]; then
            echo "  ✅ All 4 nodes healthy"
            break
        fi
    fi
    sleep 3
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
    echo "  ❌ Cluster failed to become healthy"
    docker compose -f "$COMPOSE_FILE" logs --tail=20
    exit 1
fi

# Step 4: Run stress test
echo ""
echo "[4/4] Starting stress test..."
docker compose -f "$COMPOSE_FILE" run --rm stress-tester \
    bash -c "
        mkdir -p /app/log/report
        export TARGET_NODES='$TARGET'
        export TEST_DURATION='$DURATION'
        export REAL_REQUESTS='$REAL_REQUESTS'
        uv sync --extra dev 2>&1 | tail -3; uv run pytest tests/stress/ -v \
            --html=/app/log/report/docker_stress_report.html \
            --self-contained-html
    "

echo ""
echo "========================================"
echo " Stress test complete!"
echo "========================================"
echo "Report: log/report/docker_stress_report.html"
