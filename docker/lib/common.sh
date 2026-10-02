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
      COMPOSE="$ENGINE compose --env-file .env -f docker/docker-compose.yml"
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
    *)
      echo "ERROR: unknown environment '$ENV'. Supported environments: docker, k8s"
      exit 1
      ;;
  esac
}

check_prereqs() {
  if $K8S; then
    command -v docker &>/dev/null || { echo "ERROR: docker not installed"; exit 1; }
    command -v kubectl &>/dev/null || { echo "ERROR: kubectl not installed"; exit 1; }
    kubectl cluster-info &>/dev/null || { echo "ERROR: kubectl cannot connect to cluster"; exit 1; }
  else
    command -v "$ENGINE" &>/dev/null || { echo "ERROR: $ENGINE not installed"; exit 1; }
  fi
}

ensure_product_env() {
  if [ ! -f ".env" ] && [ -f "docker/.env.HRC.example" ]; then
    cp docker/.env.HRC.example .env
    echo "  .env created from docker/.env.HRC.example (product)"
  elif [ ! -f ".env" ] && [ -f ".env.HRC.example" ]; then
    cp .env.HRC.example .env
    echo "  .env created from .env.HRC.example (product)"
  fi
  if [ -f ".env" ] && [ ! -f "docker/.env" ]; then
    cp .env docker/.env 2>/dev/null || true
  fi
  if [ ! -f "docker/.env" ] && [ -f "docker/.env.HRC.example" ]; then
    cp docker/.env.HRC.example docker/.env
    echo "  docker/.env created from docker/.env.HRC.example (product)"
  fi
  # verify product
  if [ -f ".env" ] && grep -q "HRC_ENV=product" .env; then
    echo "  .env verified: HRC_ENV=product (product mode)"
  elif [ -f "docker/.env.HRC.example" ]; then
    echo "  Note: .env not product — docker nodes will still use /app/.env.HRC.example via entrypoint"
  fi
}

