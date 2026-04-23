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

# Step 1: Build Docker image
echo ""
echo "[1/4] Building Docker image..."
docker build --no-cache -t $IMAGE_NAME -f docker/Dockerfile .
sleep 5

# Step 2: Stop existing cluster
echo ""
echo "[2/4] Stopping existing cluster..."
docker compose -f $COMPOSE_FILE down --remove-orphans -v
sleep 2

# Step 3: Start 4 HieraChain nodes
echo ""
echo "[3/4] Starting 4 HieraChain nodes..."
docker compose -f $COMPOSE_FILE up -d
sleep 5

# Step 4: Check node health
echo ""
echo "[4/4] Checking node health..."
for port in 2661 2662 2663 2664; do
    if curl -s "http://localhost:${port}/api/v1/health" > /dev/null 2>&1; then
        echo "  ✅ Node on port $port is healthy"
    else
        echo "  ❌ Node on port $port is NOT ready"
    fi
done

# Summary
echo ""
echo "========================================"
echo " Deployment complete!"
echo "========================================"
echo ""
echo "Nodes:"
echo "  node1: http://localhost:2661"
echo "  node2: http://localhost:2662"
echo "  node3: http://localhost:2663"
echo "  node4: http://localhost:2664"
echo ""
echo "Next steps:"
echo "  - Run stress test: docker/run-stress-docker-compose.sh"
echo "  - View logs: docker compose -f $COMPOSE_FILE logs -f"
echo ""
echo "Cleanup:"
echo "  docker compose -f $COMPOSE_FILE down -v"
