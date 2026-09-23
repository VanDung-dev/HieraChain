from types import SimpleNamespace

import docker.stress.test_failure_scenarios as failure_scenarios
import docker.stress.test_network_simulation as network_simulation


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
