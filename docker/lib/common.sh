#!/bin/bash
# HieraChain shared library — sourced by hierachain.sh
set -e

init_env() {
  ENV=$1
  IMAGE_NAME="hierachain:latest"
  IPFS_DIR="docker/ipfs"
  K8S=false
  PROVIDER=""

  case "$ENV" in
    docker)
      ENGINE="docker"
      COMPOSE="$ENGINE compose -f docker/docker-compose.yml"
      COMPOSE_EXEC="$COMPOSE exec -T"
      COMPOSE_LOGS="$COMPOSE logs"
      ENGINE_EXEC="$ENGINE exec"
      GATEWAY_PORT=2660
      CONTAINER_PREFIX="hierachain-"
      ;;
    podman)
      ENGINE="podman"
      COMPOSE="podman-compose -f docker/docker-compose.yml -f docker/docker-compose.podman.yml"
      COMPOSE_EXEC="$COMPOSE exec -T"
      COMPOSE_LOGS="$COMPOSE logs"
      ENGINE_EXEC="$ENGINE exec"
      GATEWAY_PORT=2660
      CONTAINER_PREFIX="hierachain-"
      ;;
    k8s)
      K8S=true
      ENGINE="docker"
      KUBECTL="kubectl -n hierachain"
      COMPOSE="docker --context=orbstack compose -f docker/docker-compose.k8s-stress.yml"
      GATEWAY_PORT=32660
      NAMESPACE=hierachain
      ;;
    lxd)
      PROVIDER="lxd"
      ENGINE="lxc"
      DNS_SUFFIX="lxd"
      GATEWAY_PORT=80
      CONTAINER_PREFIX="hrc-"
      REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
      source "$SCRIPT_DIR/lib/lxd.sh"
      source "$SCRIPT_DIR/lib/ansible.sh"
      ;;
    *)
      echo "ERROR: unknown environment '$ENV'. Use: docker, podman, k8s, lxd"
      exit 1
      ;;
  esac
}

check_prereqs() {
  if [ -n "$PROVIDER" ]; then
    command -v ansible-playbook &>/dev/null || { echo "ERROR: ansible-playbook not found (brew install ansible)"; exit 1; }
    if [ "$PROVIDER" = "lxd" ]; then
      command -v lxc &>/dev/null || { echo "ERROR: lxc not found (install LXD)"; exit 1; }
    fi
  elif $K8S; then
    command -v docker &>/dev/null || { echo "ERROR: docker not installed"; exit 1; }
    command -v kubectl &>/dev/null || { echo "ERROR: kubectl not installed"; exit 1; }
    kubectl cluster-info &>/dev/null || { echo "ERROR: kubectl cannot connect to cluster"; exit 1; }
  else
    command -v "$ENGINE" &>/dev/null || { echo "ERROR: $ENGINE not installed"; exit 1; }
  fi
}

ensure_keys() {
  if [ ! -f "$IPFS_DIR/swarm.key" ]; then
    mkdir -p "$IPFS_DIR"
    SWARM_KEY_HEX=$(openssl rand -hex 32)
    { echo "/key/swarm/psk/1.0.0/"; echo "/base16/"; echo "$SWARM_KEY_HEX"; } > "$IPFS_DIR/swarm.key"
    echo "  swarm.key generated"
  fi
  if [ -z "${IPFS_ENCRYPTION_KEY:-}" ]; then
    IPFS_ENCRYPTION_KEY=$(openssl rand -hex 32)
    export IPFS_ENCRYPTION_KEY
    echo "  IPFS_ENCRYPTION_KEY generated"
  fi
  if [ -z "${EXPLORER_TOKEN:-}" ]; then
    local tkn
    tkn=$(LC_ALL=C tr -dc 'a-z0-9' < /dev/urandom | head -c 8 || echo "default")
    export EXPLORER_TOKEN="hrc_${tkn}"
  fi
}

generate_keys() {
  rm -f "$IPFS_DIR/swarm.key"
  ensure_keys
}

WHEEL_DIR="docker/dist"

