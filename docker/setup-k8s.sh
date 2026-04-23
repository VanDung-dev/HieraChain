#!/bin/bash
# HieraChain Kubernetes Setup Script
# Creates Kind cluster and deploys StatefulSet for testing

set -e

echo "========================================"
echo " HieraChain K8s Setup"
echo "========================================"

# Check prerequisites
if ! command -v kind &> /dev/null; then
    echo "ERROR: kind not installed. Install from https://kind.sigs.k8s.io/"
    exit 1
fi

if ! command -v kubectl &> /dev/null; then
    echo "ERROR: kubectl not installed."
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo "ERROR: docker not installed."
    exit 1
fi

# Configuration
CLUSTER_NAME="hiera-cluster"
IMAGE_NAME="hierachain:latest"

# Step 1: Build Docker image
echo ""
echo "[1/6] Building Docker image..."
docker build --no-cache -t $IMAGE_NAME -f docker/Dockerfile .
sleep 5

# Step 2: Create Kind cluster
echo ""
echo "[2/6] Creating Kind cluster..."
kind create cluster --name $CLUSTER_NAME --config docker/kind-config.yaml
sleep 5

# Step 3: Set resource limits for Kind nodes (optional)
echo ""
echo "[3/6] Setting resource limits for Kind nodes..."
docker update --cpus 1 --memory 1g --memory-swap 1g ${CLUSTER_NAME}-control-plane 2>/dev/null || true
for worker in ${CLUSTER_NAME}-worker ${CLUSTER_NAME}-worker2 ${CLUSTER_NAME}-worker3; do
    docker update --cpus 1 --memory 1g --memory-swap 1g $worker 2>/dev/null || true
done
sleep 5

# Step 4: Load image into cluster
echo ""
echo "[4/6] Loading Docker image into Kind cluster..."
kind load docker-image $IMAGE_NAME --name $CLUSTER_NAME
sleep 5

# Step 5: Deploy StatefulSet
echo ""
echo "[5/6] Deploying HieraChain StatefulSet..."
kubectl apply -k docker/k8s/
sleep 5

# Step 6: Wait for pods
echo ""
echo "[6/6] Waiting for pods to become ready..."
# Use rollout status which is more robust for StatefulSets than waiting for individual pods
kubectl rollout status statefulset/hierachain-node -n hierachain --timeout=300s

# Summary
echo ""
echo "========================================"
echo " Deployment complete!"
echo "========================================"
echo ""
echo "StatefulSet:"
kubectl get statefulset -n hierachain hierachain-node
echo ""
echo "Pods:"
kubectl get pods -n hierachain -l app=hierachain -o wide
echo ""
echo "Services:"
kubectl get services -n hierachain
echo ""
echo "PVCs (auto-provisioned by StatefulSet):"
kubectl get pvc -n hierachain
echo ""
echo "Next steps:"
echo "  - Access API: kubectl port-forward service/hierachain-api 2661:2661 -n hierachain"
echo "  - Test (mock): REAL_REQUESTS=false pytest tests/stress/test_hierarchy_isolation.py -v"
echo "  - Test (real): REAL_REQUESTS=true pytest tests/stress/test_hierarchy_isolation.py -v"
echo ""
echo "Cleanup:"
echo "  kubectl delete -k docker/k8s/"
echo "  kind delete cluster --name $CLUSTER_NAME"
