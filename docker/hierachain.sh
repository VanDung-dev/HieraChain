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
  setup                 Deploy full cluster (K8s preserves data unless --force)
  stress                Run stress tests (requires running cluster)
  down                  Stop and clean up cluster

Environments:
  docker                Docker Compose (multi-region + WireGuard)
  k8s                   OrbStack Kubernetes

Options:
  --duration, -d N      Test duration in seconds (Docker stress default: 15; otherwise: 60)
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
if [ "$COMMAND" = "stress" ] && [ "$ENV" = "docker" ]; then
  DURATION=15
fi

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
    if $K8S; then
      ensure_keys
      build_image
      if $FORCE; then down_cluster; fi
      deploy_k8s
      wait_nodes_healthy
    else
      generate_keys
      generate_identities
      discover_nodes
      build_image
      down_cluster
      echo ""; echo "[4/6] Starting cluster..."
      start_services postgres-node1 postgres-node2 postgres-node3 postgres-node4 \
        node1 node2 node3 node4 gateway redis \
        ipfs-node1 ipfs-node2 ipfs-node3 ipfs-node4
      sleep 5
    fi
    connect_ipfs_swarm
    wait_gateway_healthy
    print_setup_summary
    ;;

  stress)
    if [ "$K8S" = false ]; then
      ensure_stress_api_key
    fi
    ensure_keys
    if [ "$REUSE" = false ]; then
      if $K8S; then
        build_image
        if $FORCE; then down_cluster; fi
        deploy_k8s
      else
        generate_identities
        build_image
        down_cluster
        echo ""; echo "Starting cluster..."
        start_services postgres-node1 postgres-node2 postgres-node3 postgres-node4 \
          node1 node2 node3 node4 gateway redis \
          ipfs-node1 ipfs-node2 ipfs-node3 ipfs-node4
      fi
    fi
    wait_nodes_healthy
    if $K8S; then connect_ipfs_swarm; fi
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
