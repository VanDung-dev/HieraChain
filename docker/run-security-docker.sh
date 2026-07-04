#!/bin/bash
# HieraChain Rogue (node5) Security Test Runner - Docker Compose
# Runs only the adversarial/security tests against a rogue node (node5)

set -e

# Configuration
DURATION=${1:-60}
REAL_REQUESTS="true"
TARGET="gateway:80,node1:2661,node2:2661,node3:2661,node4:2661"
COMPOSE_FILE="docker/docker-compose.yml"
IPFS_DIR="docker/ipfs"
SECURITY_PYTEST_TARGET=${SECURITY_PYTEST_TARGET:-tests/stress/security/}
ROGUE_NODE_TARGET=${ROGUE_NODE_TARGET:-rogue-node:2661}

# Reuse an already set up cluster by default (do not rebuild or restart containers)
# Set REUSE_EXISTING_CLUSTER=false to force a fresh build/up. Optionally set FORCE_RECREATE=true to force-recreate.
REUSE_EXISTING_CLUSTER=${REUSE_EXISTING_CLUSTER:-true}
FORCE_RECREATE=${FORCE_RECREATE:-false}

echo "========================================"
echo " HieraChain Docker Compose Security (node5)"
echo "========================================"
echo "Duration: ${DURATION}s"
echo "Target:   ${TARGET}"
echo "Rogue:    ${ROGUE_NODE_TARGET}"
echo ""

# Advanced adversary options (optional)
# - Set ROGUE_IMPERSONATE_NODE_ID to one of node1|node2|node3|node4 to make rogue-node use a stolen identity
#   The compose file will honor ROGUE_NODE_ID_OVERRIDE and ROGUE_IDENTITY_PATH if provided.
#   We default to node1 so all security tests run out of the box.
export ROGUE_IMPERSONATE_NODE_ID="${ROGUE_IMPERSONATE_NODE_ID:-node1}"

if [ -n "${ROGUE_IMPERSONATE_NODE_ID:-}" ]; then
  export ROGUE_NODE_ID_OVERRIDE="$ROGUE_IMPERSONATE_NODE_ID"
  export ROGUE_IDENTITY_PATH="/app/all-identities/${ROGUE_IMPERSONATE_NODE_ID}/identity.json"
  echo "[Adv] Impersonation enabled: rogue will impersonate '$ROGUE_IMPERSONATE_NODE_ID'"
  echo "[Adv] Using stolen identity path: $ROGUE_IDENTITY_PATH"
else
  echo "[Adv] Impersonation disabled (default rogue identity in use)"
fi

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

# Step 0: Generate identities including rogue-node materials (optional)
if [ "${REUSE_EXISTING_CLUSTER}" != "true" ]; then
  echo "[0/6] Generating node identities (node1–node4 + rogue-node)..."
  INCLUDE_ROGUE_NODE=true python3 docker/scripts/generate_node_identities.py
  echo "  ✅ Identities ready"
else
  echo "[0/6] Skipping identity generation (REUSE_EXISTING_CLUSTER=true)"
fi

# Step 1: Build images (optional)
if [ "${REUSE_EXISTING_CLUSTER}" != "true" ]; then
  echo "[1/6] Building Docker images..."
  docker compose -f "$COMPOSE_FILE" build
  echo "  ✅ Build complete"
else
  echo "[1/6] Skipping Docker build (REUSE_EXISTING_CLUSTER=true)"
fi

# Step 2: Start legitimate 4-node cluster + infra (optional)
if [ "${REUSE_EXISTING_CLUSTER}" != "true" ]; then
  echo "[2/6] Starting 4-node cluster (without rogue-node)..."
  UP_ARGS=""
  if [ "${FORCE_RECREATE}" = "true" ]; then
    UP_ARGS="--force-recreate"
  fi
  docker compose -f "$COMPOSE_FILE" up -d ${UP_ARGS} node1 node2 node3 node4 gateway redis ipfs-node1 ipfs-node2 ipfs-node3 ipfs-node4
else
  echo "[2/6] Reusing existing 4-node cluster (no restart)"
fi

# Step 3: Wait for cluster health
echo "[3/6] Waiting for 4 nodes and IPFS swarm to be healthy..."
MAX_RETRIES=30
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if docker compose -f "$COMPOSE_FILE" ps | grep -q "Up"; then
        HEALTHY=0
        NODES_READY=true
        for node in node1 node2 node3 node4; do
            if docker compose -f "$COMPOSE_FILE" exec -T "$node" \
                python -c "import urllib.request; urllib.request.urlopen('http://localhost:2661/api/ledger/health', timeout=5)" 2>/dev/null; then
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
    docker compose -f "$COMPOSE_FILE" logs --tail=50 || true
    exit 1
fi

# Step 4: Start rogue-node with security-test profile
echo "[4/6] Starting rogue-node (security-test profile)..."
docker compose -f "$COMPOSE_FILE" --profile security-test up -d rogue-node

# Step 5: Wait for rogue-node health
echo "[5/6] Waiting for rogue-node health..."
MAX_RETRIES=30
RETRY_COUNT=0
until docker compose -f "$COMPOSE_FILE" exec -T rogue-node \
    python -c "import urllib.request; urllib.request.urlopen('http://localhost:2661/api/ledger/health', timeout=5)" 2>/dev/null; do
    sleep 3
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "  ❌ rogue-node failed health check"
        docker compose -f "$COMPOSE_FILE" logs --tail=200 rogue-node || true
        exit 1
    fi
done
echo "  ✅ rogue-node healthy"

# Step 6: Run security tests only
echo "[6/6] Running security test suite (tests/stress/security)..."
docker compose -f "$COMPOSE_FILE" run --rm stress-tester \
    bash -c "
        mkdir -p /app/log/report
        export TARGET_NODES='$TARGET'
        export ROGUE_NODE_TARGET='${ROGUE_NODE_TARGET}'
        export TEST_DURATION='$DURATION'
        export REAL_REQUESTS='$REAL_REQUESTS'
        export HRC_IPFS_ENABLED=true
        export HRC_IPFS_HOST=/dns4/ipfs-node1/tcp/5001
        export ROGUE_IMPERSONATE_NODE_ID='${ROGUE_IMPERSONATE_NODE_ID:-}'
        export EXPLORER_TOKEN='${EXPLORER_TOKEN:-default_token}'
        uv run pytest ${SECURITY_PYTEST_TARGET} -v \
            --html=/app/log/report/docker_rogue_security_report.html \
            --self-contained-html
    "

echo ""
echo "========================================"
echo " Security (node5) phase complete!"
echo "========================================"
echo "Security report: log/report/docker_rogue_security_report.html"
