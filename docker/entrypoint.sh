#!/bin/bash
set -e

REGION=${HRC_REGION:-unknown}
NODE_ID=${HRC_NODE_ID:-unknown}

echo "[entrypoint] Starting node $NODE_ID (region: $REGION)"

WG_CONF="/app/config/identity/wg0.conf"
if [ -f "$WG_CONF" ]; then
    echo "[entrypoint] Initializing WireGuard interface"

    ip link add wg0 type wireguard 2>/dev/null || true
    wg setconf wg0 "$WG_CONF"

    WG_ADDR="${HRC_P2P_HOST:-10.200.0.0}/16"
    ip addr add "$WG_ADDR" dev wg0 2>/dev/null || true
    ip link set wg0 up

    WG_SCRIPT="/app/docker/scripts/wg-tc.sh"
    if [ -f "$WG_SCRIPT" ]; then
        echo "[entrypoint] Applying WAN simulation for $REGION"
        source "$WG_SCRIPT" "$REGION"
    fi

    echo "[entrypoint] WireGuard ready ($(wg show wg0 | head -1))"
else
    echo "[entrypoint] WARNING: No wg0.conf found"
fi

echo "[entrypoint] Starting HieraChain node $NODE_ID..."
. /app/.venv/bin/activate
exec "$@"