build_wheel() {
  local wheel
  wheel=$(ls "$WHEEL_DIR"/hierachain-*.whl 2>/dev/null | head -1)
  if [ -n "$wheel" ] && [ "$wheel" -nt pyproject.toml ]; then
    echo "  Wheel up-to-date: $(basename "$wheel")"
    return
  fi
  echo "  Building wheel..."
  mkdir -p "$WHEEL_DIR"
  rm -f "$WHEEL_DIR"/hierachain-*.whl
  uv build --wheel -o "$WHEEL_DIR"
  wheel=$(ls "$WHEEL_DIR"/hierachain-*.whl | head -1)
  echo "  Wheel: $(basename "$wheel")"
}

generate_identities() {
  echo ""; echo "[1/6] Generating fresh node identities..."
  uv run python docker/scripts/generate_node_identities.py
}

build_image() {
  build_wheel
  if [ -n "$PROVIDER" ]; then
    echo ""; echo "[2/6] Building image... (skipped — no image needed for VM provider)"
    sleep 2
    return 0
  fi
  echo ""; echo "[2/6] Building image..."
  $ENGINE build -t "$IMAGE_NAME" -f docker/Dockerfile .
  sleep 5
}

down_cluster() {
  echo ""; echo "Stopping cluster..."
  if [ -n "$PROVIDER" ]; then
    "${PROVIDER}_delete_all"
  elif $K8S; then
    kubectl delete namespace "$NAMESPACE" 2>/dev/null || true
  else
    $COMPOSE down --remove-orphans -v 2>/dev/null || true
  fi
  echo "  Done"
}

start_services() {
  local services=$*
  echo "  Starting services: $services"
  if [ "$PROVIDER" = "lxd" ]; then
    lxd_prepare_base
    ansible_generate_inventory_base "$PROVIDER"
    ansible_run "docker/ansible/playbook.base.yml"
    lxd_snapshot_clone_all
    ansible_generate_inventory "$PROVIDER"
    ansible_run "docker/ansible/playbook.nodes.yml"
  elif [ -n "$PROVIDER" ]; then
    "${PROVIDER}_create_all"
    ansible_generate_inventory "$PROVIDER"
    ansible_run "docker/ansible/playbook.yml"
  elif $K8S; then
    return
  else
    $COMPOSE up -d $services
  fi
}

wait_gateway_healthy() {
  echo ""; echo "[6/6] Checking cluster health via Gateway..."
  local max_retries=20 retry=0 healthy=false gateway_notified=false
  while [ $retry -lt $max_retries ]; do
    local gw_endpoint="gateway-health"
    local hc_endpoint="api/ledger/health"
    local gw_pattern="gateway_up"
    local hc_pattern="healthy"
    local gw_url="http://localhost:${GATEWAY_PORT}"

    if [ "$PROVIDER" = "lxd" ]; then
      local ip
      ip=$(lxc list hrc-gateway -f csv -c 4 2>/dev/null | head -1 | cut -d' ' -f1)
      gw_url="http://${ip}"
    elif $K8S; then
      gw_endpoint="web2-status"
      gw_pattern="web2_active"
      gw_url="http://localhost:${GATEWAY_PORT}"
    fi

    if curl -sf "${gw_url}/${gw_endpoint}" | grep -q "$gw_pattern"; then
      if [ "$gateway_notified" = false ]; then
        echo "  Gateway is UP"
        gateway_notified=true
      fi
      if curl -sf "${gw_url}/${hc_endpoint}" | grep -q "$hc_pattern"; then
        echo "  Cluster is READY"
        healthy=true
        break
      fi
    fi
    local msg="Gateway"
    [ "$gateway_notified" = true ] && msg="Nodes"
    echo "  ... Waiting for $msg ($((retry+1))/$max_retries)"
    sleep 3
    retry=$((retry + 1))
  done
  if [ "$healthy" = false ]; then
    echo "  Cluster may not be healthy. Check logs."
  fi
}

