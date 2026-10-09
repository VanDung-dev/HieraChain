# HieraChain Docker and Kubernetes test infrastructure

This directory contains a four-node Compose cluster, isolated container tests,
a single-node ordering benchmark, and Kubernetes manifests. Run the commands
below from the repository root.

## File layout

| Path | Purpose |
| --- | --- |
| `docker-compose.yml` | Four nodes, one PostgreSQL service per node, Nginx gateway, Redis, and four IPFS peers |
| `docker-compose.test.yml` | Isolated runtime checks with PostgreSQL 16 |
| `docker-compose.benchmark.yml` | Signed-event ordering benchmark with PostgreSQL 16 |
| `docker-compose.k8s-stress.yml` | Host-side stress runner targeting Kubernetes NodePorts |
| `Dockerfile` | `source`, `test`, `benchmark`, and final `production` stages |
| `entrypoint.sh` | Environment initialization and optional WireGuard setup |
| `hierachain.sh`, `lib/common.sh` | Cluster setup, stress execution, and cleanup wrapper |
| `scripts/` | Identity generation, network delay rules, benchmark entry point, and chaos helpers |
| `tests/` | Deterministic container runtime tests |
| `stress/` | Network, resource, failure, and other stress tests |
| `ipfs/init.sh` | IPFS initialization for the private swarm |
| `k8s/` | Kustomize resources, stress Job, and additional deployment templates |
| `kind-config.yaml` | Separate Kind configuration; the wrapper does not create a Kind cluster |

## Prerequisites

Use Docker Engine, Docker Desktop, or OrbStack with Compose v2. The cluster
requires Linux containers with WireGuard support and the `NET_ADMIN` capability.
Its fixed bridge subnets must not overlap your existing networks:
`172.28.1.0/24`, `172.28.2.0/24`, `172.28.3.0/24`, `172.29.0.0/24`, and
`10.0.0.0/24`.

The wrapper also uses Bash, `uv`, OpenSSL, and `curl`. Prepare the repository
Python environment with `uv sync`. Run the wrapper as a regular user; it rejects
root and `sudo`. The images use Python 3.12.

The main Compose file requires an external API-key JSON file. Follow
[Secure deployment](../docs/en/how-to/secure-deployment.md) to provision the file
and a client key before setup. Set its absolute host path:

```bash
export HRC_API_KEYS_SOURCE_FILE="$HOME/.config/hierachain/api-keys.json"
```

The file must already exist and contain valid key metadata. Compose mounts it
read-only at `/run/secrets/hrc_api_keys` on every node. For stress tests, also set
`HRC_API_KEY` to a provisioned key with `chains`, `events`, and `proofs`
permissions. The default client header is `X-API-Key`.

## Four-node Docker cluster

### Fresh setup

`setup docker` recreates the test cluster. It overwrites node identities and
trusted block key maps, regenerates the IPFS swarm key, builds a wheel and image,
then removes existing Compose containers and volumes before starting services.
Use it for a fresh test environment where existing data can be discarded.

```bash
bash docker/hierachain.sh setup docker
```

The wrapper creates missing `.env` files from `docker/.env.HRC.example`. The
nodes use `HRC_ENV=product`, PostgreSQL, API-key authentication, and strict signed
P2P configuration. Rate limiting is disabled in this test cluster. The default
PostgreSQL credentials are test credentials, and the gateway serves HTTP.

Each node has its own PostgreSQL database and IPFS peer. WireGuard connects the
nodes at `10.200.1.1`, `10.200.2.1`, `10.200.3.1`, and `10.200.4.1`.
The US, EU, and Asia labels select `tc` delay rules within the local runtime;
they do not deploy nodes in different geographic regions.

| Endpoint | Access |
| --- | --- |
| Gateway API | `http://localhost:2660/api/` |
| Gateway liveness | `http://localhost:2660/gateway-health` |
| Node liveness through the gateway | `http://localhost:2660/api/ledger/health` |
| Node readiness through the gateway | `http://localhost:2660/api/ledger/ready` |
| Status page | `http://localhost:2660/<EXPLORER_TOKEN>/status` |
| PostgreSQL | Loopback ports `5432`, `5433`, `5434`, and `5435` |

