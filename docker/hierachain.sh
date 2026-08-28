#!/bin/bash
# HieraChain unified deployment tool
# Usage: ./docker/hierachain.sh <command> <environment> [options]
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

if [ "$(id -u)" -eq 0 ]; then
  echo "ERROR: Do NOT run hierachain.sh with sudo or as root."
  echo "Run as regular user (e.g. bash docker/hierachain.sh ...)."
  exit 1
fi

usage() {
  cat <<EOF
Usage: hierachain.sh <command> <environment> [options]

Commands:
  setup                 Deploy full cluster from scratch
  stress                Run stress tests (requires running cluster)
  down                  Stop and clean up cluster

Environments:
  docker                Docker Compose (multi-region + WireGuard)
  k8s                   OrbStack Kubernetes

Options:
  --duration, -d N      Test duration in seconds (default: 60)
  --reuse, -r           Skip build and deploy (use existing cluster)
  --force, -f           Force recreate volumes
  --help, -h            Show this help

Examples:
  bash docker/hierachain.sh setup docker
  bash docker/hierachain.sh stress docker --reuse --duration 120
  bash docker/hierachain.sh down k8s
EOF
  exit 1
}

# === Parse args ===
COMMAND=${1:-}; ENV=${2:-}; shift 2 2>/dev/null || usage
DURATION=60; REUSE=false; FORCE=false

while [ $# -gt 0 ]; do
  case "$1" in
    --duration|-d) DURATION=$2; shift 2 ;;
    --reuse|-r)    REUSE=true; shift ;;
    --force|-f)    FORCE=true; shift ;;
    --help|-h)     usage ;;
    *)             echo "Unknown option: $1"; usage ;;
  esac
done

init_env "$ENV"
check_prereqs
ensure_product_env

echo "========================================"
echo " HieraChain ${COMMAND} (${ENV})"
echo "========================================"

# === Commands ===
case "$COMMAND" in
  setup)
    generate_keys
    generate_identities
    discover_nodes
    build_image
    down_cluster
    echo ""; echo "[4/6] Starting cluster..."
    if $K8S; then
      kubectl create namespace "$NAMESPACE" 2>/dev/null || true
      kubectl create secret generic hierachain-node-identities \
        --from-file=node-0-identity=docker/nodes/node1/identity.json \
        --from-file=node-1-identity=docker/nodes/node2/identity.json \
        --from-file=node-2-identity=docker/nodes/node3/identity.json \
        --from-file=node-3-identity=docker/nodes/node4/identity.json \
        -n "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
      kubectl create secret generic hierachain-secrets \
        --from-literal=EXPLORER_TOKEN="$EXPLORER_TOKEN" \
        --from-literal=HRC_NODES="$HRC_NODES" \
        --from-literal=IPFS_ENCRYPTION_KEY="$IPFS_ENCRYPTION_KEY" \
        -n "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
      kubectl apply -k docker/k8s/
      SWARM_KEY_FILE="docker/ipfs/swarm.key"
      if [ -f "$SWARM_KEY_FILE" ]; then
        SWARM_KEY_CONTENT=$(uv run python -c "import sys,json; print(json.dumps(sys.stdin.read()))" < "$SWARM_KEY_FILE")
        kubectl patch configmap ipfs-config -n "$NAMESPACE" \
          --patch "{\"data\":{\"swarm.key\":$SWARM_KEY_CONTENT}}" 2>/dev/null || \
          kubectl create configmap ipfs-config -n "$NAMESPACE" \
            --from-file=swarm.key="$SWARM_KEY_FILE" \
            --dry-run=client -o yaml | kubectl apply -f -
      fi
      kubectl rollout status statefulset/hierachain-node -n "$NAMESPACE" --timeout=300s
      kubectl rollout status statefulset/ipfs -n "$NAMESPACE" --timeout=300s
      kubectl rollout status deployment/web2-node -n "$NAMESPACE" --timeout=300s
    else
      start_services node1 node2 node3 node4 gateway redis \
        ipfs-node1 ipfs-node2 ipfs-node3 ipfs-node4
      sleep 5
    fi
    connect_ipfs_swarm
    wait_gateway_healthy
    print_setup_summary
    ;;

  stress)
    ensure_keys
    if [ "$REUSE" = false ]; then
      generate_identities
      build_image
      down_cluster
      echo ""; echo "Starting cluster..."
      start_services node1 node2 node3 node4 gateway redis \
        ipfs-node1 ipfs-node2 ipfs-node3 ipfs-node4
    fi
    wait_nodes_healthy
    run_tests
    echo ""; echo "Stress test complete!"
    ;;

  down)
    down_cluster
    ;;

  *)
    usage
    ;;
esac
