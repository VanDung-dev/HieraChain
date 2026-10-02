"""Offline checks for guards used by the live Docker stress tests."""

import json
from itertools import count
from unittest.mock import Mock

import pytest

import docker.stress.conftest as stress_conftest
import docker.stress.docker_helper as docker_helper
import docker.stress.real_stress_client as real_client
import docker.stress.resource_monitoring as resource_monitoring
import docker.stress.test_bft_consensus as bft
import docker.stress.test_chaos as chaos
import docker.stress.test_resource_monitoring as resource_test_module
import docker.stress.test_websocket_load as websocket_test_module
from docker.stress.resource_monitoring import ResourceMonitor, ResourceStressTester
from docker.stress.test_network_conditions import NetworkStressTester
from docker.stress.test_network_simulation import NetworkSimulator
from docker.stress.test_poison_pill import PoisonPillTest
from docker.stress.test_tsunami_flood import TsunamiFloodTest


@pytest.mark.parametrize("method", ["test_poa_throughput_baseline", "test_events_per_block_ratio"])
def test_consensus_stress_requires_block_growth(monkeypatch: pytest.MonkeyPatch, method: str) -> None:
    from types import SimpleNamespace

    ticks = count()
    monkeypatch.setattr(bft, "time", SimpleNamespace(monotonic=lambda: next(ticks), sleep=Mock()))
    test = bft.TestBFTThroughput()
    test.client = Mock(node_status={"node1": SimpleNamespace(is_healthy=True, url="http://node1:2661")})
    test.client.submit_event.return_value = True
    test.client.session.get.return_value = Mock(
        status_code=200, json=lambda: {"total_blocks": 1, "total_events": 0},
    )
    with pytest.raises(AssertionError, match="produce committed blocks"):
        getattr(test, method)()


@pytest.mark.parametrize("drained", [False, True])
def test_consensus_throughput_waits_for_all_business_events(
    monkeypatch: pytest.MonkeyPatch, drained: bool,
) -> None:
    from types import SimpleNamespace

    now = [0.0]
    monkeypatch.setattr(bft, "time", SimpleNamespace(
        monotonic=lambda: now[0], sleep=lambda delay: now.__setitem__(0, now[0] + delay),
    ))
    test = bft.TestBFTThroughput()
    test.client = Mock(node_status={"node1": SimpleNamespace(url="http://node1:2661")})

    def stats() -> dict[str, int]:
        # One of two business events plus consensus metadata is insufficient.
        return {"total_blocks": 3, "total_events": 106 if drained and now[0] >= 2 else 105}

    test.client.session.get.return_value = Mock(status_code=200, json=stats)
    before = {"total_blocks": 2, "total_events": 103}
    if drained:
        assert test._wait_for_committed_events("node1", before, sent=2) == 1
        assert now[0] == 2
    else:
        with pytest.raises(AssertionError, match="Only 1/2 accepted events committed"):
            test._wait_for_committed_events("node1", before, sent=2)
        assert now[0] == 120


