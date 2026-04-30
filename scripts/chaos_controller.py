#!/usr/bin/env python3
"""
HieraChain Chaos Controller (Socket Edition)
Uses Docker Engine API via unix socket to avoid dependency on docker CLI.
"""

import json
import socket
import sys
import argparse
import logging
import http.client

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ChaosController")

class DockerSocketClient:
    def __init__(self, socket_path="/var/run/docker.sock"):
        self.socket_path = socket_path

    def post(self, path, body=None):
        conn = http.client.HTTPConnection("localhost")
        conn.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        conn.sock.connect(self.socket_path)
        
        headers = {"Content-Type": "application/json"}
        conn.request("POST", path, body=json.dumps(body) if body else None, headers=headers)
        res = conn.getresponse()
        data = res.read().decode()
        return res.status, data

    def exec_run(self, container_name, cmd):
        """Execute a command in a container via Docker API."""
        # 1. Create exec instance
        status, data = self.post(f"/v1.41/containers/{container_name}/exec", {
            "AttachStdout": True,
            "AttachStderr": True,
            "Cmd": cmd,
            "User": "root"
        })
        
        if status != 201:
            logger.error(f"Failed to create exec on {container_name}: {data}")
            return None
            
        exec_id = json.loads(data)["Id"]
        
        # 2. Start exec instance
        status, data = self.post(f"/v1.41/exec/{exec_id}/start", {"Detach": False, "Tty": False})
        if status != 200:
            logger.error(f"Failed to start exec on {container_name}: {data}")
            return None
            
        return data

class ChaosController:
    def __init__(self):
        self.nodes = ["hierachain-node1", "hierachain-node2", "hierachain-node3", "hierachain-node4"]
        self.client = DockerSocketClient()

    def apply_latency(self, node, ms=150, jitter=20, loss=1):
        logger.info(f"Applying WAN simulation to {node}: {ms}ms latency, {jitter}ms jitter, {loss}% loss")
        
        # Clean up existing rules
        self.client.exec_run(node, ["tc", "qdisc", "del", "dev", "eth0", "root"]) 
        
        # Add new latency rule
        cmd = ["tc", "qdisc", "add", "dev", "eth0", "root", "netem", 
               "delay", f"{ms}ms", f"{jitter}ms", "distribution", "normal",
               "loss", f"{loss}%"]
        
        if self.client.exec_run(node, cmd) is not None:
            logger.info(f"✅ WAN simulation active on {node}")

    def reset_network(self, node):
        logger.info(f"Resetting network on {node}")
        self.client.exec_run(node, ["tc", "qdisc", "del", "dev", "eth0", "root"])
        logger.info(f"✅ Network reset on {node}")

    def status(self, node):
        print(f"\n--- Network status for {node} ---")
        out = self.client.exec_run(node, ["tc", "qdisc", "show", "dev", "eth0"])
        print(out if out else "No active rules")

def main():
    parser = argparse.ArgumentParser(description="HieraChain Chaos Controller (Socket Edition)")
    parser.add_argument("action", choices=["apply", "reset", "status"], help="Action to perform")
    parser.add_argument("--node", help="Specific node (default: all)")
    parser.add_argument("--latency", type=int, default=150, help="Latency in ms (default: 150)")
    parser.add_argument("--jitter", type=int, default=20, help="Jitter in ms (default: 20)")
    parser.add_argument("--loss", type=int, default=1, help="Packet loss percentage (default: 1)")

    args = parser.parse_args()
    controller = ChaosController()
    
    target_nodes = [args.node] if args.node else controller.nodes

    for node in target_nodes:
        if args.action == "apply":
            controller.apply_latency(node, args.latency, args.jitter, args.loss)
        elif args.action == "reset":
            controller.reset_network(node)
        elif args.action == "status":
            controller.status(node)

if __name__ == "__main__":
    main()
