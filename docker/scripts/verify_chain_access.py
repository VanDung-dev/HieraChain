import argparse
import json
import os
import secrets
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from generate_node_identities import generate_node_identity

REGRESSIONS = [
    "tests/unit/api/test_chain_access.py",
    "tests/unit/hierarchical/test_chain_access.py",
    "tests/unit/hierarchical/test_hierarchy_manager_feature_scope.py",
    "tests/unit/hierarchical/test_hierarchy_manager_recovery.py",
    "tests/unit/api/test_graphql.py",
    "tests/unit/api/test_graphql_event_queries.py",
    "tests/unit/api/test_api_transport_scopes.py",
    "tests/unit/api/test_websocket.py",
    "tests/unit/api/test_api_regressions.py",
    "tests/unit/api/test_ledger_events.py",
    "tests/unit/api/test_ledger_proofs.py",
    "tests/unit/api/test_admin_secure_event.py",
    "tests/unit/api/test_server.py",
    "tests/unit/api/test_hierarchy_lifespan.py",
    "tests/unit/api/test_graphql_security.py",
    "tests/unit/api/test_channel_event_submission.py",
    "tests/integration/api_business/test_api_business.py",
    "tests/integration/api_ledger/test_endpoints.py",
    "tests/integration/api_admin/test_internal_admin.py",
    "tests/integration/test_registry_multiworker.py",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--context")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    work = Path(tempfile.mkdtemp(prefix="hrc-chain-docker-"))
    source, config, reports = (work / name for name in ("source", "config", "reports"))
    for directory in (source, config, reports):
        directory.mkdir()
    config.chmod(0o700)
    records = {}
    for name, user, scopes in (
        ("platform", "platform", ["chains", "organizations:manage", "chains:manage"]),
        ("alice", "alice", ["chains", "events", "proofs"]),
        ("bob", "bob", ["chains", "events", "proofs"]),
        ("outsider", "outsider", ["all"]),
        ("reader", "alice", ["chains"]),
    ):
        records[secrets.token_urlsafe(32)] = {"user_id": user, "permissions": scopes, "app_details": {"name": name}}
    identity = generate_node_identity("chain-check", "Check-MSP")
    for name, value in (
        ("api-keys.json", records), ("identity.json", identity),
        ("trusted.json", {identity["node_id"]: identity["signing_public_key"]}),
    ):
        path = config / name
        path.write_text(json.dumps(value))
        path.chmod(0o600)
    files = subprocess.run(
        ["rtk", "proxy", "git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root, capture_output=True, check=True,
    ).stdout.decode().split("\0")
    for name in files:
        path = root / name
        if name and path.is_file():
            destination = source / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
    project = "hrc-chain-" + secrets.token_hex(5)
    env = {
        **os.environ,
        "SOURCE_DATE_EPOCH": subprocess.run(
            ["rtk", "proxy", "git", "show", "-s", "--format=%ct", "HEAD"],
            cwd=root, capture_output=True, text=True, check=True,
        ).stdout.strip(),
        "UV_CACHE_DIR": str(work / "uv-cache"),
        "BUILDX_CONFIG": str(work / "buildx"),
        "HRC_CHAIN_IMAGE": project + ":production",
        "HRC_CHAIN_TEST_IMAGE": project + ":test",
        "HRC_CHAIN_CONFIG": str(config),
        "HRC_CHAIN_REPORTS": str(reports),
        "HRC_CHAIN_PASSWORD": secrets.token_hex(24),
    }
    docker = ["rtk", "docker"]
    if args.context:
        docker += ["--context", args.context]
    compose = docker + ["compose", "-p", project, "-f", str(source / "docker/docker-compose.chain-access.yml")]
    sequence = 0

    def run(label: str, command: list[str], timeout: int = 180) -> None:
        nonlocal sequence
        sequence += 1
        logfile = reports / f"{sequence:02}-{label}.log"
        print(label, flush=True)
        started = time.monotonic()
        with logfile.open("w") as output:
            result = subprocess.run(command, cwd=source, env=env, stdout=output, stderr=subprocess.STDOUT,
                                    timeout=timeout, check=False)
        print(f"{label}: exit={result.returncode}, seconds={time.monotonic() - started:.1f}", flush=True)
        if result.returncode:
            print("\n".join(logfile.read_text().splitlines()[-65:]), flush=True)
            raise subprocess.CalledProcessError(result.returncode, [label])

    try:
        run("wheel", ["rtk", "uv", "build", "--wheel", "--out-dir", "docker/dist"])
        run("production-build", compose + ["build", "app-sqlite"], timeout=900)
        run("test-build", compose + ["build", "checks"], timeout=900)
        run("backends", compose + ["up", "-d", "--wait", "--wait-timeout", "90", "postgres", "redis"])
        postgres_url = f"postgresql://postgres:{env['HRC_CHAIN_PASSWORD']}@postgres:5432/hierachain"
        run("runtime", compose + ["run", "--rm", "-e", "HRC_STORAGE_BACKEND=postgres",
                                  "-e", "DATABASE_URL=" + postgres_url, "checks", "python", "-m", "pytest",
                                  "docker/tests/test_runtime.py", "-q", "--junitxml=/reports/runtime.xml"])
        regression_script = (
            "import subprocess,sys\n"
            f"files={REGRESSIONS!r}\n"
            "for name in files:\n"
            " result=subprocess.run([sys.executable,'-m','pytest',name,'-q','--tb=short','--fail-on-skip',"
            "'--junitxml=/reports/'+name.replace('/','_')+'.xml'],timeout=120)\n"
            " if result.returncode: sys.exit(result.returncode)\n"
        )
        apps = ["app-sqlite", "app-postgres", "app-redis"]
        run("applications", compose + ["up", "-d", "--wait", "--wait-timeout", "90", *apps])
        for phase in ("live_access", "recovered_access", "empty_policy_survives_recreation"):
            run(phase, compose + ["run", "--rm", "checks", "python", "-m", "pytest",
                                  f"docker/tests/live_chain_access.py::test_{phase}", "-q", "--tb=short",
                                  f"--junitxml=/reports/{phase}.xml"])
            if phase != "empty_policy_survives_recreation":
                run("stop-" + phase, compose + ["stop", *apps])
                run("recreate-" + phase, compose + ["up", "-d", "--force-recreate", "--wait",
                                                    "--wait-timeout", "90", *apps])
        run("regressions", compose + ["run", "--rm", "checks", "python", "-c", regression_script], timeout=300)
    finally:
        try:
            run("application-logs", compose + ["logs", "--no-color", "app-sqlite", "app-postgres", "app-redis"])
        finally:
            try:
                run("cleanup", compose + ["down", "--volumes", "--remove-orphans"], timeout=90)
            finally:
                shutil.rmtree(config)
                print("Reports:", reports, flush=True)


if __name__ == "__main__":
    main()