def test_consensus_stress_requires_restarted_primary_recovery(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import call

    test = bft.TestBFTViewChange()
    test.client = Mock()
    monkeypatch.setattr(test, "_find_healthy", lambda: ["node1", "node2", "node3"])
    monkeypatch.setattr(test, "_run_node_command", Mock())
    monkeypatch.setattr(test, "_poll_recovery", Mock(side_effect=[0.1, None]))
    with pytest.raises(AssertionError, match="Restarted primary must recover"):
        test.test_view_change_recovery_time()
    assert test._run_node_command.call_args_list == [call("node1", "stop"), call("node1", "start")]
    assert [call.args[0] for call in test._poll_recovery.call_args_list] == [["node2", "node3"], ["node1"]]
    test.client.wait_for_nodes.assert_not_called()


def test_consensus_recovery_checks_every_target_with_one_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    now = [0.0]
    monkeypatch.setattr(bft, "time", SimpleNamespace(
        monotonic=lambda: now[0], sleep=lambda delay: now.__setitem__(0, now[0] + delay),
    ))
    test = bft.TestBFTViewChange()
    test._check_node_recovered = Mock(side_effect=lambda node_id, _deadline: node_id == "node2")
    assert test._poll_recovery(["node2", "node1"], 0.0) is None
    assert now[0] == 60.0
    assert {call.args[0] for call in test._check_node_recovered.call_args_list} == {"node1", "node2"}
    assert {call.args[1] for call in test._check_node_recovered.call_args_list} == {60.0}


def test_consensus_recovery_requires_ledger_readiness_before_stats() -> None:
    test = bft.TestBFTViewChange()
    test.client = Mock()
    test.client.check_health.return_value = False
    assert not test._check_node_recovered("node1", bft.time.monotonic() + 60)
    test.client.session.get.assert_not_called()


@pytest.mark.parametrize("method", ["test_ipfs_event_stress", "test_ipfs_resolve_stress"])
def test_ipfs_setup_failure_stops_before_sending_events(monkeypatch: pytest.MonkeyPatch, method: str) -> None:
    monkeypatch.setenv("HRC_IPFS_ENABLED", "false")
    from docker.stress import test_ipfs_stress as ipfs

    client = Mock()
    client.wait_for_nodes.return_value = True
    client.create_chains_on_nodes.return_value = False
    monkeypatch.setattr(ipfs, "RealStressClient", lambda: client)
    monkeypatch.setattr(ipfs, "_preload_ipfs_data", lambda _count: [])
    with pytest.raises(AssertionError, match="prepare IPFS stress chain on all target nodes"):
        getattr(ipfs.TestIPFSStress(), method)()
    client.create_chains_on_nodes.assert_called_once_with(ipfs.CHAIN_NAME)
    client.session.post.assert_not_called()


def test_ipfs_event_uses_entity_id_directly_without_registration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HRC_IPFS_ENABLED", "false")
    from docker.stress import test_ipfs_stress as ipfs

    client = Mock()
    client.session.post.return_value = Mock(status_code=200, ok=True, json=lambda: {"success": True})
    ref = {"cid": "test-cid", "nonce": "test-nonce", "metadata": {}}
    result = ipfs.TestIPFSStress()._submit_ipfs_event("http://node1:2661", "new-entity", ref, client)
    assert result["status"] == 200
    client.session.post.assert_called_once()
    request = client.session.post.call_args
    assert request.args == (f"http://node1:2661/api/ledger/chains/{ipfs.CHAIN_NAME}/events",)
    assert request.kwargs["json"]["entity_id"] == "new-entity"
    assert request.kwargs["json"]["details_cid"] == ref["cid"]


@pytest.mark.parametrize("client_type", [real_client.RealStressClient, NetworkStressTester])
def test_stress_readiness_never_falls_back_to_liveness(client_type: type) -> None:
    client = client_type(nodes=["node1:2661"])
    client.node_status["node1"].is_healthy = True
    client.session.get = Mock(return_value=Mock(status_code=503, text="Recovery failed"))
    try:
        assert not client.check_health("node1")
        client.session.get.assert_called_once_with("http://node1:2661/api/ledger/ready", timeout=client.timeout)
        assert client.session.get_adapter("http://node1").max_retries.total == 0
    finally:
        client.session.close()


def test_node_wait_shares_one_deadline_and_clears_stale_health(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    now = [0.0]
    budgets = []
    client = real_client.RealStressClient(nodes=["node1:2661", "node2:2661", "node3:2661"])
    for status in client.node_status.values():
        status.is_healthy = True

    def stalled_get(_url: str, timeout: real_client.Timeout) -> None:
        budgets.append(timeout.total)
        now[0] += timeout.total
        raise real_client.requests.ReadTimeout("stalled")

    client.session.get = stalled_get
    monkeypatch.setattr(real_client, "time", SimpleNamespace(monotonic=lambda: now[0], sleep=Mock()))
    try:
        assert not client.wait_for_nodes(timeout=5)
        assert budgets == [3.0, 2.0]
        assert now[0] == 5.0
        assert not any(status.is_healthy for status in client.node_status.values())
        real_client.time.sleep.assert_not_called()
    finally:
        client.session.close()


@pytest.mark.parametrize("outcomes, expected", [([True, False], False), ([True, True], True)])
def test_chain_preparation_requires_every_target_node(outcomes: list[bool], expected: bool) -> None:
    client = real_client.RealStressClient(nodes=["node1:2661", "node2:2661"])
    client._try_create_chain_on_node = Mock(side_effect=outcomes)
    try:
        assert client.create_chains_on_nodes("custom-chain") is expected
        assert [call.args for call in client._try_create_chain_on_node.call_args_list] == [
            ("node1", "custom-chain"), ("node2", "custom-chain"),
        ]
        client.create_chain = Mock(return_value=False)
        client.verify_chain_exists = Mock(return_value=False)
        assert not real_client.RealStressClient._try_create_chain_on_node(client, "node1", "custom-chain")
        client.create_chain.assert_called_once_with("node1", "custom-chain")
        client.verify_chain_exists.assert_called_once_with("node1", "custom-chain")
    finally:
        client.session.close()


def test_poison_setup_reports_the_unwritable_node_without_random_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(real_client, "REAL_REQUESTS", True)
    test = PoisonPillTest({"chain_name": "custom-chain", "target_nodes": ["node1:2661", "node2:2661"]})
    test.client.session.close()
    test.client = Mock(node_status={"node1": object(), "node2": object()})
    test.client.submit_secure_event.return_value = False
    with pytest.raises(RuntimeError, match="not writable on node1"):
        test._ensure_nodes_ready()
    test.client.create_chains_on_nodes.assert_called_once_with("custom-chain")
    test.client.submit_secure_event.assert_called_once()
    assert test.client.submit_secure_event.call_args.kwargs["node_id"] == "node1"
    test.client.verify_chain_exists.assert_not_called()


def test_auth_preflight_requires_key_before_any_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HRC_API_KEY", raising=False)
    client = real_client.RealStressClient(nodes=["node1:2661"])
    client.session.get = Mock()
    with pytest.raises(RuntimeError, match="Set HRC_API_KEY"):
        client.preflight_auth()
    client.session.get.assert_not_called()
    client.session.close()


@pytest.mark.parametrize("timeout, attempts", [(None, 2), (0.01, 1)])
def test_event_timeout_budget_does_not_repeat_connection_attempts(timeout: float | None, attempts: int) -> None:
    client = real_client.RealStressClient(nodes=["node1:2661"])
    client.session.post = Mock(side_effect=real_client.requests.ConnectionError("offline"))
    assert not client.submit_event("node1", {}, timeout=timeout)
    assert client.session.post.call_count == attempts
    actual_timeout = client.session.post.call_args.kwargs["timeout"]
    if timeout is None:
        assert actual_timeout == client.timeout
    else:
        assert actual_timeout.total == timeout
    assert client.node_status["node1"].error_count == client.results.failed_requests == 1
    client.session.close()


@pytest.mark.parametrize("status_code", [401, 403, 429, 503])
def test_auth_preflight_aborts_on_first_rejection(
    monkeypatch: pytest.MonkeyPatch, status_code: int,
) -> None:
    monkeypatch.setenv("HRC_API_KEY", "test-credential")
    client = real_client.RealStressClient(nodes=["node1:2661", "node2:2661"])
    client.session.get = Mock(return_value=Mock(status_code=status_code))
    with pytest.raises(RuntimeError, match=f"HTTP {status_code}") as error:
        client.preflight_auth()
    assert "test-credential" not in str(error.value)
    client.session.get.assert_called_once_with("http://node1:2661/api/ledger/chains", timeout=client.timeout)


def test_auth_preflight_checks_all_nodes_and_handles_connection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HRC_API_KEY", "test-credential")
    client = real_client.RealStressClient(nodes=["gateway:80", "node1:2661", "node2:2661"])
    assert client.session.headers["X-API-Key"] == "test-credential"
    client.session.get = Mock(return_value=Mock(status_code=200))
    client.preflight_auth()
    assert [call.args[0] for call in client.session.get.call_args_list] == [
        "http://node1:2661/api/ledger/chains", "http://node2:2661/api/ledger/chains",
    ]
    client.session.get = Mock(side_effect=real_client.requests.ConnectionError())
    with pytest.raises(RuntimeError, match="could not reach"):
        client.preflight_auth()


def test_websocket_and_http_share_configured_auth_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HRC_API_KEY", "test-credential")
    monkeypatch.setenv("HRC_API_KEY_NAME", "Custom-Key")
    client = real_client.RealStressClient(nodes=["node1:2661"])
    assert client.session.headers["Custom-Key"] == "test-credential"
    calls = []

    class Socket:
        async def send(self, _message: str) -> None:
            pass

        async def close(self) -> None:
            pass

    async def connect(url: str, **kwargs: object) -> Socket:
        calls.append((url, kwargs))
        return Socket()

    monkeypatch.setattr(websocket_test_module.websockets, "connect", connect)
    tester = websocket_test_module.WebSocketLoadTest("http://node1:2661")
    try:
        assert tester.connect_sync(1, "stress_test")
        assert calls == [("ws://node1:2661/ws?chain_name=stress_test", {
            "open_timeout": 10, "additional_headers": {"Custom-Key": "test-credential"},
        })]
    finally:
        tester.cleanup()
        client.session.close()


def test_docker_session_preflight_fails_before_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    preflight = Mock(side_effect=RuntimeError("Authentication preflight failed: HTTP 403"))
    monkeypatch.setattr(real_client.RealStressClient, "preflight_auth", preflight)
    monkeypatch.setenv("REAL_REQUESTS", "true")
    monkeypatch.setenv("HRC_STRESS_ENV", "docker")
    with pytest.raises(pytest.UsageError, match="HTTP 403"):
        stress_conftest.pytest_sessionstart(Mock())
    preflight.assert_called_once()
    monkeypatch.setenv("REAL_REQUESTS", "false")
    stress_conftest.pytest_sessionstart(Mock())
    assert preflight.call_count == 1


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