wait_nodes_healthy() {
  if [ -n "$PROVIDER" ]; then
    echo ""; echo "Waiting for nodes to be healthy..."
    local max_retries=30 retry=0
    while [ $retry -lt $max_retries ]; do
      local healthy=0
      for node in node1 node2 node3 node4; do
        if "${PROVIDER}_node_exec" "$node" curl -sf "http://localhost:2661/api/ledger/health" | grep -q "healthy" 2>/dev/null; then
          healthy=$((healthy + 1))
        fi
      done
      if [ "$healthy" -ge 4 ]; then
        echo "  All nodes healthy"
        return 0
      fi
      echo "  Waiting... ($((retry+1))/$max_retries, $healthy/4)"
      sleep 3
      retry=$((retry + 1))
    done
    echo "  Cluster not healthy"
    return 1
  elif $K8S; then
    echo "  (health check handled via kubectl rollout)"
    return 0
  fi
  echo ""; echo "Waiting for nodes to be healthy..."
  local max_retries=30 retry=0
  while [ $retry -lt $max_retries ]; do
    local healthy=0 nodes_ready=true
    for node in node1 node2 node3 node4; do
      if $COMPOSE_EXEC "$node" python -c "import urllib.request; urllib.request.urlopen('http://localhost:2661/api/ledger/health', timeout=5)" 2>/dev/null; then
        healthy=$((healthy + 1))
      fi
    done
    for ipfs_node in ipfs-node1 ipfs-node2 ipfs-node3 ipfs-node4; do
      if ! $COMPOSE_EXEC "$ipfs_node" ipfs id 2>/dev/null >/dev/null; then
        nodes_ready=false
      fi
    done
    if [ "$healthy" -ge 4 ] && [ "$nodes_ready" = true ]; then
      echo "  All nodes healthy"
      return 0
    fi
    echo "  Waiting... ($((retry+1))/$max_retries, $healthy/4)"
    sleep 3
    retry=$((retry + 1))
  done
  echo "  Cluster not healthy"
  return 1
}

connect_ipfs_swarm() {
  echo ""; echo "[5/6] Connecting IPFS private swarm..."
  local max_retries=15
  if [ -n "$PROVIDER" ]; then
    for i in $(seq 1 4); do
      local node="${CONTAINER_PREFIX}ipfs-node${i}"
      echo "  Waiting for $node..."
      for j in $(seq 1 $max_retries); do
        if "${PROVIDER}_ipfs_exec" "$node" ipfs id 2>/dev/null >/dev/null; then
          break
        fi
        sleep 2
      done
    done
    local peer_ids=""
    for i in $(seq 1 4); do
      local node="${CONTAINER_PREFIX}ipfs-node${i}"
      local pid
      pid=$("${PROVIDER}_ipfs_exec" "$node" ipfs config Identity.PeerID 2>/dev/null || echo "")
      [ -n "$pid" ] && peer_ids="$peer_ids ipfs-node${i}:$pid"
    done
    local dns_suffix
    dns_suffix=$("${PROVIDER}_dns_suffix")
    for src in $(seq 1 4); do
      for dst in $(seq 1 4); do
        [ "$src" = "$dst" ] && continue
        local dst_peer
        dst_peer=$(echo "$peer_ids" | tr ' ' '\n' | grep "^ipfs-node${dst}:" | cut -d: -f2)
        if [ -n "$dst_peer" ]; then
          echo "  Connecting ipfs-node${src} → ipfs-node${dst}..."
          "${PROVIDER}_ipfs_exec" "${CONTAINER_PREFIX}ipfs-node${src}" \
            ipfs swarm connect "/dns4/${CONTAINER_PREFIX}ipfs-node${dst}.${dns_suffix}/tcp/4001/p2p/$dst_peer" 2>/dev/null || true
        fi
      done
    done
  elif $K8S; then
    for i in $(seq 0 3); do
      echo "  Waiting for ipfs-$i..."
      for j in $(seq 1 $max_retries); do
        $KUBECTL exec "ipfs-$i" -- ipfs id 2>/dev/null >/dev/null && break
        sleep 2
      done
    done
    local peer_ids=""
    for i in $(seq 0 3); do
      local pid
      pid=$($KUBECTL exec "ipfs-$i" -- ipfs config Identity.PeerID 2>/dev/null || echo "")
      [ -n "$pid" ] && peer_ids="$peer_ids ipfs-$i:$pid"
    done
    for src in $(seq 0 3); do
      for dst in $(seq 0 3); do
        [ "$src" = "$dst" ] && continue
        local dst_peer dst_ip
        dst_peer=$(echo "$peer_ids" | tr ' ' '\n' | grep "^ipfs-$dst:" | cut -d: -f2)
        dst_ip=$($KUBECTL get pod "ipfs-$dst" -o jsonpath='{.status.podIP}' 2>/dev/null || echo "")
        if [ -n "$dst_peer" ] && [ -n "$dst_ip" ]; then
          $KUBECTL exec "ipfs-$src" -- ipfs swarm connect "/ip4/$dst_ip/tcp/4001/p2p/$dst_peer" 2>/dev/null || true
        fi
      done
    done
  else
    for i in $(seq 1 4); do
      local node="${CONTAINER_PREFIX}ipfs-node${i}"
      echo "  Waiting for $node..."
      for j in $(seq 1 $max_retries); do
        $ENGINE_EXEC "$node" ipfs id 2>/dev/null >/dev/null && break
        sleep 2
      done
    done
    local peer_ids=""
    for i in $(seq 1 4); do
      local node="${CONTAINER_PREFIX}ipfs-node${i}"
      local pid
      pid=$($ENGINE_EXEC "$node" ipfs config Identity.PeerID 2>/dev/null || echo "")
      [ -n "$pid" ] && peer_ids="$peer_ids ipfs-node${i}:$pid"
    done
    for src in $(seq 1 4); do
      for dst in $(seq 1 4); do
        [ "$src" = "$dst" ] && continue
        local dst_peer dst_ip
        dst_peer=$(echo "$peer_ids" | tr ' ' '\n' | grep "^ipfs-node${dst}:" | cut -d: -f2)
        dst_ip=$(get_container_ip "${CONTAINER_PREFIX}ipfs-node${dst}")
        if [ -n "$dst_peer" ] && [ -n "$dst_ip" ]; then
          echo "  Connecting ipfs-node${src} → ipfs-node${dst}..."
          $ENGINE_EXEC "${CONTAINER_PREFIX}ipfs-node${src}" \
            ipfs swarm connect "/ip4/$dst_ip/tcp/4001/p2p/$dst_peer" 2>/dev/null || true
        fi
      done
    done
  fi
}

