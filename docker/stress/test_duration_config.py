import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import docker.stress.test_failure_scenarios as failure_scenarios
import docker.stress.test_network_simulation as network_simulation
from docker.stress.test_tsunami_flood import TsunamiFloodTest


def test_network_simulation_uses_configured_duration(monkeypatch):
    observed_durations = []

    class StubSimulator:
        def __init__(self, nodes):
            pass

        def run_network_simulation_test(self, network_type, config, duration):
            observed_durations.append(duration)
            return SimpleNamespace(
                duration=duration,
                total_requests=1,
                successful_requests=1,
                failed_requests=0,
            )

        def print_results(self):
            pass

    monkeypatch.setattr(network_simulation, "TEST_DURATION", 7)
    monkeypatch.setattr(network_simulation, "NetworkSimulator", StubSimulator)

    network_simulation.test_network_simulation()

    assert observed_durations == [7] * 5


def test_failure_scenarios_use_configured_duration(monkeypatch):
    monkeypatch.setattr(failure_scenarios, "TEST_DURATION", 7)
    test_case = failure_scenarios.TestFailureScenarios()
    failure_scenarios.TestFailureScenarios.setup.__wrapped__(test_case)

    assert [scenario.config["duration"] for scenario in test_case.scenarios] == [7] * 5


def test_flood_deadline_stops_batches_and_joins_workers(monkeypatch: pytest.MonkeyPatch) -> None:
    flood = TsunamiFloodTest({
        "target_nodes": ["node1:2661"], "num_events": 20, "batch_size": 2,
        "event_size_bytes": 8, "concurrent_senders": 1, "timeout_seconds": 0.06,
    })
    monkeypatch.setattr(flood, "_ensure_nodes_ready", lambda: None)
    calls = []
    threads = set()

    def slow_request(node_id: str, event: dict, *, timeout: float) -> bool:
        calls.append(timeout)
        threads.add(threading.current_thread())
        time.sleep(min(0.02, timeout))
        return False

    monkeypatch.setattr(flood.client, "submit_event", slow_request)
    start = time.monotonic()
    result = flood.run_flood()
    assert time.monotonic() - start < 0.3
    assert result["status"] == "timed_out"
    assert result["unattempted_events"] > 0
    assert result["sent_failed"] == len(calls)
    assert result["sent_success"] + result["sent_failed"] + result["unattempted_events"] == 20
    assert calls and all(0 < timeout <= 0.06 for timeout in calls)
    assert all(not thread.is_alive() for thread in threads)
    assert flood.client.session.get_adapter("http://").max_retries.total == 0
    flood.client.session.close()


def test_flood_completed_workload_and_worker_error_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    flood = TsunamiFloodTest({"target_nodes": ["node1:2661"], "timeout_seconds": 1})
    monkeypatch.setattr(flood.client, "submit_event", Mock(return_value=True))
    flood._execute_batches([[{}, {}], [{}, {}]], 2, ["node1:2661"])
    result = flood._build_results(4, 0.1, ["node1:2661"], 2)
    assert result["status"] == "completed" and result["sent_success"] == 4
    assert result["sent_failed"] == result["unattempted_events"] == 0
    monkeypatch.setattr(flood.client, "submit_event", Mock(side_effect=ValueError("worker failure")))
    with pytest.raises(ValueError, match="worker failure"):
        flood._execute_batches([[{}]], 1, ["node1:2661"])
    assert flood._stop.is_set()
    flood.client.session.close()


def test_flood_deadline_bounds_a_stalled_http_response(monkeypatch: pytest.MonkeyPatch) -> None:
    release = threading.Event()

    class StalledResponse(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            release.wait(timeout=2)
            self.close_connection = True

        def log_message(self, _format: str, *_args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), StalledResponse)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
    thread.start()
    flood = TsunamiFloodTest({
        "target_nodes": [f"127.0.0.1:{server.server_port}"], "num_events": 20, "batch_size": 2,
        "event_size_bytes": 8, "concurrent_senders": 1, "timeout_seconds": 0.05,
    })
    monkeypatch.setattr(flood, "_ensure_nodes_ready", lambda: None)
    try:
        start = time.monotonic()
        result = flood.run_flood()
        assert time.monotonic() - start < 0.5
        assert result["status"] == "timed_out"
        assert result["sent_failed"] == 1
        assert result["unattempted_events"] == 19
    finally:
        flood.client.session.close()
        release.set()
        server.shutdown()
        thread.join()
        server.server_close()