The gateway binds to `127.0.0.1:2660`; node APIs listen on container port `2661`.
The setup summary prints the status-page token. The Compose file mounts
`status.html` but does not provide an `explorer.html` file for its explorer route.
Setup checks gateway and node liveness, and a failed final gateway check only
prints a message. A successful wrapper exit alone does not establish readiness
or cluster-wide consistency.

### Key persistence

The wrapper obtains the IPFS payload encryption key from the exported
`IPFS_ENCRYPTION_KEY`, then `.env`, then `docker/.env`, and finally
`docker/ipfs/encryption.key`. It creates the last file once if needed and reuses
it. The value must be 64 hexadecimal characters. Compose maps this host variable
to the nodes' `HRC_IPFS_ENCRYPTION_KEY`.

Keep the encryption key available when reusing data. `setup` resets the swarm
key and node identities, but it does not intentionally rotate the persisted
payload encryption key. Set `EXPLORER_TOKEN` in the calling environment if you
need a stable status-page path; otherwise the wrapper generates one.

### Stress tests

After setting `HRC_API_KEY` in your shell or the root `.env`, reuse the cluster:

```bash
bash docker/hierachain.sh stress docker --reuse

# Extend the configurable measurement windows.
bash docker/hierachain.sh stress docker --reuse --duration 60
```

The wrapper runs all of `docker/stress/` with `REAL_REQUESTS=true`. Docker stress
defaults to 15 seconds per network-condition, network-simulation, and
failure-scenario case. Tests with explicit measurement windows keep their own
durations; `--duration` is not a timeout for the whole suite.

The Docker runner checks that a client key is configured and performs an
authentication preflight against the targets before live tests run. The runner
mounts `/var/run/docker.sock`, and some scenarios alter running containers or
network conditions. Run the suite against an expendable test cluster.

Without `--reuse`, the Docker stress command generates fresh identities, builds
the image, removes containers and volumes, and starts a new cluster first.
Reports from the wrapper's Compose runner are written to:

```text
log/report/docker_stress_report.html
log/report/docker_stress_report.xml
```

### Direct Compose commands and cleanup

Direct Compose startup does not generate identities, peer environment files,
trusted key maps, or IPFS keys. First prepare them with the wrapper. To restart
that prepared environment, supply the same API-key source file,
`IPFS_ENCRYPTION_KEY`, and `EXPLORER_TOKEN` through your shell or `.env`:

```bash
docker compose --env-file .env -f docker/docker-compose.yml up -d

# Stop containers while retaining volumes.
docker compose --env-file .env -f docker/docker-compose.yml stop
```

A production image build also requires a current `hierachain-*.whl` under
`docker/dist/`. The wrapper builds it with `uv build --wheel -o docker/dist`
after removing stale build output and older wheels. The `test` and `benchmark`
stages install the source tree and do not require this prebuilt wheel.

To discard the cluster and its Docker volumes:

```bash
bash docker/hierachain.sh down docker
```

This calls Compose `down --remove-orphans -v`, deleting node data, PostgreSQL
data, and IPFS data volumes. Host files under `docker/nodes/`, `docker/ipfs/`,
and `log/` remain. The parsed `--force` flag does not control this behavior;
volume removal happens without it.

## Isolated container tests

Run the `test` image stage without starting the four-node cluster:

```bash
docker compose -f docker/docker-compose.test.yml \
  --profile docker-test run --build --rm docker-tests
```

The profile starts an isolated PostgreSQL 16 service and checks three things:
explicit test configuration and runtime directories, journal replay after abrupt
process exit, and PostgreSQL adapter connectivity to an empty ledger. Journal
fsync remains enabled. Authentication, P2P, IPFS, and rate limiting are disabled
for this profile.

The application limit defaults to 1 CPU and 1 GiB of memory. Override
`DOCKER_TEST_CPUS` and `DOCKER_TEST_MEMORY` when needed. Cleanup removes its
services and anonymous volumes:

```bash
docker compose -f docker/docker-compose.test.yml --profile docker-test down -v
```

## Ordering throughput benchmark

The benchmark requires a signing identity and matching trusted block key map.
The current Compose file does not mount them, and the benchmark script does not
create them. Running the unmodified file with `up` therefore fails during
`OrderingService` initialization.

