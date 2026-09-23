"""Offline checks for guards used by the live Docker stress tests."""

import json

import pytest

import docker.stress.docker_helper as docker_helper
import docker.stress.real_stress_client as real_client
import docker.stress.resource_monitoring as resource_monitoring
import docker.stress.test_chaos as chaos
import docker.stress.test_resource_monitoring as resource_test_module
from docker.stress.resource_monitoring import ResourceMonitor, ResourceStressTester
from docker.stress.test_network_conditions import NetworkStressTester
from docker.stress.test_network_simulation import NetworkSimulator
from docker.stress.test_poison_pill import PoisonPillTest
from docker.stress.test_tsunami_flood import TsunamiFloodTest


def test_flood_and_poison_tests_refuse_local_simulation(monkeypatch):
    monkeypatch.setattr(real_client, "REAL_REQUESTS", False)
    flood = TsunamiFloodTest({"target_nodes": ["node1:2661"]})
    poison = PoisonPillTest({"target_nodes": ["node1:2661"]})

    with pytest.raises(RuntimeError, match="live RealStressClient"):
        flood._process_event({"event_type": "test"}, "node1")
    with pytest.raises(RuntimeError, match="REAL_REQUESTS=true"):
        poison.send_event("node1", {"_is_poison": True})


def test_shared_stress_runner_and_resource_tester_fail_without_live_services(monkeypatch):
    class OfflineClient:
        def wait_for_nodes(self, timeout):
            return False

    monkeypatch.setattr(real_client, "RealStressClient", OfflineClient)
    with pytest.raises(RuntimeError, match="healthy"):
        real_client.run_real_stress_test(duration=0)

    monkeypatch.setattr(resource_monitoring, "REAL_REQUESTS", False)
    with pytest.raises(RuntimeError, match="REAL_REQUESTS=true"):
        ResourceStressTester(nodes=["node1:2661"])


def test_resource_monitor_uses_real_docker_stats_and_rejects_unavailable_data(monkeypatch):
    stats = {
        "cpu_stats": {
            "cpu_usage": {"total_usage": 2000},
            "system_cpu_usage": 10000,
            "online_cpus": 2,
        },
        "precpu_stats": {
            "cpu_usage": {"total_usage": 1000},
            "system_cpu_usage": 5000,
        },
        "memory_stats": {"usage": 50 * 1024 * 1024},
        "networks": {"eth0": {"rx_bytes": 10, "tx_bytes": 20}},
        "blkio_stats": {"io_service_bytes_recursive": [{"op": "Read", "value": 30}]},
    }

    class DockerStats:
        def request(self, method, path):
            assert method == "GET"
            assert path == "/v1.41/containers/hierachain-node1/stats?stream=false"
            return 200, json.dumps(stats)

    monkeypatch.setattr(docker_helper, "get_docker_client", lambda: DockerStats())
    metric = ResourceMonitor(nodes=["node1"])._get_container_metrics("node1")
    assert metric.cpu_usage == 40
    assert metric.memory_usage == 50

    class UnavailableDockerStats:
        def request(self, method, path):
            return 503, "Docker stats unavailable"

    monkeypatch.setattr(docker_helper, "get_docker_client", lambda: UnavailableDockerStats())
    with pytest.raises(RuntimeError, match="returned HTTP 503"):
        ResourceMonitor(nodes=["node1"])._get_container_metrics("node1")


def test_network_simulated_failures_are_counted_as_requests(monkeypatch):
    simulator = NetworkSimulator(nodes=["node1:2661"])
    simulator.simulate_network_conditions("packet_loss", {"loss_rate": 100})
    monkeypatch.setattr("docker.stress.test_network_simulation.random.randint", lambda *_: 1)
    simulator._send_request("node1")
    assert simulator.results.total_requests == 1
    assert simulator.results.failed_requests == 1
    assert simulator.results.successful_requests == 0

    tester = NetworkStressTester(nodes=["node1:2661"])
    tester.packet_loss_rate = 100
    tester._send_request("node1")
    assert tester.results.total_requests == 1
    assert tester.results.failed_requests == 1
    assert tester.results.successful_requests == 0


def test_docker_cpu_limit_uses_nano_cpus(monkeypatch):
    client = docker_helper.DockerSocketClient(socket_path="unused")
    calls = []

    def request(method, path, body=None):
        calls.append((method, path, body))
        return 200, "{}"

    monkeypatch.setattr(client, "request", request)
    assert client.container_update("hierachain-node1", 0.1)
    assert calls == [(
        "POST",
        "/v1.41/containers/hierachain-node1/update",
        {"NanoCpus": 100_000_000},
    )]


def test_chaos_action_errors_fail_the_stress_test(monkeypatch):
    monkeypatch.setattr(chaos, "_is_k8s", lambda: False)
    monkeypatch.setitem(chaos.DOCKER_ACTIONS, "stop", lambda *_args, **_kwargs: ("", "Docker API rejected stop"))
    with pytest.raises(RuntimeError, match="Docker API rejected stop"):
        chaos._do("node1", "stop")


def test_docker_resource_stress_fails_instead_of_skipping_without_socket(monkeypatch):
    monkeypatch.setenv("HRC_STRESS_ENV", "docker")
    monkeypatch.setattr(resource_test_module.os.path, "exists", lambda _path: False)
    with pytest.raises(pytest.fail.Exception, match="requires the mounted Docker Engine socket"):
        resource_test_module.TestResourceMonitoring.setup.__wrapped__(resource_test_module.TestResourceMonitoring())
