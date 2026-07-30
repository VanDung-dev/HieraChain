#!/bin/bash
# Apply WAN simulation tc rules on wg0 based on region
# Usage: source wg-tc.sh <region>
# Defines one-way latency per side; RTT = 2x configured value

REGION=${1:-unknown}

tc qdisc del dev wg0 root 2>/dev/null || true
tc qdisc add dev wg0 root handle 1: htb default 30

tc class add dev wg0 parent 1: classid 1:30 htb rate 1000mbit
tc qdisc add dev wg0 parent 1:30 handle 30: netem delay 1ms

case "$REGION" in
    us)
        # US -> EU: RTT 200-300ms
        tc class add dev wg0 parent 1: classid 1:1 htb rate 1000mbit
        tc qdisc add dev wg0 parent 1:1 handle 10: netem delay 125ms 25ms
        tc filter add dev wg0 protocol ip parent 1:0 prio 1 u32 \
            match ip dst 10.200.2.0/24 flowid 1:1

        # US -> Asia: RTT 400-500ms
        tc class add dev wg0 parent 1: classid 1:2 htb rate 1000mbit
        tc qdisc add dev wg0 parent 1:2 handle 20: netem delay 225ms 25ms
        tc filter add dev wg0 protocol ip parent 1:0 prio 2 u32 \
            match ip dst 10.200.3.0/24 flowid 1:2
        tc filter add dev wg0 protocol ip parent 1:0 prio 3 u32 \
            match ip dst 10.200.4.0/24 flowid 1:2
        ;;
    eu)
        # EU -> US: RTT 200-300ms
        tc class add dev wg0 parent 1: classid 1:1 htb rate 1000mbit
        tc qdisc add dev wg0 parent 1:1 handle 10: netem delay 125ms 25ms
        tc filter add dev wg0 protocol ip parent 1:0 prio 1 u32 \
            match ip dst 10.200.1.0/24 flowid 1:1

        # EU -> Asia: RTT 300-400ms
        tc class add dev wg0 parent 1: classid 1:2 htb rate 1000mbit
        tc qdisc add dev wg0 parent 1:2 handle 20: netem delay 175ms 25ms
        tc filter add dev wg0 protocol ip parent 1:0 prio 2 u32 \
            match ip dst 10.200.3.0/24 flowid 1:2
        tc filter add dev wg0 protocol ip parent 1:0 prio 3 u32 \
            match ip dst 10.200.4.0/24 flowid 1:2
        ;;
    asia)
        # NOTE: applied per-node, so this is node3 OR node4, not both

        # Asia -> US: RTT 400-500ms
        tc class add dev wg0 parent 1: classid 1:1 htb rate 1000mbit
        tc qdisc add dev wg0 parent 1:1 handle 10: netem delay 225ms 25ms
        tc filter add dev wg0 protocol ip parent 1:0 prio 1 u32 \
            match ip dst 10.200.1.0/24 flowid 1:1

        # Asia -> EU: RTT 300-400ms
        tc class add dev wg0 parent 1: classid 1:2 htb rate 1000mbit
        tc qdisc add dev wg0 parent 1:2 handle 20: netem delay 175ms 25ms
        tc filter add dev wg0 protocol ip parent 1:0 prio 2 u32 \
            match ip dst 10.200.2.0/24 flowid 1:2

        # Asia -> Asia (e.g. node3->node4): RTT 0-100ms
        tc class add dev wg0 parent 1: classid 1:10 htb rate 1000mbit
        tc qdisc add dev wg0 parent 1:10 handle 100: netem delay 25ms 25ms

        # Match the other Asia node(s)
        MY_WG_IP=$(ip addr show dev wg0 | grep 'inet ' | awk '{print $2}')
        case "$MY_WG_IP" in
            10.200.3.*)
                tc filter add dev wg0 protocol ip parent 1:0 prio 10 u32 \
                    match ip dst 10.200.4.0/24 flowid 1:10
                ;;
            10.200.4.*)
                tc filter add dev wg0 protocol ip parent 1:0 prio 10 u32 \
                    match ip dst 10.200.3.0/24 flowid 1:10
                ;;
        esac
        ;;
    *)
        echo "[wg-tc] Unknown region: $REGION, no tc rules applied"
        ;;
esac