run_tests() {
  local report="${ENV}_stress_report"
  echo ""; echo "[4/4] Running tests..."

  if [ -n "$PROVIDER" ]; then
    local target dns
    dns=$("${PROVIDER}_dns_suffix")
    target=$("${PROVIDER}_stress_host")
    if declare -f "${PROVIDER}_node_targets" > /dev/null; then
      TARGET_NODES=$("${PROVIDER}_node_targets")
    else
      TARGET_NODES="${target}:80,${CONTAINER_PREFIX}node1.${dns}:2661,${CONTAINER_PREFIX}node2.${dns}:2661,${CONTAINER_PREFIX}node3.${dns}:2661,${CONTAINER_PREFIX}node4.${dns}:2661"
    fi
    export TARGET_NODES
    export REAL_REQUESTS=true
    export HRC_IPFS_ENABLED=true
    if declare -f "${PROVIDER}_ipfs_host" > /dev/null; then
      export HRC_IPFS_HOST=$("${PROVIDER}_ipfs_host")
    else
      export HRC_IPFS_HOST=/dns4/${CONTAINER_PREFIX}ipfs1.${dns}/tcp/5001
    fi
    export HRC_IPFS_TIMEOUT=120
    export HRC_IPFS_ENCRYPTION_KEY="${IPFS_ENCRYPTION_KEY}"
    uv run --extra dev pytest tests/stress/ -v \
      --html=log/report/${report}.html \
      --self-contained-html \
      --junitxml=log/report/${report}.xml \
      -o "addopts="
  elif $K8S; then
    TARGET_NODES="${TARGET_NODES:-host.docker.internal:${GATEWAY_PORT}}"
    k8s_env="export K8S_NAMESPACE='${NAMESPACE}'"
  else
    TARGET_NODES="gateway:80,node1:2661,node2:2661,node3:2661,node4:2661"
  fi

  if [ -z "$PROVIDER" ]; then
    $COMPOSE run --rm stress-tester \
      bash -c "
        mkdir -p /app/log/report
        export TARGET_NODES='${TARGET_NODES}'
        export TEST_DURATION='${DURATION:-60}'
        export REAL_REQUESTS='true'
        export HRC_IPFS_ENABLED=true
        export HRC_IPFS_HOST=/dns4/ipfs-node1/tcp/5001
        export HRC_IPFS_ENCRYPTION_KEY='${IPFS_ENCRYPTION_KEY}'
        ${k8s_env}
        uv run pytest tests/stress/ -v \
          --html=/app/log/report/${report}.html \
          --self-contained-html \
          --junitxml=/app/log/report/${report}.xml
      "
  fi
}

