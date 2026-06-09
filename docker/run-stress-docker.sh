#!/bin/bash
# HieraChain Stress Test Runner - Docker Compose
# Runs stress tests on a Docker Compose cluster with IPFS private swarm

set -e

# Configuration
DURATION=${1:-60}
REAL_REQUESTS="true"
TARGET="gateway:80,node1:2661,node2:2661,node3:2661,node4:2661"
COMPOSE_FILE="docker/docker-compose.yml"
IPFS_DIR="docker/ipfs"
STRESS_PYTEST_TARGET=${STRESS_PYTEST_TARGET:-tests/stress/}

# Reuse an already set up cluster by default (do not rebuild or restart containers)
# Set REUSE_EXISTING_CLUSTER=false to force a fresh build/up. Optionally set FORCE_RECREATE=true to force-recreate.
REUSE_EXISTING_CLUSTER=${REUSE_EXISTING_CLUSTER:-true}
FORCE_RECREATE=${FORCE_RECREATE:-false}

echo "========================================"
echo " HieraChain Docker Compose Stress Test"
echo "========================================"
echo "Duration: ${DURATION}s"
echo "Target:   ${TARGET}"
echo ""

# Ensure IPFS swarm.key exists
if [ ! -f "$IPFS_DIR/swarm.key" ]; then
    echo "[Pre] Generating IPFS swarm.key..."
    mkdir -p "$IPFS_DIR"
    SWARM_KEY_HEX=$(openssl rand -hex 32)
    {
      echo "/key/swarm/psk/1.0.0/"
      echo "/base16/"
      echo "$SWARM_KEY_HEX"
    } > "$IPFS_DIR/swarm.key"
    echo "  ✅ swarm.key generated"
fi

# Export IPFS encryption key if not already set
if [ -z "${IPFS_ENCRYPTION_KEY:-}" ]; then
    export IPFS_ENCRYPTION_KEY=$(openssl rand -hex 32)
    echo "[Pre] IPFS_ENCRYPTION_KEY generated"
fi

# Step pre: Generate identities (including rogue for config completeness)
if [ "${REUSE_EXISTING_CLUSTER}" != "true" ]; then
  echo "[0/4] Generating node identities (node1–node4 + rogue)..."
  INCLUDE_ROGUE_NODE=true python3 docker/scripts/generate_node_identities.py
  echo "  ✅ Identities ready"
else
  echo "[0/4] Skipping identity generation (REUSE_EXISTING_CLUSTER=true)"
fi

# Step 1: Rebuild images with latest code (optional)
if [ "${REUSE_EXISTING_CLUSTER}" != "true" ]; then
  echo "[1/4] Building Docker images..."
  docker compose -f "$COMPOSE_FILE" build
  echo "  ✅ Build complete"
else
  echo "[1/4] Skipping Docker build (REUSE_EXISTING_CLUSTER=true)"
fi

if [ "${REUSE_EXISTING_CLUSTER}" != "true" ]; then
  echo "[2/4] Starting legitimate 4-node cluster..."
  # Do not enable security-test profile here; only legit services are started
  UP_ARGS=""
  if [ "${FORCE_RECREATE}" = "true" ]; then
    UP_ARGS="--force-recreate"
  fi
  docker compose -f "$COMPOSE_FILE" up -d ${UP_ARGS} node1 node2 node3 node4 gateway redis ipfs-node1 ipfs-node2 ipfs-node3 ipfs-node4
else
  echo "[2/4] Reusing existing 4-node cluster (no restart)"
fi

# Wait for cluster health
echo "[3/4] Waiting for cluster to be healthy..."
MAX_RETRIES=30
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if docker compose -f "$COMPOSE_FILE" ps | grep -q "Up"; then
        HEALTHY=0
        NODES_READY=true
        for node in node1 node2 node3 node4; do
            if docker compose -f "$COMPOSE_FILE" exec -T "$node" \
                python -c "import urllib.request; urllib.request.urlopen('http://localhost:2661/api/v1/health', timeout=5)" 2>/dev/null; then
                HEALTHY=$((HEALTHY + 1))
            fi
        done
        for ipfs_node in ipfs-node1 ipfs-node2 ipfs-node3 ipfs-node4; do
            if ! docker compose -f "$COMPOSE_FILE" exec -T "$ipfs_node" \
                ipfs id 2>/dev/null >/dev/null; then
                NODES_READY=false
            fi
        done
        if [ "$HEALTHY" -ge 4 ] && [ "$NODES_READY" = true ]; then
            echo "  ✅ All 4 nodes and IPFS swarm healthy"
            break
        fi
    fi
    sleep 3
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
    echo "  ❌ Cluster failed to become healthy"
    if [ "${REUSE_EXISTING_CLUSTER}" = "true" ]; then
        echo "  Hint: Cluster may not be running. Start it first, or rerun with REUSE_EXISTING_CLUSTER=false to auto-start."
    fi
    docker compose -f "$COMPOSE_FILE" logs --tail=20 || true
    exit 1
fi

# Step 4: Run stress test
echo ""
echo "[4/4] Starting normal stress test (excluding security suite) + IPFS integration..."
docker compose -f "$COMPOSE_FILE" run --rm stress-tester \
    bash -c "
        mkdir -p /app/log/report
        export TARGET_NODES='$TARGET'
        export TEST_DURATION='$DURATION'
        export REAL_REQUESTS='$REAL_REQUESTS'
        export HRC_IPFS_ENABLED=true
        export HRC_IPFS_HOST=/dns4/ipfs-node1/tcp/5001
        uv run pytest ${STRESS_PYTEST_TARGET} -v \
            --ignore=tests/stress/security \
            --html=/app/log/report/docker_stress_report.html \
            --self-contained-html
    "

echo ""
echo "========================================"
echo " Stress test complete!"
echo "========================================"
echo "Normal report:  log/report/docker_stress_report.html"
