"""Capacity and rotation advice must not claim completed operational actions."""

import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from hierachain.core.parquet_log import read_parquet_log
from hierachain.error_mitigation import (
    ConsensusValidator,
    EncryptionValidator,
    ResourceValidator,
    ValidationError,
)
from hierachain.serialization import loads_json


@pytest.mark.parametrize("healthy_count", [0, 3, 4])
def test_node_health_advice_preserves_membership_and_quorum(
    healthy_count: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("hierachain.error_mitigation.consensus_validator.time.time", lambda: 100.0)
    nodes = [SimpleNamespace(health_status="active", last_heartbeat=100.0) for _ in range(healthy_count)]
    if healthy_count == 3:
        nodes.append(SimpleNamespace(health_status="active", last_heartbeat=70.0))
    original = list(nodes)
    validator = ConsensusValidator({"f": 1})
    with caplog.at_level(logging.INFO):
        healthy = validator.monitor_and_scale(nodes)
        if healthy_count < 4:
            with pytest.raises(ValidationError):
                validator.validate_node_count(healthy)
        else:
            assert validator.validate_node_count(healthy)
    assert healthy == original[:healthy_count]
    assert nodes == original
    rows = read_parquet_log("log/error_mitigation/consensus_scaling.parquet").to_pylist()
    assert len(rows) == int(healthy_count < 4)
    if rows:
        record = loads_json(rows[0]["data"])
        assert record["event"] == record["payload"]["event"] == "consensus_capacity_recommendation"
        assert record["payload"]["healthy_nodes_count"] == healthy_count
        assert record["payload"]["required_nodes"] == 4
    assert "Auto-scaling initiated" not in caplog.text
    assert "auto_scaling_triggered" not in caplog.text


@pytest.mark.parametrize("auto_scale", [False, True])
@pytest.mark.parametrize("above_threshold", [False, True])
def test_resource_advice_preserves_thresholds_and_legacy_flag(
    auto_scale: bool, above_threshold: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cpu, memory, disk = (71, 81, 86) if above_threshold else (70, 80, 85)
    monkeypatch.setattr("psutil.cpu_percent", lambda interval: cpu)
    monkeypatch.setattr("psutil.virtual_memory", lambda: SimpleNamespace(percent=memory))
    monkeypatch.setattr("psutil.disk_usage", lambda path: SimpleNamespace(used=disk, total=100))
    config = {"auto_scale": auto_scale}
    status = ResourceValidator(config).validate_resources()
    assert config == {"auto_scale": auto_scale}
    assert (status["cpu_percent"], status["memory_percent"], status["disk_percent"]) == (cpu, memory, disk)
    assert status["violations"] == ([
        "CPU usage 71.0% > 70%", "Memory usage 81.0% > 80%", "Disk usage 86.0% > 85%",
    ] if above_threshold else [])
    rows = read_parquet_log("log/error_mitigation/resource_scaling.parquet").to_pylist()
    records = [loads_json(row["data"]) for row in rows]
    assert [record["resource_type"] for record in records] == (
        ["cpu", "memory"] if auto_scale and above_threshold else []
    )
    assert all(record["event"] == "resource_capacity_recommendation" for record in records)
    assert all(record["auto_scale_enabled"] is True for record in records)


@pytest.mark.parametrize("resource_type, label", [("cpu", "CPU"), ("memory", "Memory"), ("disk", "Disk")])
@pytest.mark.parametrize("delta", [-0.5, 0, 0.5])
def test_custom_resource_thresholds_are_independent_and_strict(
    resource_type: str, label: str, delta: float, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    thresholds = {"cpu": 20, "memory": 30, "disk": 40}
    usage = dict(thresholds)
    usage[resource_type] += delta
    monkeypatch.setattr("psutil.cpu_percent", lambda interval: usage["cpu"])
    monkeypatch.setattr("psutil.virtual_memory", lambda: SimpleNamespace(percent=usage["memory"]))
    monkeypatch.setattr("psutil.disk_usage", lambda path: SimpleNamespace(used=usage["disk"], total=100))
    config = {f"{resource}_threshold": threshold for resource, threshold in thresholds.items()}
    status = ResourceValidator({**config, "auto_scale": True}).validate_resources()
    assert status["violations"] == (
        [f"{label} usage {usage[resource_type]:.1f}% > {thresholds[resource_type]}%"] if delta > 0 else []
    )
    records = [loads_json(row["data"]) for row in read_parquet_log(
        "log/error_mitigation/resource_scaling.parquet",
    ).to_pylist()]
    assert [record["resource_type"] for record in records] == (
        [resource_type] if delta > 0 and resource_type != "disk" else []
    )


def test_resource_log_failure_preserves_error_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("psutil.cpu_percent", lambda interval: 71)
    monkeypatch.setattr("psutil.virtual_memory", lambda: SimpleNamespace(percent=81))
    monkeypatch.setattr("psutil.disk_usage", lambda path: SimpleNamespace(used=86, total=100))
    writer = Mock(side_effect=OSError("disk unavailable"))
    monkeypatch.setattr("hierachain.core.parquet_log.write_parquet_log", writer)
    assert ResourceValidator({"auto_scale": True}).validate_resources() == {
        "error": "disk unavailable", "violations": [],
    }
    assert writer.call_count == 1
    assert writer.call_args.args[1]["resource_type"] == "cpu"


def test_consensus_log_failure_does_not_discard_healthy_nodes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("hierachain.error_mitigation.consensus_validator.time.time", lambda: 100.0)
    monkeypatch.setattr("hierachain.core.parquet_log.write_parquet_log", Mock(side_effect=OSError("disk unavailable")))
    node = SimpleNamespace(health_status="active", last_heartbeat=100.0)
    failed = SimpleNamespace(health_status="failed", last_heartbeat=100.0)
    assert ConsensusValidator({"f": 1}).monitor_and_scale([node, failed]) == [node]
    assert "Failed to log capacity recommendation" in caplog.text


@pytest.mark.parametrize("interval", [0, 2592000, 2592001])
def test_rotation_validation_only_warns_and_does_not_schedule_or_resolve_keys(
    interval: int, caplog: pytest.LogCaptureFixture,
) -> None:
    resolver = Mock(side_effect=AssertionError("validation must not access keys"))
    config = {"algorithm": "AES-256-GCM", "key_id": "retained", "key_rotation_interval": interval}
    original = dict(config)
    with caplog.at_level(logging.INFO):
        assert EncryptionValidator(config, key_resolver=resolver).validate_config()
    resolver.assert_not_called()
    assert config == original
    assert ("rotation is managed by the host application" in caplog.text) == (interval < 2592000)
    assert "key_rotation_scheduled" not in caplog.text
    assert "next_rotation" not in caplog.text