discover_nodes() {
  HRC_NODES=$(grep "hostname:" docker/docker-compose.yml | awk '{print $2}' | grep -v -E "gateway|redis|ipfs" | tr '\n' ',' | sed 's/,$//')
  export HRC_NODES
  echo "  Nodes: $HRC_NODES"
}

get_container_ip() {
  local container=$1
  case "$ENV" in
    docker)
      docker inspect -f '{{(index .NetworkSettings.Networks "docker_wgmesh").IPAddress}}' "$container" 2>/dev/null || echo ""
      ;;
    podman)
      podman inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$v.IPAddress}}{{"\n"}}{{end}}' "$container" 2>/dev/null | head -1 || echo ""
      ;;
  esac
}

print_setup_summary() {
  local port=$GATEWAY_PORT

  echo ""
  echo "========================================"
  echo " Deployment complete! (${ENV})"
  echo "========================================"
  echo ""
  echo "Enterprise API Gateway (Web2 simulation):"
  echo "  Primary Port: ${port}"

  if [ -n "$PROVIDER" ]; then
    local gw_url
    gw_url=$("${PROVIDER}_gateway_url")
    echo "  Gateway URL: ${gw_url}"
    echo ""
    echo "Developer Helper:"
    echo "  Gateway:  ${gw_url}"
  else
    echo "  (Accessible from LAN 0.0.0.0)"
    local dev_helper=$([ "$ENV" = "podman" ] && echo "podman exec" || echo "docker exec")
    echo ""
    echo "Developer Helper:"
    echo "  Get token: ${dev_helper} ${CONTAINER_PREFIX}gateway env | grep EXPLORER_TOKEN"
  fi

  echo ""
  echo "Stealth Explorer (Secure Access):"
  echo "  Token:    ${EXPLORER_TOKEN}"
  if [ -n "$PROVIDER" ]; then
    local gw_url
    gw_url=$("${PROVIDER}_gateway_url")
    echo "  Status:   ${gw_url}/${EXPLORER_TOKEN}/status"
    echo "  Explorer: ${gw_url}/${EXPLORER_TOKEN}/explorer"
  else
    echo "  Status:   http://localhost:${port}/${EXPLORER_TOKEN}/status"
    echo "  Explorer: http://localhost:${port}/${EXPLORER_TOKEN}/explorer"
  fi

  echo ""
  echo "HieraChain Nodes (WireGuard Mesh):"
  echo "  node1 (US region)   → 10.200.1.1"
  echo "  node2 (EU region)   → 10.200.2.1"
  echo "  node3 (Asia region) → 10.200.3.1"
  echo "  node4 (Asia region) → 10.200.4.1"

  echo ""
  echo "IPFS Private Swarm:"
  if [ -n "$PROVIDER" ]; then
    local dns_suffix
    dns_suffix=$("${PROVIDER}_dns_suffix")
    for i in $(seq 1 4); do
      echo "  ${CONTAINER_PREFIX}ipfs-node${i} → ${CONTAINER_PREFIX}ipfs-node${i}.${dns_suffix}"
    done
  else
    for i in $(seq 1 4); do
      local ip=$(get_container_ip "${CONTAINER_PREFIX}ipfs-node${i}")
      echo "  ipfs-node${i} → ${ip:-N/A}"
    done
  fi

  echo ""
  echo "Encryption Key: ${IPFS_ENCRYPTION_KEY:0:16}..."
  echo ""
  echo "Next steps:"
  echo "  Stress test: bash docker/hierachain.sh stress ${ENV} --reuse"
  echo "  Cleanup:     bash docker/hierachain.sh down ${ENV}"
  echo "========================================"
}
