#!/bin/bash
# IPFS Kubernetes Deployment Script for OrbStack

# Step 0: Check Kubernetes context
NAMESPACE="hierachain"
IMAGE_NAME="hierachain:latest"
IPFS_DIR="/data/ipfs"
EXPLORER_TOKEN=$(LC_ALL=C tr -dc 'a-z0-9' < /dev/urandom | head -c 16)
IPFS_ENCRYPTION_KEY=$(openssl rand -hex 32)
IPFS_SWARM_KEY_FILE="docker/ipfs/swarm.key"

# Ensure IPFS swarm.key exists (private network — never commit real key to git)
if [ ! -f "$IPFS_SWARM_KEY_FILE" ]; then
  echo "[Pre] Generating IPFS swarm.key..."
  mkdir -p "$(dirname "$IPFS_SWARM_KEY_FILE")"
  SWARM_KEY_HEX=$(openssl rand -hex 32)
  {
    echo "/key/swarm/psk/1.0.0/"
    echo "/base16/"
    echo "$SWARM_KEY_HEX"
  } > "$IPFS_SWARM_KEY_FILE"
  echo "  ✅ swarm.key generated (not committed to git)"
else
  echo "[Pre] Using existing swarm.key"
fi

# Step 1: Generate Node Identities (Cryptographic Keys)
echo ""
echo "[1/6] Generating fresh node identities..."
uv run python docker/scripts/generate_node_identities.py

# Step 2: Build Docker image in OrbStack context
echo ""
echo "[2/6] Building Docker image in OrbStack context..."
CURRENT_VERSION=$(uv run python -c "import sys; sys.path.insert(0, '.'); from hierachain.config.version import __version__; print(__version__)" 2>/dev/null || echo "0.0.1-k8s")

docker build -t $IMAGE_NAME \
    --build-arg VERSION=${CURRENT_VERSION} \
    -f docker/Dockerfile .
echo "  ✅ Build complete"

# Step 3: Check OrbStack Kubernetes
echo ""
echo "[3/6] Checking OrbStack Kubernetes..."
if ! kubectl cluster-info &>/dev/null; then
    echo "  ❌ ERROR: kubectl cannot connect to Kubernetes cluster"
    echo "  Make sure OrbStack Kubernetes is running"
    exit 1
fi
echo "  Connected to: $(kubectl cluster-info | head -1)"

# Step 4: Deploy Resources (namespace first, then configs, then kustomize)
echo ""
echo "[4/6] Deploying HieraChain Resources..."

# Create namespace
kubectl create namespace $NAMESPACE || true

# Create K8s secrets (must exist before pods start)
echo "  Creating K8s secrets..."

# Node identities secret (init container reads these)
kubectl create secret generic hierachain-node-identities \
  --from-file=node-0-identity=docker/nodes/node1/identity.json \
  --from-file=node-1-identity=docker/nodes/node2/identity.json \
  --from-file=node-2-identity=docker/nodes/node3/identity.json \
  --from-file=node-3-identity=docker/nodes/node4/identity.json \
  -n $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

# Web2 gateway + IPFS encryption secrets
kubectl create secret generic hierachain-secrets \
  --from-literal=EXPLORER_TOKEN=$EXPLORER_TOKEN \
  --from-literal=HRC_NODES="node1,node2,node3,node4" \
  --from-literal=IPFS_ENCRYPTION_KEY=$IPFS_ENCRYPTION_KEY \
  -n $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

# Apply all resources via kustomize (creates namespace, configs, statefulsets, etc.)
kubectl apply -k docker/k8s/

# Inject IPFS swarm.key into ConfigMap (not stored in git to avoid leaking secrets)
echo "  Injecting IPFS swarm.key into ConfigMap..."
SWARM_KEY_FILE="docker/ipfs/swarm.key"
if [ -f "$SWARM_KEY_FILE" ]; then
  SWARM_KEY_CONTENT=$(uv run python -c "import sys,json; print(json.dumps(sys.stdin.read()))" < "$SWARM_KEY_FILE")
  kubectl patch configmap ipfs-config -n $NAMESPACE \
    --patch "{\"data\":{\"swarm.key\":$SWARM_KEY_CONTENT}}" || {
    echo "  ⚠️  ConfigMap patch failed — trying full replace..."
    kubectl create configmap ipfs-config -n $NAMESPACE \
      --from-file=swarm.key="$SWARM_KEY_FILE" \
      --dry-run=client -o yaml | kubectl apply -f -
  }
  echo "  ✅ IPFS swarm.key injected"
else
  echo "  ⚠️  $SWARM_KEY_FILE not found — IPFS will run in public mode"
  echo "  To generate: printf '%s\\n' '/key/swarm/psk/1.0.0/' '/base16/' \"\$(openssl rand -hex 32)\" > $SWARM_KEY_FILE"
fi

