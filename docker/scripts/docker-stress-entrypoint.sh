#!/bin/sh
# Entrypoint for stress tester to patch kubeconfig and handle network routing
set -e

# Copy kubeconfig to a writable location if it exists
if [ -f /root/.kube/config ]; then
  echo "Setting up writable kubeconfig..."
  mkdir -p /app/data/.kube
  cp /root/.kube/config /app/data/.kube/config
  export KUBECONFIG=/app/data/.kube/config
  
  echo "Patching kubeconfig: 127.0.0.1 -> host.docker.internal"
  sed -i 's/127.0.0.1/host.docker.internal/g' "$KUBECONFIG"
fi

# Verify host.docker.internal is reachable
if ping -c 1 -W 2 host.docker.internal > /dev/null 2>&1; then
  echo "host.docker.internal is reachable."
else
  echo "WARNING: host.docker.internal is NOT reachable. Attempting Gateway IP fallback..."
  
  # Find Gateway IP using /proc/net/route (standard on Linux, no extra tools needed)
  HOST_IP=$(awk 'NR>1 && $2=="00000000" {
    hex=$8; 
    printf "%d.%d.%d.%d\n",
      strtonum("0x"substr(hex,7,2)),
      strtonum("0x"substr(hex,5,2)),
      strtonum("0x"substr(hex,3,2)),
      strtonum("0x"substr(hex,1,2))
    exit
  }' /proc/net/route 2>/dev/null)

  if [ -n "$HOST_IP" ]; then
    echo "Gateway IP found: $HOST_IP — patching kubeconfig and TARGET_NODES..."
    # Patch kubeconfig if it exists
    if [ -f "$KUBECONFIG" ]; then
        sed -i "s/host.docker.internal/$HOST_IP/g" "$KUBECONFIG"
    fi
    # Update TARGET_NODES to use the host IP
    # We strip the current host but keep the port (defaulting to 32661)
    PORT=$(echo "$TARGET_NODES" | cut -d: -f2)
    [ -z "$PORT" ] || [ "$PORT" = "$TARGET_NODES" ] && PORT="32661"
    export TARGET_NODES="${HOST_IP}:${PORT}"
    echo "New TARGET_NODES: $TARGET_NODES"
  else
    echo "ERROR: Could not determine host IP. Network tests will likely fail."
  fi
fi

# Activate virtual environment
if [ -f /app/.venv/bin/activate ]; then
  . /app/.venv/bin/activate
fi

# Execute the original command passed by Docker
echo "Executing: $@"
exec "$@"
