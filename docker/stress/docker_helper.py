"""
Docker API Socket Helpers.
Provides low-level socket communication with the local Docker daemon to inspect,
stop, start, pause, and check resource usage of container instances.
"""

import json
import socket
import http.client
import os
import subprocess
import logging

logger = logging.getLogger(__name__)

class DockerSocketClient:
    def __init__(self, socket_path="/var/run/docker.sock"):
        self.socket_path = socket_path

    def request(self, method: str, path: str, body=None) -> tuple[int, str]:
        if not os.path.exists(self.socket_path):
            raise FileNotFoundError(f"Docker socket not found at {self.socket_path}")
        conn = http.client.HTTPConnection("localhost")
        conn.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        conn.sock.connect(self.socket_path)
        
        headers = {"Content-Type": "application/json"}
        conn.request(method, path, body=json.dumps(body) if body else None, headers=headers)
        res = conn.getresponse()
        data = res.read().decode()
        return res.status, data

    def container_action(self, container_name: str, action: str) -> bool:
        try:
            status, data = self.request("POST", f"/v1.41/containers/{container_name}/{action}")
            if status in (200, 204, 304):  # 304 means container already in that state
                return True
            logger.error(f"Docker socket {action} failed on {container_name}: status={status}, data={data}")
            return False
        except Exception as e:
            logger.error(f"Docker socket container_action error: {e}")
            return False

    def container_update(self, container_name: str, cpus: float) -> bool:
        try:
            quota = int(cpus * 100000)
            body = {
                "CpuPeriod": 100000,
                "CpuQuota": quota
            }
            status, data = self.request("POST", f"/v1.41/containers/{container_name}/update", body)
            if status in (200, 204):
                return True
            logger.error(f"Docker socket update failed on {container_name}: status={status}, data={data}")
            return False
        except Exception as e:
            logger.error(f"Docker socket container_update error: {e}")
            return False

    def exec_run(self, container_name: str, cmd: list[str]) -> tuple[int, str]:
        try:
            status, data = self.request("POST", f"/v1.41/containers/{container_name}/exec", {
                "AttachStdout": True,
                "AttachStderr": True,
                "Cmd": cmd,
                "User": "root"
            })
            if status != 201:
                return status, f"Failed to create exec: {data}"
            exec_id = json.loads(data)["Id"]
            
            status, data = self.request("POST", f"/v1.41/exec/{exec_id}/start", {"Detach": False, "Tty": False})
            return status, data
        except Exception as e:
            return 500, str(e)


# Global client instance
_socket_client = None

def get_docker_client():
    global _socket_client
    if _socket_client is None:
        _socket_client = DockerSocketClient()
    return _socket_client

def run_docker_container_action(container_name: str, action: str) -> tuple[str, str]:
    """
    Tries to run stop/start/restart using docker CLI first, and falls back to unix socket API
    if the docker CLI is not found or fails.
    """
    try:
        # Try docker CLI
        result = subprocess.run(["docker", action, container_name], capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            return result.stdout, result.stderr
        # If CLI failed but exists, log and try socket
        logger.info(f"Docker CLI failed (code {result.returncode}), trying docker socket...")
    except FileNotFoundError:
        # CLI not found, try socket
        pass
    except Exception as e:
        logger.warning(f"Docker CLI error: {e}, trying docker socket...")

    # Fallback to docker socket API
    client = get_docker_client()
    success = client.container_action(container_name, action)
    if success:
        return f"Successfully {action}ed container {container_name} via socket", ""
    else:
        return "", f"Failed to {action} container {container_name} via socket"

def run_docker_container_update(container_name: str, cpus: str) -> tuple[str, str]:
    """
    Tries to run docker update --cpus using CLI first, and falls back to unix socket API.
    """
    try:
        result = subprocess.run(["docker", "update", "--cpus", cpus, container_name], capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            return result.stdout, result.stderr
    except FileNotFoundError:
        pass
    except Exception:
        pass

    try:
        client = get_docker_client()
        success = client.container_update(container_name, float(cpus))
        if success:
            return f"Successfully updated container {container_name} cpus to {cpus} via socket", ""
        else:
            return "", f"Failed to update container {container_name} cpus via socket"
    except Exception as e:
        return "", str(e)

def run_docker_exec(container_name: str, cmd: list[str]) -> tuple[str, str]:
    """
    Tries to run docker exec using CLI first, and falls back to unix socket API.
    """
    try:
        result = subprocess.run(["docker", "exec", container_name] + cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            return result.stdout, result.stderr
    except FileNotFoundError:
        pass
    except Exception:
        pass

    try:
        client = get_docker_client()
        status, data = client.exec_run(container_name, cmd)
        if status in (200, 201):
            return data, ""
        else:
            return "", f"Docker socket exec failed: status={status}, data={data}"
    except Exception as e:
        return "", str(e)
