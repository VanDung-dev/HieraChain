# LXD provider — create/delete/manage containers via `lxc` CLI

LXD_CONTAINERS=(hrc-redis hrc-gateway hrc-ipfs{1..4} hrc-node{1..4})

lxd_prepare_base() {
  echo "  Preparing base container (Ubuntu 24.04)..."
  lxc delete -f hrc-base 2>/dev/null || true
  lxc launch ubuntu:24.04 hrc-base >/dev/null
  echo "  Waiting for base to start..."
  sleep 5
  echo "  Base container ready"
}

lxd_snapshot_clone_all() {
  echo "  Snapshotting base..."
  lxc snapshot hrc-base snap

  echo "  Cloning to all containers..."
  for name in "${LXD_CONTAINERS[@]}"; do
    lxc delete -f "$name" 2>/dev/null || true
    lxc copy hrc-base/snap "$name"
    lxc start "$name" >/dev/null 2>&1
    sleep 3
    echo "    $name started"
  done

  lxc delete -f hrc-base
  echo "  All containers cloned and started"
}

lxd_delete_all() {
  echo "  Deleting LXD containers..."
  lxc delete -f hrc-base 2>/dev/null || true
  for name in "${LXD_CONTAINERS[@]}"; do
    lxc delete -f "$name" 2>/dev/null || true
  done
  echo "  Done"
}

lxd_gateway_url() {
  local ip
  ip=$(lxc list hrc-gateway -f csv -c 4 | head -1 | cut -d' ' -f1)
  echo "http://${ip}"
}

lxd_node_exec() {
  local node=$1; shift
  lxc exec "hrc-${node}" -- "$@"
}

lxd_ipfs_exec() {
  local name=$1; shift
  lxc exec "$name" -- "$@"
}

lxd_dns_suffix() {
  echo "lxd"
}

lxd_stress_host() {
  local ip
  ip=$(lxc list hrc-gateway -f csv -c 4 | head -1 | cut -d' ' -f1)
  echo "${ip}"
}

lxd_node_targets() {
  local gateway_ip ip
  gateway_ip=$(lxc list hrc-gateway -f csv -c 4 | head -1 | cut -d' ' -f1)
  local targets="${gateway_ip}:80"
  for i in 1 2 3 4; do
    ip=$(lxc list "hrc-node${i}" -f csv -c 4 | head -1 | cut -d' ' -f1)
    targets="${targets},${ip}:2661"
  done
  echo "${targets}"
}

lxd_ipfs_host() {
  local ip
  ip=$(lxc list hrc-ipfs1 -f csv -c 4 | head -1 | cut -d' ' -f1)
  echo "/ip4/${ip}/tcp/5001"
}
