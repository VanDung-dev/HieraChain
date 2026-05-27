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

# Verify host.docker.internal is reachable via TCP
# (ping/curl not available in python:3.12-slim images)
HOST_REACHABLE=$(python3 -c "
import socket
try:
    s = socket.create_connection(('host.docker.internal', 80), timeout=2)
    s.close()
    print('yes')
except Exception:
    print('no')
" 2>/dev/null || echo "no")

if [ "$HOST_REACHABLE" = "yes" ]; then
  echo "host.docker.internal is reachable."
else
  echo "WARNING: host.docker.internal is NOT reachable. Attempting Gateway IP fallback..."

  # Extract gateway IP from /proc/net/route using Python
  # (mawk lacks strtonum, so awk-based hex parsing is unreliable in slim images)
  HOST_IP=$(python3 -c "
import struct, socket
with open('/proc/net/route') as f:
    next(f)  # skip header
    for line in f:
        parts = line.strip().split()
        if parts[1] == '00000000':
            print(socket.inet_ntoa(struct.pack('<I', int(parts[2], 16))))
            break
" 2>/dev/null || echo "")

  if [ -n "$HOST_IP" ]; then
    echo "Gateway IP found: $HOST_IP — patching kubeconfig and TARGET_NODES..."
    # Patch kubeconfig if it exists
    if [ -f "$KUBECONFIG" ]; then
        sed -i "s/host.docker.internal/$HOST_IP/g" "$KUBECONFIG"
    fi
    # Update TARGET_NODES to use the host IP
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
