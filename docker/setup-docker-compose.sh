#!/bin/bash
# HieraChain Docker Compose Setup Script
# Creates a 4-node cluster using Docker Compose for stress testing

set -e

echo "========================================"
echo " HieraChain Docker Compose Setup"
echo "========================================"

# Check prerequisites
if ! command -v docker &> /dev/null; then
    echo "ERROR: docker not installed."
    exit 1
fi

# Configuration
IMAGE_NAME="hierachain:latest"
COMPOSE_FILE="docker/docker-compose.test.yml"
# Generate a random token for the stealth explorer
EXPLORER_TOKEN=$(LC_ALL=C tr -dc 'a-z0-9' < /dev/urandom | head -c 8 || echo "default")
export EXPLORER_TOKEN="hrc_${EXPLORER_TOKEN}"

# Step 1: Generate Node Identities
echo ""
echo "[1/5] Generating fresh node identities (cryptographic keys)..."
python3 scripts/generate_node_identities.py

# Step 2: Build Docker image
echo ""
echo "[2/5] Building Docker image..."
docker build --no-cache -t $IMAGE_NAME -f docker/Dockerfile .
sleep 5

# Step 3: Stop existing cluster
echo ""
echo "[3/5] Stopping existing cluster..."
docker compose -f $COMPOSE_FILE down --remove-orphans -v
sleep 2

# Step 4: Start 4 HieraChain nodes
echo ""
echo "[4/5] Starting 4 HieraChain nodes..."
docker compose -f $COMPOSE_FILE up -d
sleep 5

# Step 5: Check cluster health via Gateway
echo ""
echo "[5/5] Checking cluster health via Gateway..."
MAX_RETRIES=15
RETRY_COUNT=0
HEALTHY=false

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    # Check gateway health and backend connectivity
    if curl -s http://localhost:2660/gateway-health | grep -q "gateway_up"; then
        echo "  ✅ Gateway is UP"
        # Check if we can reach HieraChain through the gateway
        if curl -s http://localhost:2660/api/v1/health | grep -q "healthy"; then
            echo "  ✅ HieraChain Cluster is READY"
            HEALTHY=true
            break
        fi
    fi
    echo "  ... Waiting for cluster to be ready (attempt $((RETRY_COUNT+1))/$MAX_RETRIES)"
    sleep 3
    RETRY_COUNT=$((RETRY_COUNT+1))
done

if [ "$HEALTHY" = false ]; then
    echo "  ❌ Cluster failed to start properly. Check logs with: docker compose -f $COMPOSE_FILE logs"
fi

# Summary
echo ""
echo "========================================"
echo " Deployment complete!"
echo "========================================"
echo ""
echo ""
echo "Enterprise API Gateway (Web2 simulation):"
echo "  Primary Port: 2660 (Accessible from LAN 0.0.0.0)"
echo ""
echo "Stealth Explorer (Secure Access):"
echo "  Token:    ${EXPLORER_TOKEN}"
echo "  Status:   http://localhost:2660/${EXPLORER_TOKEN}/status"
echo "  Explorer: http://localhost:2660/${EXPLORER_TOKEN}/explorer"
echo ""
echo "Developer Helper:"
echo "  Get token: docker exec hierachain-gateway env | grep EXPLORER_TOKEN"
echo ""
echo "HieraChain Nodes (Isolated Internal Network):"
echo "  Subnet: 172.28.0.0/24 (node1-node4)"
echo "  (No direct external access for security)"
echo ""
echo "Next steps:"
echo "  - Run stress test: bash docker/run-stress-docker-compose.sh"
echo "  - View cluster logs: docker compose -f $COMPOSE_FILE logs -f"
echo ""
echo "Cleanup:"
echo "  docker compose -f $COMPOSE_FILE down -v"
echo "========================================"
