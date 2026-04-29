#!/bin/bash
# HieraChain Quick Poison Pill Test (API v3 focus)
# Bypasses full stress suite to validate security hardening quickly.

set -e

# Project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${PROJECT_ROOT}/docker/docker-compose.test.yml"

echo "=========================================================="
echo " HieraChain Security Hardening Validation (Poison Pill)"
echo "=========================================================="

# 1. Build optimized images
echo "[1/4] Building docker images..."
docker compose -f "$COMPOSE_FILE" build --parallel --quiet

# 2. Reset cluster state
echo "[2/4] Resetting cluster state..."
docker compose -f "$COMPOSE_FILE" down --remove-orphans -v
docker compose -f "$COMPOSE_FILE" up -d node1 node2 node3 node4

# 3. Wait for nodes to be healthy
echo "[3/4] Waiting for cluster to reach high-availability state..."
MAX_RETRIES=30
RETRIES=0
until [ $RETRIES -ge $MAX_RETRIES ]
do
    # Compatibility fix: Check for '(healthy)' string in ps output
    HEALTHY_NODES=$(docker compose -f "$COMPOSE_FILE" ps | grep -c "(healthy)") || true
    if [ "$HEALTHY_NODES" -ge 4 ]; then
        echo "  ✅ All 4 nodes are healthy!"
        break
    fi
    echo "  ... waiting ($RETRIES/$MAX_RETRIES) - $HEALTHY_NODES/4 healthy"
    RETRIES=$((RETRIES+1))
    sleep 2
done

if [ "$RETRIES" -ge "$MAX_RETRIES" ]; then
    echo "❌ ERROR: Cluster failed to start within timeout."
    docker compose -f "$COMPOSE_FILE" logs
    exit 1
fi

# 4. Execute targeted tests
echo "[4/4] Executing targeted API v3 Poison Pill tests..."
docker compose -f "$COMPOSE_FILE" --profile stress-test run --rm stress-tester \
    bash -c "
        export REAL_REQUESTS=true
        export LOG_LEVEL=DEBUG
        # Focus on API v3 security hardening
        uv run pytest tests/stress/test_poison_pill.py -v -k 'test_v3_secure_rejection or test_poison_rejection'
    "

echo ""
echo "=========================================================="
echo " ✅ Security Validation Complete!"
echo "=========================================================="
# docker compose -f "$COMPOSE_FILE" down
