#!/bin/bash
# HieraChain Podman Compose Setup Script
# Creates a 4-node cluster with IPFS private swarm using Podman Compose

set -e

echo "========================================"
echo " HieraChain Podman Compose Setup"
echo "========================================"

# Check prerequisites
if ! command -v podman &> /dev/null; then
    echo "ERROR: podman not installed."
    exit 1
fi

# Configuration
IMAGE_NAME="hierachain:latest"
COMPOSE_FILE="docker/docker-compose.yml"
COMPOSE_PODMAN="docker/docker-compose.podman.yml"
COMPOSE_FILES="-f $COMPOSE_FILE -f $COMPOSE_PODMAN"
IPFS_DIR="docker/ipfs"

# Generate a random token for the stealth explorer
EXPLORER_TOKEN=$(LC_ALL=C tr -dc 'a-z0-9' < /dev/urandom | head -c 8 || echo "default")
export EXPLORER_TOKEN="hrc_${EXPLORER_TOKEN}"

# ---- Generate IPFS private swarm key ----
echo ""
echo "[Pre] Generating IPFS private swarm key..."
mkdir -p "$IPFS_DIR"
SWARM_KEY_HEX=$(openssl rand -hex 32)
{
  echo "/key/swarm/psk/1.0.0/"
  echo "/base16/"
  echo "$SWARM_KEY_HEX"
} > "$IPFS_DIR/swarm.key"
echo "  IPFS swarm.key generated at $IPFS_DIR/swarm.key"

# ---- Generate IPFS encryption key for HieraChain app ----
echo ""
echo "[Pre] Generating IPFS encryption key..."
IPFS_ENCRYPTION_KEY=$(openssl rand -hex 32)
export IPFS_ENCRYPTION_KEY
echo "  IPFS_ENCRYPTION_KEY generated"

# Step 0: Auto-discover nodes from compose file
echo ""
echo "[0/6] Discovering cluster nodes..."
HRC_NODES=$(grep "hostname:" $COMPOSE_FILE | awk '{print $2}' | grep -v -E "gateway|redis|ipfs" | tr '\n' ',' | sed 's/,$//')
export HRC_NODES
echo "  Found nodes: ${HRC_NODES}"

# Step 1: Generate Node Identities (including rogue-node for WireGuard configs)
echo ""
echo "[1/6] Generating fresh node identities (cryptographic keys + WireGuard)..."
INCLUDE_ROGUE_NODE=true python3 docker/scripts/generate_node_identities.py

# Step 2: Build Podman image
echo ""
echo "[2/6] Building Podman image..."
CURRENT_VERSION=$(python3 -c "import sys; sys.path.insert(0, '.'); from hierachain.config.version import __version__; print(__version__)")
echo "  Target Version: ${CURRENT_VERSION}"

podman build -t $IMAGE_NAME \
    --build-arg VERSION=${CURRENT_VERSION} \
    -f docker/Dockerfile .
sleep 5

# Step 3: Stop existing cluster
echo ""
echo "[3/6] Stopping existing cluster..."
podman compose $COMPOSE_FILES down --remove-orphans -v
sleep 2

# Step 4: Start 4 HieraChain nodes + IPFS private swarm
echo ""
echo "[4/6] Starting HieraChain cluster with IPFS swarm..."
podman compose $COMPOSE_FILES up -d
sleep 5

# Step 5: Connect IPFS peers into a private swarm
echo ""
echo "[5/6] Connecting IPFS private swarm..."
MAX_RETRIES=15
for ipfs_node in ipfs-node1 ipfs-node2 ipfs-node3 ipfs-node4; do
    echo "  Waiting for $ipfs_node..."
    for i in $(seq 1 $MAX_RETRIES); do
        if podman exec "hierachain-$ipfs_node" ipfs id 2>/dev/null >/dev/null; then
            break
        fi
        sleep 2
    done
done

PEER_IDS=""
for ipfs_node in ipfs-node1 ipfs-node2 ipfs-node3 ipfs-node4; do
    PEER_ID=$(podman exec "hierachain-$ipfs_node" ipfs config Identity.PeerID 2>/dev/null || echo "")
    if [ -n "$PEER_ID" ]; then
        PEER_IDS="$PEER_IDS $ipfs_node:$PEER_ID"
    fi