read_configured_ipfs_key() {
  local env_file="$1" line value parsed_key="" seen=false
  [ -f "$env_file" ] || return 1

  while IFS= read -r line || [ -n "$line" ]; do
    [[ "$line" =~ ^[[:space:]]*(export[[:space:]]+)?IPFS_ENCRYPTION_KEY[[:space:]]*=[[:space:]]*(.*)$ ]] || continue
    seen=true
    value="${BASH_REMATCH[2]}"
    value="${value%$'\r'}"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"

    if [[ "$value" =~ ^\"([[:xdigit:]]{64})\"([[:space:]]*#.*)?$ ]] \
      || [[ "$value" =~ ^\'([[:xdigit:]]{64})\'([[:space:]]*#.*)?$ ]] \
      || [[ "$value" =~ ^([[:xdigit:]]{64})([[:space:]]+#.*)?$ ]]; then
      parsed_key="${BASH_REMATCH[1]}"
    elif [[ -z "$value" || "$value" =~ ^#.*$ ]]; then
      parsed_key=""
    else
      return 2
    fi
  done < "$env_file"

  [ "$seen" = true ] || return 1
  printf '%s' "$parsed_key"
}

ensure_keys() {
  if [ ! -f "$IPFS_DIR/swarm.key" ]; then
    mkdir -p "$IPFS_DIR"
    SWARM_KEY_HEX=$(openssl rand -hex 32)
    { echo "/key/swarm/psk/1.0.0/"; echo "/base16/"; echo "$SWARM_KEY_HEX"; } > "$IPFS_DIR/swarm.key"
    echo "  swarm.key generated"
  fi
  if [ -z "${IPFS_ENCRYPTION_KEY:-}" ]; then
    local configured_key configured_status env_file
    for env_file in ".env" "docker/.env"; do
      if [ -f "$env_file" ]; then
        if configured_key=$(read_configured_ipfs_key "$env_file"); then
          if [ -n "$configured_key" ]; then
            IPFS_ENCRYPTION_KEY="$configured_key"
            echo "  IPFS_ENCRYPTION_KEY loaded from $env_file"
            break
          fi
        else
          configured_status=$?
          if [ "$configured_status" -eq 2 ]; then
            echo "ERROR: IPFS_ENCRYPTION_KEY in $env_file must contain exactly 64 hexadecimal characters (32 bytes)"
            exit 1
          fi
        fi
      fi
    done
  fi
  if [ -z "${IPFS_ENCRYPTION_KEY:-}" ]; then
    local encryption_key_file="$IPFS_DIR/encryption.key"
    mkdir -p "$IPFS_DIR"
    if [ ! -f "$encryption_key_file" ]; then
      local generated_key
      generated_key=$(openssl rand -hex 32)
      # Create the secret once, without replacing a key created by a concurrent setup.
      (umask 077; set -o noclobber; printf '%s\n' "$generated_key" > "$encryption_key_file") 2>/dev/null || true
      if [ ! -f "$encryption_key_file" ]; then
        echo "ERROR: could not persist IPFS encryption key to $encryption_key_file"
        exit 1
      fi
    fi
    chmod 600 "$encryption_key_file"
    IFS= read -r IPFS_ENCRYPTION_KEY < "$encryption_key_file" || true
    echo "  IPFS_ENCRYPTION_KEY loaded from $encryption_key_file"
  fi
  if [[ ! "$IPFS_ENCRYPTION_KEY" =~ ^[[:xdigit:]]{64}$ ]]; then
    echo "ERROR: IPFS_ENCRYPTION_KEY must contain exactly 64 hexadecimal characters (32 bytes)"
    exit 1
  fi
  export IPFS_ENCRYPTION_KEY
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

ensure_stress_api_key() {
  $COMPOSE --profile stress-test config --format json | uv run --no-sync python -c '
import sys
import orjson
config = orjson.loads(sys.stdin.buffer.read())
key = config["services"]["stress-tester"].get("environment", {}).get("HRC_API_KEY")
if not isinstance(key, str) or not key.strip():
    raise SystemExit("ERROR: set HRC_API_KEY in .env or the environment to a provisioned chains/events/proofs key before stress")
'
}

build_wheel() {
  local wheel
  echo "  Building wheel..."
  mkdir -p "$WHEEL_DIR"
  # setuptools reuses build/lib, which can retain modules deleted from the source tree.
  rm -rf build
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
  echo ""; echo "[2/6] Building image..."
  $ENGINE build --target production -t "$IMAGE_NAME" -f docker/Dockerfile .
  sleep 5
}

down_cluster() {
  echo ""; echo "Stopping cluster..."
  if $K8S; then
    kubectl delete namespace "$NAMESPACE" 2>/dev/null || true
  else
    $COMPOSE down --remove-orphans -v 2>/dev/null || true
  fi
  echo "  Done"
}

start_services() {
  local services=$*
  echo "  Starting services: $services"
  if $K8S; then
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

    if $K8S; then
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
  if $K8S; then
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
  if $K8S; then
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

  if $K8S; then
    k8s_env="export K8S_NAMESPACE='${NAMESPACE}'"
    # K8s in-cluster Job uses K8s DNS (web2-service etc.), compose fallback uses host gateway
    K8S_JOB_NODES="web2-service:80,hierachain-node-0.hierachain-node-headless:2661,hierachain-node-1.hierachain-node-headless:2661,hierachain-node-2.hierachain-node-headless:2661,hierachain-node-3.hierachain-node-headless:2661"
    K8S_COMPOSE_NODES="${TARGET_NODES:-host.docker.internal:${GATEWAY_PORT}}"
    # Try in-cluster Job first
    if kubectl get namespace "${NAMESPACE}" >/dev/null 2>&1; then
      echo "  Running K8s stress via Job (in-cluster DNS: ${K8S_JOB_NODES})..."
      kubectl apply -f docker/k8s/stress-tester.yaml >/dev/null 2>&1 || true
      # Ensure Job uses correct nodes and duration
      kubectl set env job/stress-tester -n "${NAMESPACE}" TARGET_NODES="${K8S_JOB_NODES}" TEST_DURATION="${DURATION:-60}" >/dev/null 2>&1 || true
      if kubectl wait --for=condition=complete job/stress-tester -n "${NAMESPACE}" --timeout=400s 2>/dev/null; then
        kubectl logs -n "${NAMESPACE}" job/stress-tester --tail=300 2>/dev/null || true
        # copy reports from job
        kubectl cp "${NAMESPACE}/$(kubectl get pod -n "${NAMESPACE}" -l job-name=stress-tester -o jsonpath='{.items[0].metadata.name} 2>/dev/null'):/app/log/report/${report}.html" "log/${report}.html" 2>/dev/null || true
        return 0
      fi
      echo "  K8s Job not ready, falling back to compose stress-tester with ${K8S_COMPOSE_NODES}..."
      TARGET_NODES="${K8S_COMPOSE_NODES}"
      # Patch docker-stress-entrypoint gateway IP if needed (host.docker.internal fallback)
      # Let entrypoint handle host.docker.internal -> gateway IP
    else
      TARGET_NODES="${K8S_COMPOSE_NODES}"
    fi
  else
    TARGET_NODES="gateway:80,node1:2661,node2:2661,node3:2661,node4:2661"
  fi

  $COMPOSE --profile stress-test run --rm stress-tester \
    bash -c "
      set -e
      mkdir -p /app/log/report
      export TARGET_NODES='${TARGET_NODES}'
      export TEST_DURATION='${DURATION:-60}'
      export REAL_REQUESTS='true'
      export HRC_STRESS_ENV='${ENV}'
      export HRC_IPFS_ENABLED=true
      export HRC_IPFS_HOST=/dns4/ipfs-node1/tcp/5001
      export HRC_IPFS_ENCRYPTION_KEY='${IPFS_ENCRYPTION_KEY}'
      ${k8s_env}
      pytest docker/stress/ -v --log-level=INFO --durations=10 \
        -o log_cli=false -o faulthandler_timeout=0 --show-capture=no --tb=short \
        --html=/app/log/report/${report}.html \
        --self-contained-html \
        --junitxml=/app/log/report/${report}.xml
    "
}

discover_nodes() {
  HRC_NODES=$(grep "hostname:" docker/docker-compose.yml | awk '{print $2}' | grep -v -E "gateway|redis|ipfs|postgres" | tr '\n' ',' | sed 's/,$//')
  export HRC_NODES
  echo "  Nodes: $HRC_NODES"
}

get_container_ip() {
  local container=$1
  docker inspect -f '{{(index .NetworkSettings.Networks "docker_wgmesh").IPAddress}}' "$container" 2>/dev/null || echo ""
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
  echo "  (Accessible from LAN 0.0.0.0)"
  echo ""
  echo "Developer Helper:"
  echo "  Get token: docker exec ${CONTAINER_PREFIX}gateway env | grep EXPLORER_TOKEN"

  echo ""
  echo "Stealth Explorer (Secure Access):"
  echo "  Token:    ${EXPLORER_TOKEN}"
  echo "  Status:   http://localhost:${port}/${EXPLORER_TOKEN}/status"
  echo "  Explorer: http://localhost:${port}/${EXPLORER_TOKEN}/explorer"

  echo ""
  echo "HieraChain Nodes (WireGuard Mesh):"
  echo "  node1 (US region)   → 10.200.1.1"
  echo "  node2 (EU region)   → 10.200.2.1"
  echo "  node3 (Asia region) → 10.200.3.1"
  echo "  node4 (Asia region) → 10.200.4.1"

  echo ""
  echo "IPFS Private Swarm:"
  for i in $(seq 1 4); do
    local ip=$(get_container_ip "${CONTAINER_PREFIX}ipfs-node${i}")
    echo "  ipfs-node${i} → ${ip:-N/A}"
  done

  echo ""
  echo "Encryption Key: configured (hidden)"
  echo ""
  echo "Next steps:"
  echo "  Stress test: bash docker/hierachain.sh stress ${ENV} --reuse"
  echo "  Cleanup:     bash docker/hierachain.sh down ${ENV}"
  echo "========================================"
}
