import logging
import os

from docker.stress.docker_helper import (
    run_docker_container_action,
    run_docker_exec,
)

logger = logging.getLogger(__name__)

NODE_IDS = ("node1", "node2", "node3", "node4")
NODE_PREFIX = "hierachain-"
_RESET_ERRORS = (
    "Cannot delete qdisc with handle of zero",
    "Cannot find device",
    "No such file or directory",
    "Operation not permitted",
    "RTNETLINK answers: Invalid argument",
)


def live_docker_enabled() -> bool:
    return (
        os.getenv("HRC_STRESS_ENV") == "docker"
        and os.getenv("REAL_REQUESTS", "true").lower() == "true"
    )


def start_nodes() -> None:
    for node_id in NODE_IDS:
        _, error = run_docker_container_action(f"{NODE_PREFIX}{node_id}", "start")
        if error:
            logger.debug("Could not start %s: %s", node_id, error)


def restart_nodes(node_ids) -> None:
    for node_id in node_ids:
        _, error = run_docker_container_action(f"{NODE_PREFIX}{node_id}", "restart")
        if error:
            logger.warning("Could not restart %s: %s", node_id, error)


def reset_network() -> None:
    for node_id in NODE_IDS:
        _, error = run_docker_exec(
            f"{NODE_PREFIX}{node_id}",
            ["tc", "qdisc", "del", "dev", "eth0", "root"],
        )
        if error and not any(known in error for known in _RESET_ERRORS):
            logger.debug("Could not reset network on %s: %s", node_id, error)


def _wait_ready(timeout: float) -> tuple[bool, dict[str, str]]:
    from docker.stress.real_stress_client import RealStressClient

    client = RealStressClient()
    try:
        if client.wait_for_nodes(timeout=timeout):
            return True, {}
        return False, {
            node_id: status.last_error or "not ready"
            for node_id, status in client.node_status.items()
            if not status.is_healthy
        }
    finally:
        client.session.close()


def restore_cluster(timeout: float = 90.0) -> None:
    if not live_docker_enabled():
        return

    start_nodes()
    reset_network()

    ready, failures = _wait_ready(timeout)
    if ready:
        return

    logger.warning("Restarting unhealthy nodes before next test: %s", failures)
    restart_nodes(failures)
    ready, failures = _wait_ready(timeout)
    if not ready:
        raise RuntimeError(f"Stress cluster did not recover before the next test: {failures}")