done

echo "  Discovered peers:${PEER_IDS}"

for src_node in ipfs-node1 ipfs-node2 ipfs-node3 ipfs-node4; do
    for dst_node in ipfs-node1 ipfs-node2 ipfs-node3 ipfs-node4; do
        if [ "$src_node" = "$dst_node" ]; then
            continue
        fi
        DST_PEER=$(echo "$PEER_IDS" | tr ' ' '\n' | grep "^$dst_node:" | cut -d: -f2)
        if [ -n "$DST_PEER" ]; then
            DST_WG_IP=$(podman inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$v.IPAddress}}{{"\n"}}{{end}}' "hierachain-$dst_node" 2>/dev/null | head -1 || echo '')
            if [ -n "$DST_WG_IP" ]; then
                echo "  Connecting $src_node → $dst_node ($DST_WG_IP)..."
                podman exec "hierachain-$src_node" \
                    ipfs swarm connect "/ip4/$DST_WG_IP/tcp/4001/p2p/$DST_PEER" \
                    2>/dev/null || true
            fi
        fi
    done
done

# Step 6: Check cluster health via Gateway
echo ""
echo "[6/6] Checking cluster health via Gateway..."
MAX_RETRIES=20
RETRY_COUNT=0
HEALTHY=false
GATEWAY_NOTIFIED=false

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:2660/gateway-health | grep -q "gateway_up"; then
        if [ "$GATEWAY_NOTIFIED" = false ]; then
            echo "  ✅ Gateway is UP"
            GATEWAY_NOTIFIED=true
        fi

        if curl -s http://localhost:2660/api/ledger/health | grep -q "healthy"; then
            echo "  ✅ HieraChain Cluster is READY"
            HEALTHY=true
            break
        fi
    fi

    if [ "$GATEWAY_NOTIFIED" = false ]; then
        echo "  ... Waiting for Gateway (attempt $((RETRY_COUNT+1))/$MAX_RETRIES)"
    else
        echo "  ... Waiting for HieraChain Nodes ($((RETRY_COUNT+1))/$MAX_RETRIES)"
    fi

    sleep 3
    RETRY_COUNT=$((RETRY_COUNT+1))
done

if [ "$HEALTHY" = false ]; then
    echo "  ❌ Cluster failed to start properly. Check logs with: podman compose $COMPOSE_FILES logs"
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
echo "  Get token: podman exec hierachain-gateway env | grep EXPLORER_TOKEN"
echo ""
echo "HieraChain Nodes (Multi-Region WireGuard Mesh):"
echo "  US region:   node1  (10.200.1.1  | 172.28.1.10)"
echo "  EU region:   node2  (10.200.2.1  | 172.28.2.10)"
echo "  Asia region: node3  (10.200.3.1  | 172.28.3.10)"
echo "  Asia region: node4  (10.200.4.1  | 172.28.3.11)"
echo "  P2P traffic travels through WireGuard overlay (encrypted + WAN latency)"
echo ""
echo "IPFS Private Swarm (Cross-Region Mesh):"
echo "  US:   ipfs-node1  → 172.28.1.61  (wgmesh: 172.29.0.61)"
echo "  EU:   ipfs-node2  → 172.28.2.61  (wgmesh: 172.29.0.62)"
echo "  Asia: ipfs-node3  → 172.28.3.61  (wgmesh: 172.29.0.63)"
echo "  Asia: ipfs-node4  → 172.28.3.62  (wgmesh: 172.29.0.64)"
echo ""
echo "Cross-Region Latency Simulation (tc on WireGuard interfaces):"
echo "  US↔EU:    200-300ms"
echo "  US↔Asia:  400-500ms"
echo "  EU↔Asia:  300-400ms"
echo "  Asia↔Asia: 0-100ms"
echo "  Encryption Key: ${IPFS_ENCRYPTION_KEY:0:16}... (saved in swarm.key)"
echo ""
echo "Next steps:"
echo "  - Run stress test: bash docker/run-stress-podman.sh"
echo "  - View cluster logs: podman compose $COMPOSE_FILES logs -f"
echo ""
echo "Cleanup:"
echo "  podman compose $COMPOSE_FILES down -v"
echo "========================================"
