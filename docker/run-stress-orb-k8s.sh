#!/bin/bash
# HieraChain Stress Test Runner - OrbStack K8s
# Runs stress tests on a Kubernetes cluster with IPFS private swarm
#
# Usage:
#   bash docker/run-stress-orb-k8s.sh [duration_seconds]
#
# Prerequisites:
#   - K8s cluster running with HieraChain deployed (run setup-orb-k8s.sh first)
#   - OrbStack Docker context available

set -e

# Configuration
DURATION=${1:-60}
TARGET=${TARGET:-"host.docker.internal:32661"}
NAMESPACE="hierachain"
COMPOSE_FILE="docker/docker-compose.k8s-stress.yml"
IPFS_DIR="docker/ipfs"

# Reuse clusters that are already set up by default: no image builds, no ConfigMap/Secret updates, no rollouts
# Set REUSE_EXISTING_CLUSTER=false to do full build + update + rollout.
REUSE_EXISTING_CLUSTER=${REUSE_EXISTING_CLUSTER:-true}

echo "========================================"
echo " HieraChain OrbStack K8s Stress Test"
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
else
    echo "[Pre] Using existing swarm.key"
fi

# Export IPFS encryption key if not already set
if [ -z "${IPFS_ENCRYPTION_KEY:-}" ]; then
    export IPFS_ENCRYPTION_KEY=$(openssl rand -hex 32)
    echo "[Pre] IPFS_ENCRYPTION_KEY generated"
else
    echo "[Pre] Using existing IPFS_ENCRYPTION_KEY"
fi

# Step 1: Rebuild Docker image with latest code
echo ""
if [ "${REUSE_EXISTING_CLUSTER}" != "true" ]; then
  echo "[1/4] Building Docker image..."
  docker build -t hierachain:latest -f docker/Dockerfile .
  echo "  ✅ Build complete"
else
  echo "[1/4] Skip build (REUSE_EXISTING_CLUSTER=true)"
fi

# Step 2: Restart/Update K8s cluster resources
echo ""
if [ "${REUSE_EXISTING_CLUSTER}" != "true" ]; then
  echo "[2/4] Restarting K8s cluster..."

  # Update IPFS configmap with latest swarm.key
  echo "  Updating IPFS config..."
  # Patch init.sh with K8s-specific additions (swarm.key copy + permission fix)
  # using awk instead of sed for macOS/Linux compatibility
  INIT_SH_CONTENT=$(awk '
/^# 1. Ensure swarm.key is in place for private network/ {
      print "# 0. Copy swarm.key from ConfigMap mount if present (K8s deployment)"
      print "if [ -f /container-init.d/swarm.key ] && [ ! -f \042$SWARM_KEY_FILE\042 ]; then"
      print "    echo \042[IPFS Init] Copying swarm.key from ConfigMap mount...\042"
      print "    cp /container-init.d/swarm.key \042$SWARM_KEY_FILE\042"
      print "fi"
      print
  }
  /echo.*Ready/ {
      print "# 5. Fix permissions: init runs as root but daemon runs as ipfs (UID 1000)"
      print "chown -R 1000:1000 /data/ipfs 2>/dev/null || true"
      print
  }
  { print }
  ' docker/ipfs/init.sh)
  TEMP_INIT_SH=$(mktemp)
  echo "$INIT_SH_CONTENT" > "$TEMP_INIT_SH"

  kubectl create configmap ipfs-config -n $NAMESPACE \
      --from-file=init.sh="$TEMP_INIT_SH" \
      --from-file=swarm.key=docker/ipfs/swarm.key \
      --dry-run=client -o yaml | kubectl apply -f -
  rm -f "$TEMP_INIT_SH"
  echo "  ✅ IPFS config updated"

  # Update IPFS encryption key in secrets (preserve EXPLORER_TOKEN and HRC_NODES)
  # Read existing EXPLORER_TOKEN from the secret, or generate a new one
  EXISTING_TOKEN=$(kubectl get secret hierachain-secrets -n $NAMESPACE -o jsonpath='{.data.EXPLORER_TOKEN}' 2>/dev/null | base64 -d 2>/dev/null || echo "")
  if [ -z "$EXISTING_TOKEN" ]; then
      EXISTING_TOKEN=$(LC_ALL=C tr -dc 'a-z0-9' < /dev/urandom | head -c 16)
  fi
  kubectl create secret generic hierachain-secrets -n $NAMESPACE \
      --from-literal=EXPLORER_TOKEN=$EXISTING_TOKEN \
      --from-literal=HRC_NODES="node1,node2,node3,node4" \
      --from-literal=IPFS_ENCRYPTION_KEY=$IPFS_ENCRYPTION_KEY \
      --dry-run=client -o yaml | kubectl apply -f -
  echo "  ✅ IPFS encryption key updated"

  # Restart IPFS and HieraChain nodes
  echo "  Restarting IPFS statefulset..."
  kubectl rollout restart statefulset/ipfs -n $NAMESPACE

  echo "  Restarting HieraChain nodes..."
  kubectl rollout restart statefulset/hierachain-node -n $NAMESPACE
