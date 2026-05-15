#!/bin/bash
# HieraChain Kubernetes Setup Script (Optimized)
# Creates Kind cluster and deploys HieraChain with Web2 simulation
# Matches the feature set of setup-docker-compose.sh

set -e

echo "========================================"
echo " HieraChain K8s Setup"
echo "========================================"

# Check prerequisites
for cmd in kind kubectl docker python3; do
    if ! command -v $cmd &> /dev/null; then
        echo "ERROR: $cmd not installed."
        exit 1
    fi
done

# Configuration
CLUSTER_NAME="hiera-cluster"
IMAGE_NAME="hierachain:latest"
NAMESPACE="hierachain"

# Generate a random token for the stealth explorer (parity with docker-compose)
EXPLORER_TOKEN=$(LC_ALL=C tr -dc 'a-z0-9' < /dev/urandom | head -c 8 || echo "default")
EXPLORER_TOKEN="hrc_${EXPLORER_TOKEN}"

# Node list for discovery
HRC_NODES="hierachain-node-0,hierachain-node-1,hierachain-node-2,hierachain-node-3"

# Step 0: Generate Node Identities (Cryptographic Keys)
echo ""
echo "[0/7] Generating fresh node identities..."
python3 docker/scripts/generate_node_identities.py

# Step 1: Build Docker image
echo ""
echo "[1/7] Building Docker image..."
CURRENT_VERSION=$(python3 -c "import sys; sys.path.insert(0, '.'); from hierachain.units.version import __version__; print(__version__)" 2>/dev/null || echo "0.0.1-k8s")
docker build --no-cache -t $IMAGE_NAME --build-arg VERSION=${CURRENT_VERSION} -f docker/Dockerfile .
sleep 2

# Step 2: Create Kind cluster
echo ""
echo "[2/7] Creating Kind cluster (5 Nodes: 1 CP + 4 Workers)..."
if kind get clusters | grep -q "^$CLUSTER_NAME$"; then
    echo "  Cluster already exists. Skipping creation."
else
    kind create cluster --name $CLUSTER_NAME --config docker/kind-config.yaml
fi
sleep 2

# Step 3: Set resource limits for Kind nodes
echo ""
echo "[3/7] Setting resource limits for Kind nodes..."
# Control-plane runs etcd + apiserver + scheduler + controller-manager → needs more headroom
docker update --cpus 2 --memory 2g --memory-swap 3g ${CLUSTER_NAME}-control-plane 2>/dev/null || true
# Worker needs: 0.5 CPU / 500MB for system (kubelet, kube-proxy) + 1 CPU / 1GB for HieraChain pod
for worker in ${CLUSTER_NAME}-worker ${CLUSTER_NAME}-worker2 ${CLUSTER_NAME}-worker3 ${CLUSTER_NAME}-worker4; do
    docker update --cpus 1.5 --memory 1.5g --memory-swap 2.5g $worker 2>/dev/null || true
done

# Step 4: Load image into cluster
echo ""
echo "[4/7] Loading Docker image into Kind cluster..."
kind load docker-image $IMAGE_NAME --name $CLUSTER_NAME

# Step 5: Deploy Resources
echo ""
echo "[5/7] Deploying HieraChain Resources..."
# Ensure namespace exists first
kubectl apply -f docker/k8s/namespace.yaml

# Create Secret for Explorer Token and Node list
kubectl create secret generic hierachain-secrets -n $NAMESPACE \
  --from-literal=EXPLORER_TOKEN=$EXPLORER_TOKEN \
  --from-literal=HRC_NODES=$HRC_NODES \
  --dry-run=client -o yaml | kubectl apply -f -

# Create Secret for Node Identities (mounting keys into the cluster)
kubectl create secret generic hierachain-node-identities -n $NAMESPACE \
  --from-file=node-0-identity=docker/nodes/node1/identity.json \
  --from-file=node-1-identity=docker/nodes/node2/identity.json \
  --from-file=node-2-identity=docker/nodes/node3/identity.json \
  --from-file=node-3-identity=docker/nodes/node4/identity.json \
  --dry-run=client -o yaml | kubectl apply -f -

# Apply all other manifests via Kustomize
kubectl apply -k docker/k8s/

# Force restart web2-node to pick up new secrets/configs
kubectl rollout restart deployment web2-node -n $NAMESPACE
kubectl rollout status deployment web2-node -n $NAMESPACE --timeout=300s

# Step 6: Wait for pods
echo ""
echo "[6/7] Waiting for HieraChain cluster to stabilize..."
kubectl rollout status statefulset/hierachain-node -n $NAMESPACE --timeout=300s
kubectl rollout status deployment/web2-node -n $NAMESPACE --timeout=300s

# Step 7: Check cluster health via Web2 Gateway
echo ""
echo "[7/7] Checking cluster health via Web2 Gateway (localhost:32660)..."
MAX_RETRIES=20
RETRY_COUNT=0
HEALTHY=false

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:32660/web2-status | grep -q "web2_active"; then
        if curl -s http://localhost:32660/api/v1/health | grep -q "healthy"; then
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
    echo "  ⚠️  Health check timed out, but pods are running. You may need to wait longer."
fi

# Summary (Matches setup-docker-compose.sh)
echo ""
echo "========================================"
echo " K8s Deployment complete!"
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
echo "  Health:       http://localhost:32661/api/v1/health"
echo ""
echo "Cluster Infrastructure (Kind):"
echo "  Namespace:    ${NAMESPACE}"
echo "  Nodes:        5 (1 Control Plane + 4 Workers)"
echo ""
echo "Next steps:"
echo "  - Run stress test: bash docker/run-stress-k8s.sh"
echo "  - View pods:       kubectl get pods -n ${NAMESPACE}"
echo "  - View logs:       kubectl logs -l app=hierachain -n ${NAMESPACE} -f"
echo ""
echo "Cleanup:"
echo "  kind delete cluster --name $CLUSTER_NAME"
echo "========================================"