# Step 5: Wait for pods
echo ""
echo "[5/6] Waiting for HieraChain cluster to stabilize..."
kubectl rollout status statefulset/hierachain-node -n $NAMESPACE --timeout=300s
kubectl rollout status statefulset/ipfs -n $NAMESPACE --timeout=300s
kubectl rollout status deployment/web2-node -n $NAMESPACE --timeout=300s

# Step 6: Connect IPFS peers into a private swarm
echo ""
echo "[6/6] Connecting IPFS private swarm..."
MAX_RETRIES=15
for i in $(seq 0 3); do
    echo "  Waiting for ipfs-$i..."
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
echo "  Discovered peers:${PEER_IDS}"

# Connect each IPFS node to all others
for src_idx in $(seq 0 3); do
    for dst_idx in $(seq 0 3); do
        if [ "$src_idx" = "$dst_idx" ]; then
            continue
        fi
        DST_PEER=$(echo "$PEER_IDS" | tr ' ' '\n' | grep "^ipfs-$dst_idx:" | cut -d: -f2)
        SRC_POD="ipfs-$src_idx"
        DST_POD="ipfs-$dst_idx"
        DST_IP=$(kubectl get pod "$DST_POD" -n $NAMESPACE -o jsonpath='{.status.podIP}' 2>/dev/null || echo '0.0.0.0')
        if [ -n "$DST_PEER" ] && [ "$DST_IP" != "0.0.0.0" ]; then
            echo "  Connecting ipfs-$src_idx → ipfs-$dst_idx ($DST_PEER)..."
            kubectl exec -n $NAMESPACE "$SRC_POD" -- \
                ipfs swarm connect "/ip4/$DST_IP/tcp/4001/p2p/$DST_PEER" \
                2>/dev/null || true
        fi
    done
done

# Check cluster health via Web2 Gateway
echo ""
echo "Checking cluster health via Web2 Gateway (localhost:32660)..."
MAX_RETRIES=20
RETRY_COUNT=0
HEALTHY=false

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:32660/web2-status | grep -q "web2_active"; then
        if curl -s http://localhost:32660/api/ledger/health | grep -q "healthy"; then
            echo "  ✅ HieraChain Cluster is READY via Web2 Gateway"
            HEALTHY=true
            break
        fi
    fi
    echo "  ... Waiting for cluster to respond ($((RETRY_COUNT+1))/$MAX_RETRIES)"
    sleep 3
    RETRY_COUNT=$((RETRY_COUNT+1))
done

if [ "$HEALTHY" = false ]; then
    echo "  ⚠️  Health check timed out, but pods are running."
fi

# Summary
echo ""
echo "========================================"
echo " K8s Deployment complete! (OrbStack)"
echo "========================================"
echo ""
echo "Enterprise API Gateway (Web2 simulation):"
echo "  Primary Port: 32660 (Mapped from K8s NodePort)"
echo "  Health:       http://localhost:32660/web2-status"
echo ""
echo "Stealth Explorer (Secure Access):"
echo "  Token:    ${EXPLORER_TOKEN}"
echo "  Status:   http://localhost:32660/${EXPLORER_TOKEN}/status"
echo "  Explorer: http://localhost:32660/${EXPLORER_TOKEN}/explorer"
echo ""
echo "HieraChain API (Direct Cluster Access):"
echo "  Primary Port: 32661"
echo "  Health:       http://localhost:32661/api/ledger/health"
echo ""
echo "IPFS Private Swarm:"
echo "  ipfs-0 → $(kubectl get pod ipfs-0 -n $NAMESPACE -o jsonpath='{.status.podIP}' 2>/dev/null || echo 'N/A')"
echo "  ipfs-1 → $(kubectl get pod ipfs-1 -n $NAMESPACE -o jsonpath='{.status.podIP}' 2>/dev/null || echo 'N/A')"
echo "  ipfs-2 → $(kubectl get pod ipfs-2 -n $NAMESPACE -o jsonpath='{.status.podIP}' 2>/dev/null || echo 'N/A')"
echo "  ipfs-3 → $(kubectl get pod ipfs-3 -n $NAMESPACE -o jsonpath='{.status.podIP}' 2>/dev/null || echo 'N/A')"
echo "  Encryption Key: ${IPFS_ENCRYPTION_KEY:0:16}... (stored in hierachain-secrets)"
echo ""
echo "Cluster Infrastructure (OrbStack Kubernetes):"
echo "  Namespace:    ${NAMESPACE}"
echo "  Context:      $(kubectl config current-context)"
echo ""
echo "Next steps:"
echo "  - Run stress test: bash docker/run-stress-orb-k8s.sh"
echo "  - View pods:       kubectl get pods -n ${NAMESPACE}"
echo "  - View logs:       kubectl logs -l app=hierachain -n ${NAMESPACE} -f"
echo ""
echo "Cleanup:"
echo "  kubectl delete namespace ${NAMESPACE}"
echo "========================================"