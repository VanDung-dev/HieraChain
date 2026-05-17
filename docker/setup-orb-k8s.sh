#!/bin/bash
# HieraChain Kubernetes Setup Script (OrbStack)
# Deploys HieraChain to OrbStack's built-in Kubernetes cluster

set -e

echo "========================================"
echo " HieraChain K8s Setup (OrbStack)"
echo "========================================"

# Configuration
IMAGE_NAME="hierachain:latest"
NAMESPACE="hierachain"

# Generate a random token for the stealth explorer
EXPLORER_TOKEN=$(LC_ALL=C tr -dc 'a-z0-9' < /dev/urandom | head -c 8 || echo "default")
EXPLORER_TOKEN="hrc_${EXPLORER_TOKEN}"

HRC_NODES="hierachain-node-0,hierachain-node-1,hierachain-node-2,hierachain-node-3"

# Step 0: Generate Node Identities (Cryptographic Keys)
echo ""
echo "[1/6] Generating fresh node identities..."
python3 docker/scripts/generate_node_identities.py

# Step 1: Build Docker image in OrbStack context
echo ""
echo "[2/6] Building Docker image in OrbStack..."
CURRENT_VERSION=$(python3 -c "import sys; sys.path.insert(0, '.'); from hierachain.units.version import __version__; print(__version__)" 2>/dev/null || echo "0.0.1-k8s")
docker --context=orbstack build --no-cache -t $IMAGE_NAME --build-arg VERSION=${CURRENT_VERSION} -f docker/Dockerfile .
sleep 2

# Step 2: Check OrbStack Kubernetes context
echo ""
echo "[3/6] Checking OrbStack Kubernetes..."
if ! kubectl cluster-info &>/dev/null; then
    echo "  ERROR: kubectl cannot connect to Kubernetes cluster"
    echo "  Make sure OrbStack Kubernetes is running"
    exit 1
fi
echo "  Connected to: $(kubectl cluster-info --request-timeout=5s 2>/dev/null | head -1)"

# Step 3: Image is already in OrbStack docker from build step
echo ""
echo "[4/6] Image ready in OrbStack (built directly in orbstack context)"
sed -i '' 's/imagePullPolicy: Always/imagePullPolicy: IfNotPresent/g' docker/k8s/node-statefulset.yaml 2>/dev/null || true
sed -i '' 's/imagePullPolicy: Always/imagePullPolicy: IfNotPresent/g' docker/k8s/web2-node.yaml 2>/dev/null || true

# Step 5: Deploy Resources
echo ""
echo "[5/6] Deploying HieraChain Resources..."

kubectl apply -f docker/k8s/namespace.yaml

kubectl create secret generic hierachain-secrets -n $NAMESPACE \
    --from-literal=EXPLORER_TOKEN=$EXPLORER_TOKEN \
    --from-literal=HRC_NODES=$HRC_NODES \
    --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic hierachain-node-identities -n $NAMESPACE \
    --from-file=node-0-identity=docker/nodes/node1/identity.json \
    --from-file=node-1-identity=docker/nodes/node2/identity.json \
    --from-file=node-2-identity=docker/nodes/node3/identity.json \
    --from-file=node-3-identity=docker/nodes/node4/identity.json \
    --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -k docker/k8s/

kubectl rollout restart deployment web2-node -n $NAMESPACE
kubectl rollout status deployment web2-node -n $NAMESPACE --timeout=300s

# Step 6: Wait for pods
echo ""
echo "[6/6] Waiting for HieraChain cluster to stabilize..."
kubectl rollout status statefulset/hierachain-node -n $NAMESPACE --timeout=300s
kubectl rollout status deployment/web2-node -n $NAMESPACE --timeout=300s

# Check cluster health via Web2 Gateway
echo ""
echo "Checking cluster health via Web2 Gateway (localhost:32660)..."
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
    echo "  ⚠️  Health check timed out, but pods are running."
fi

# imagePullPolicy already set to IfNotPresent (no need to restore)

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
echo "  Health:       http://localhost:32661/api/v1/health"
echo ""
echo "Cluster Infrastructure (OrbStack Kubernetes):"
echo "  Namespace:    ${NAMESPACE}"
echo "  Context:      $(kubectl config current-context)"
echo ""
echo "Next steps:"
echo "  - Run stress test: bash docker/run-stress-k8s.sh"
echo "  - View pods:       kubectl get pods -n ${NAMESPACE}"
echo "  - View logs:       kubectl logs -l app=hierachain -n ${NAMESPACE} -f"
echo ""
echo "Cleanup:"
echo "  kubectl delete namespace ${NAMESPACE}"
echo "========================================"