Prepare a separate identity directory containing `identity.json` and
`trusted_block_keys.json`, following
[Quickstart](../docs/en/getting-started/quickstart.md). An existing generated
`docker/nodes/node1/` directory also contains these files. Do not regenerate
identities belonging to a running cluster just to run the benchmark.

Mount that directory to run the default workload of 5,000 signed events with a
batch size of 100:

```bash
export BENCHMARK_IDENTITY_DIR="/absolute/path/to/benchmark-identity"
docker compose -f docker/docker-compose.benchmark.yml run --build --rm \
  --volume "$BENCHMARK_IDENTITY_DIR:/app/config/identity:ro" \
  --env HRC_VALIDATOR_IDENTITY=/app/config/identity/identity.json \
  --env HRC_BLOCK_TRUSTED_KEYS_FILE=/app/config/identity/trusted_block_keys.json \
  throughput
```

Override the workload with:

```bash
BENCHMARK_EVENTS=20000 BENCHMARK_BATCH_SIZE=500 \
docker compose -f docker/docker-compose.benchmark.yml run --build --rm \
  --volume "$BENCHMARK_IDENTITY_DIR:/app/config/identity:ro" \
  --env HRC_VALIDATOR_IDENTITY=/app/config/identity/identity.json \
  --env HRC_BLOCK_TRUSTED_KEYS_FILE=/app/config/identity/trusted_block_keys.json \
  throughput
```

This measures one local `OrderingService` backed by PostgreSQL 16 and an
append-only journal with fsync enabled. It reports submitted, committed,
rejected, and unfinished event counts, committed events per second, and observed
submit-to-commit p95/p99 latency. Latency includes submission and draining delay.
The benchmark raises an error if rejected or unfinished events remain. It does
not measure four-node network consensus throughput.

The application limit defaults to 1 CPU and 1 GiB; override `BENCHMARK_CPUS` and
`BENCHMARK_MEMORY` to change it. The JSON result is printed to the container log
and written to `/app/log/benchmark_debug.log`. `/app/data` and `/app/log` use
anonymous volumes, so retain any results you need before removing them:

```bash
docker compose -f docker/docker-compose.benchmark.yml down -v
```

## Kubernetes assets and current limitations

The wrapper's `k8s` mode targets an existing local Kubernetes environment. It
uses the current `kubectl` context and assumes the gateway NodePort is reachable
at `localhost:32660`. Its host-side stress fallback explicitly uses the Docker
context `orbstack`. It does not create a Kubernetes cluster or publish/load the
locally built `hierachain:latest` image into another cluster.

The Kustomize resource set declares four node pods with SQLite and data PVCs,
four IPFS pods, Redis, and an Nginx gateway. Its ConfigMap selects
`HRC_ENV=test` and disables authentication. The gateway NodePort is `32660` and
the node API NodePort is `32661`. This differs from the PostgreSQL-backed
product-mode Compose cluster.

The following gaps need to be fixed before treating this path as a working
setup and stress workflow:

- Nodes require `/app/config/identity/trusted_block_keys.json`, but the identity
  init container copies only the node identity and generates `peers.env`. The
  setup wrapper's identity Secret also omits the trusted block key maps.
- The in-cluster stress Job calls `uv run pytest ... --timeout=...`. The final
  production image installs neither `uv` nor `pytest-timeout`. Its script also
  does not generate the HTML report that the wrapper attempts to copy.
- `stress k8s` without `--reuse` deletes the namespace, but its subsequent
  `start_services` call does not reapply Kubernetes resources. The Job is tried
  only when the namespace exists; failure leads to the OrbStack Compose fallback.
- The standalone `docker-compose.k8s-stress.yml` targets
  `host.docker.internal:32661`; the wrapper fallback defaults to port `32660`.
  The fallback requires a host kubeconfig and reachable NodePort, does not inject
  `HRC_API_KEY`, and uses an image without `kubectl` for tests that need it.

The wrapper exposes `setup k8s`, `stress k8s --reuse`, and `down k8s`, but these
limitations prevent describing them as a ready-to-run EKS/GKE deployment.
`setup k8s` and `down k8s` delete the entire `hierachain` namespace, including
its PVCs; backing-volume retention depends on the cluster's reclaim policy.
Only resources listed in `k8s/kustomization.yaml` are applied during setup;
additional manifests and templates are not deployed automatically.