else
  echo "[2/4] Skip update/rollout K8s (REUSE_EXISTING_CLUSTER=true)"
fi

# Step 3: Wait for cluster to be healthy
echo ""
echo "[3/4] Waiting for cluster to be healthy..."

echo "  Waiting for IPFS..."
kubectl rollout status statefulset/ipfs -n $NAMESPACE --timeout=300s
echo "  ✅ IPFS statefulset ready"

echo "  Waiting for HieraChain nodes..."
kubectl rollout status statefulset/hierachain-node -n $NAMESPACE --timeout=300s
echo "  ✅ HieraChain nodes ready"

# Connect IPFS peers into a private swarm
echo "  Reconnecting IPFS swarm..."
MAX_RETRIES=15

# Wait for all IPFS pods to respond
for i in $(seq 0 3); do
    for j in $(seq 1 $MAX_RETRIES); do
        if kubectl exec -n $NAMESPACE "ipfs-$i" -- ipfs id 2>/dev/null >/dev/null; then
            break
        fi
        sleep 2
    done
done

# Extract peer IDs and connect each node to all others
PEER_IDS=""
for i in $(seq 0 3); do
    PEER_ID=$(kubectl exec -n $NAMESPACE "ipfs-$i" -- ipfs config Identity.PeerID 2>/dev/null || echo "")
    if [ -n "$PEER_ID" ]; then
        PEER_IDS="$PEER_IDS ipfs-$i:$PEER_ID"
    fi
done

for src_idx in $(seq 0 3); do
    for dst_idx in $(seq 0 3); do
        if [ "$src_idx" = "$dst_idx" ]; then
            continue
        fi
        DST_PEER=$(echo "$PEER_IDS" | tr ' ' '\n' | grep "^ipfs-$dst_idx:" | cut -d: -f2)
        DST_IP=$(kubectl get pod "ipfs-$dst_idx" -n $NAMESPACE -o jsonpath='{.status.podIP}' 2>/dev/null || echo '')
        if [ -n "$DST_PEER" ] && [ -n "$DST_IP" ]; then
            kubectl exec -n $NAMESPACE "ipfs-$src_idx" -- \
                ipfs swarm connect "/ip4/$DST_IP/tcp/4001/p2p/$DST_PEER" \
                2>/dev/null || true
        fi
    done
done
echo "  ✅ IPFS swarm connected"

# Wait for all HieraChain nodes to report healthy
echo "  Waiting for all HieraChain nodes to report healthy..."
MAX_RETRIES=30
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    HEALTHY_COUNT=0
    for i in $(seq 0 3); do
        STATUS=$(kubectl exec -n $NAMESPACE "hierachain-node-$i" -- \
            python -c "
import urllib.request
try:
    resp = urllib.request.urlopen('http://localhost:2661/api/ledger/health', timeout=5)
    print(resp.read().decode())
except Exception as e:
    print('error: ' + str(e))
" 2>/dev/null || echo "error")
        if echo "$STATUS" | grep -q "healthy"; then
            HEALTHY_COUNT=$((HEALTHY_COUNT + 1))
        fi
    done
    if [ "$HEALTHY_COUNT" -ge 4 ]; then
        echo "  ✅ All 4 HieraChain nodes healthy"
        break
    fi
    echo "  ... ${HEALTHY_COUNT}/4 nodes healthy ($((RETRY_COUNT+1))/$MAX_RETRIES)"
    sleep 3
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
    echo "  ❌ Cluster failed to become healthy"
    echo "  Current pods:"
    kubectl get pods -n $NAMESPACE
    kubectl logs -n $NAMESPACE -l app=hierachain --tail=20 || true
    if [ "${REUSE_EXISTING_CLUSTER}" = "true" ]; then
        echo "  Hint: The cluster may not be ready. Run setup first or set REUSE_EXISTING_CLUSTER=false to let the script build & roll out automatically."
    fi
    exit 1
fi

# Step 4: Run stress test
echo ""
echo "[4/4] Starting stress test + IPFS integration..."
docker --context=orbstack compose -f "$COMPOSE_FILE" run --rm --build stress-tester \
    bash -c "
        mkdir -p /app/log/report
        export TARGET_NODES='$TARGET'
        export TEST_DURATION='$DURATION'
        export HRC_IPFS_ENABLED=true
        export HRC_IPFS_ENCRYPTION_KEY='$IPFS_ENCRYPTION_KEY'
        export K8S_NAMESPACE='$NAMESPACE'
        uv run pytest tests/stress/ -v \
            --html=/app/log/report/orb_k8s_stress_report.html \
            --self-contained-html \
            --junitxml=/app/log/report/docker_stress_report.xml
    "

echo ""
echo "========================================"
echo " Stress test + IPFS integration complete!"
echo "========================================"
echo "Report: log/report/orb_k8s_stress_report.html"
