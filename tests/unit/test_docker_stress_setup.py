"""Regression checks for stress setup without touching a live cluster."""

import os
import shlex
import subprocess
import sys
from pathlib import Path

import orjson
import pytest

COMMON = Path(__file__).resolve().parents[2] / "docker/lib/common.sh"


def test_docker_stress_output_keeps_reports_and_hides_live_logs() -> None:
    source = COMMON.read_text(encoding="utf-8")
    command = source[source.index("pytest docker/stress/"):source.index('--junitxml=', source.index("pytest docker/stress/"))]
    assert "-v" in command
    assert "--log-cli-level" not in command
    assert "-o log_cli=false" in command
    assert "-o faulthandler_timeout=0" in command
    assert "--show-capture=no --tb=short" in command
    assert "--log-level=INFO" in command
    assert "--html=" in command


def test_wheel_build_discards_deleted_modules_and_rebuilds(tmp_path: Path) -> None:
    (tmp_path / "build/lib").mkdir(parents=True)
    (tmp_path / "build/lib/deleted.py").write_text("stale", encoding="utf-8")
    (tmp_path / "docker/dist").mkdir(parents=True)
    (tmp_path / "docker/dist/hierachain-old.whl").touch()
    (tmp_path / "hierachain").mkdir()
    source = tmp_path / "hierachain/kept.py"
    source.write_text("current", encoding="utf-8")
    uv = tmp_path / "uv"
    uv.write_text('#!/bin/sh\n[ "$1" = build ] || exit 1\ntouch docker/dist/hierachain-new.whl\n', encoding="utf-8")
    uv.chmod(0o700)
    result = subprocess.run(
        ["bash", "-c", f"source {shlex.quote(str(COMMON))}; build_wheel"],
        cwd=tmp_path, env={**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}"},
        capture_output=True, text=True, timeout=10, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "build").exists()
    assert not (tmp_path / "docker/dist/hierachain-old.whl").exists()
    assert (tmp_path / "docker/dist/hierachain-new.whl").exists()
    assert source.read_text(encoding="utf-8") == "current"


@pytest.mark.parametrize("key", [None, "", "   ", "test-credential"])
def test_stress_key_guard_reads_compose_config_without_exposing_key(tmp_path: Path, key: str | None) -> None:
    config = tmp_path / "compose.json"
    config.write_bytes(orjson.dumps({"services": {"stress-tester": {"environment": {"HRC_API_KEY": key}}}}))
    uv = tmp_path / "uv"
    uv.write_text(f'#!/bin/sh\nshift 3\nexec {shlex.quote(sys.executable)} "$@"\n', encoding="utf-8")
    uv.chmod(0o700)
    result = subprocess.run(
        ["bash", "-c", f"source {shlex.quote(str(COMMON))}; "
         f"compose() {{ cat {shlex.quote(str(config))}; }}; COMPOSE=compose; ensure_stress_api_key"],
        cwd=tmp_path, env={**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}"},
        capture_output=True, text=True, timeout=10, check=False,
    )
    assert (result.returncode == 0) == bool(key and key.strip())
    assert "test-credential" not in result.stdout + result.stderr
