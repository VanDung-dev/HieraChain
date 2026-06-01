#!/bin/sh
# IPFS Private Swarm Initialization
# Runs before IPFS daemon starts (via /container-init.d/)

set -e

# 0. Clean up stale lock files from previous runs
if [ -f "/data/ipfs/repo.lock" ]; then
    echo "[IPFS Init] Removing stale repo.lock file..."
    rm -f "/data/ipfs/repo.lock"
fi

SWARM_KEY_FILE="/data/ipfs/swarm.key"

# 1. Ensure swarm.key is in place for private network
if [ -f "$SWARM_KEY_FILE" ]; then
    echo "[IPFS Init] Private swarm key found at $SWARM_KEY_FILE"
else
    echo "[IPFS Init] WARNING: No swarm.key found — running in public network mode"
fi

# 2. Initialize IPFS repo if needed
if [ ! -f /data/ipfs/config ]; then
    echo "[IPFS Init] Initializing IPFS repo..."
    ipfs init --profile=server
fi

# 3. Disable AutoConf (required for private networks in Kubo >=0.40)
#    AutoConf tries to reach conf.ipfs-mainnet.org which fails with swarm.key
ipfs config AutoConf.Enabled --bool false 2>/dev/null || true

# 4. Remove default bootstrap peers (private swarm doesn't use public bootstraps)
ipfs bootstrap rm --all 2>/dev/null || true

# 5. Bootstrap to other IPFS nodes discovered via Docker DNS
#    Kubo will auto-discover peers via mDNS on the same network,
#    so explicit bootstrap is optional for well-connected containers.
echo "[IPFS Init] Ready — Peer ID: $(ipfs config Identity.PeerID 2>/dev/null || echo 'unknown')"
