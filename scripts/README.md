# HieraChain development scripts

These scripts measure local performance, inspect source code and SARIF reports,
and probe a running API. Run commands from the repository root. Security probes
write test data or generate load, so use an isolated local test environment.

## Layout

| Path | Purpose |
| --- | --- |
| `benchmark_hashing.py` | Compare block-header hashing with full-event JSON serialization |
| `benchmark_throughput.py` | Measure signed-event ordering throughput and observed commit latency |
| `static_analysis.py` | Custom regex/AST checks for security, quality, terminology, and dependencies |
| `sarif_analysis.py` | Display findings from an existing SARIF file |
| `verify_storage.py` | Persistence-check script with an unresolved backend import |
| `security/base_probe.py` | Common argument parser, headers, and JSON report helpers |
| `security/` | HTTP probes, a socket-based load probe, and two database audit scripts |

The Docker stress entrypoint is
[`docker/scripts/docker-stress-entrypoint.sh`](../docker/scripts/docker-stress-entrypoint.sh).
It is used by the Kubernetes Compose stress runner; see
[Docker infrastructure](../docker/README.md) for its workflow and limitations.

## Prepare the environment

Use the repository virtual environment and locked development dependencies:

```bash
uv sync --frozen --extra dev
source .venv/bin/activate
```

If `uv` is unavailable, install the development extra in a virtual environment:

```bash
python -m pip install -e ".[dev]"
```

Run modules with `python -m scripts.<name>`. This keeps repository imports
available; security probes also use relative imports and need module invocation.

## Hashing benchmark

```bash
python -m scripts.benchmark_hashing
```

The workload is fixed: 10,000 events, 1,000 calls to `Block.calculate_hash()`, and
10 calls that serialize the full event list to sorted JSON before hashing. The
script prints block initialization time, average time per call, and their timing
ratio. It has no CLI workload options.

Block-header hashing uses the Merkle root already computed during initialization.
The ratio compares repeated header hashing with full-event serialization; it
does not include rebuilding the Merkle tree on every call or establish overall
ledger throughput.

## Ordering throughput benchmark

The benchmark creates one local `OrderingService` and submits signed events.
It requires a fixed signing identity and a trusted public-key map containing
that identity. Provision these files as described in
[Quickstart](../docs/en/getting-started/quickstart.md).

Use a dedicated database, journal directory, and log file. The parent directory
for the log file must already exist:

```bash
mkdir -p log/report
export HRC_ENV=test
export HRC_VALIDATOR_IDENTITY="/absolute/path/to/identity.json"
export HRC_BLOCK_TRUSTED_KEYS_FILE="/absolute/path/to/trusted-block-keys.json"
export HRC_BENCHMARK_DB_URL="sqlite:///benchmark.sqlite"
export HRC_BENCHMARK_JOURNAL_DIR="benchmark-journal"
export HRC_BENCHMARK_LOG_FILE="log/report/benchmark.log"
python -m scripts.benchmark_throughput --events 1000 --batch-size 100
```

| Setting | Default |
| --- | --- |
| `--events` | `1000`; must be positive |
| `--batch-size` | `100`; must be positive |
| `HRC_BENCHMARK_DB_URL` | `hierachain.db` |
| `HRC_BENCHMARK_JOURNAL_DIR` | `journal` |
| `HRC_BENCHMARK_LOG_FILE` | `benchmark_debug.log` |

The CLI does not have a `--workers` option. Event generation and signing happen
before the timed submission loop. The result logs submitted, committed, rejected,
and unfinished event counts, committed events per second, and p95/p99 latency.
Latency measures submission to observed commit and includes submission/draining
delay. The batch timeout is 0.5 seconds; draining stops after completion,
rejection, or a 60-second measurement window. Rejected or unfinished events raise
an error. Journal fsync and storage adapter commit remain part of the path.

Relative journal paths are anchored under the working directory's `data/`:
the example uses `data/benchmark-journal`. Absolute journal paths must also stay
inside that `data/` directory. The database and journal persist after the run;
use a fresh pair when comparing independent workloads. Running the repository
tests removes `data/`, including journals created there. For a PostgreSQL-backed
container benchmark with explicit identity mounts, see the
[Docker README](../docker/README.md).

## Static analysis

```bash
python -m scripts.static_analysis

mkdir -p log/report
python -m scripts.static_analysis hierachain -o log/report/static-analysis.json -f json
python -m scripts.static_analysis hierachain -o log/report/static-analysis.txt -f text
```

The positional `project_path` defaults to `hierachain`. `-o`/`--output` writes the
report to a file; otherwise it prints to stdout. `-f`/`--format` accepts `json`
and `text`, with JSON as the default. Parent output directories are not created
by the script.

The analyzer scans Python files with its own regex and AST rules. It checks
patterns resembling hardcoded secrets, SQL injection, insecure randomness, and
debug mode; function length, parameter count, and docstrings; and project
terminology. It does not invoke Bandit or SonarQube.

Dependency checks only inspect pinned entries in `requirements*.txt` beneath
the selected directory against a small hardcoded version list. They do not scan
`uv.lock` or `pyproject.toml` or query an advisory service. Review findings in
context. The CLI exits with code 1 for critical findings or a top-level failure;
high-severity findings alone do not cause that exit code. A nonexistent scan
path can produce an empty report, so check the path before using the result.

## SARIF display

```bash
python -m scripts.sarif_analysis path/to/report.sarif
```

The optional positional path defaults to `python.sarif`. The script reads SARIF
JSON and prints the tool name, rule, severity, message, and first physical
location for each displayed finding. Entries without that location are omitted
from the displayed count.

Use a report produced by an analyzer that supports SARIF. This script does not
run an analyzer or convert another report format. A missing file prints an
informational message and exits successfully; invalid JSON exits with code 1.
Printed findings do not change its exit status.

## HTTP security probes

Start an isolated API with the configuration you intend to inspect. Supply a
provisioned API key with the permissions required by the chosen endpoint when
authentication is enabled. Probe headers use `X-API-Key`; the parser does not
load `HRC_API_KEY` automatically.

Inspect a probe's options before running it:

```bash
python -m scripts.security.http_headers_probe --help
```

For example, after setting `HRC_API_KEY` in your calling shell:

```bash
mkdir -p log/report
python -m scripts.security.http_headers_probe \
  --base-url http://127.0.0.1:2661 --api-key "$HRC_API_KEY" \
  --output log/report/http-headers.json
```

Most HTTP probes share these options from `base_probe.py`:

| Option | Behavior |
| --- | --- |
| `--base-url` | Defaults to `http://127.0.0.1:2661` |
| `--api-key` | Optional CLI value used in the `X-API-Key` header |
| `--output`, `-o` | JSON report file; defaults to stdout |
| `--timeout` | Request timeout in seconds; defaults to `10` |

BaseProbe reports contain `probe_type`, `base_url`, `timestamp`, summary counts,
and per-case results with status, elapsed time, findings, and errors. Progress
messages normally go to stderr. Create the output directory yourself.

| Module under `scripts.security` | Work performed |
| --- | --- |
| `auth_bypass_probe` | Missing/malformed keys, header variants, and query-string attempts |
| `api_key_edge_cases_probe` | Empty, oversized, Unicode, case-variant, and scope-related key inputs |
| `http_headers_probe` | Response security headers and CORS/cache observations |
| `error_disclosure_verify` | Error-response text checks for internal information |
| `log_level_test` | Error disclosure under the server's current log configuration |
| `path_traversal_probe` | Path traversal inputs to channel routes |
| `ssrf_probe` | URL-like contract metadata and timing/body heuristics |
| `stored_injection_probe` | Attempts to store and retrieve injection payloads |
| `input_fuzzer` | Injection patterns, malformed types, Unicode, and large/nested inputs |
| `business_flow_sequence` | Channel/private-collection workflow and missing-parent cases |
| `json_nested_bomb` | A depth-2,000 JSON object and a 100,000-item array |
| `oversized_payload_probe` | A fixed 10 MiB invalid-JSON body |
| `rate_limit_stress` | Concurrent requests to `/api/business/health` |
| `slowloris_like_probe` | Partial HTTP headers over raw sockets |

### Interface exceptions

`rate_limit_stress` uses its own parser. It supports `--output` without the `-o`
alias, and adds `--count` (default 200) and `--concurrency` (default 20):

```bash
python -m scripts.security.rate_limit_stress \
  --base-url http://127.0.0.1:2661 --count 100 --concurrency 10
```

`oversized_payload_probe` uses a fixed 30-second HTTP timeout despite accepting
`--timeout`. `slowloris_like_probe` accepts the common options but does not use
`--api-key` or `--timeout`: it opens up to five sockets with a fixed four-second
socket timeout and sends partial headers in five rounds separated by two
seconds. Its JSON report has a separate outcome-based structure.

`log_level_test` does not change the server's `LOG_LEVEL`. Restart the test server
with the desired setting and run the probe separately for each configuration.

### Interpret results

Probe findings are observations for review. These scripts generally catch
request errors and report findings without returning a failing process status.
An exit code of 0 or an empty report does not establish that a control passed.
Check the attempted endpoint, authentication, status code, and errors.

Several probes contain illustrative paths or payloads that can receive 404/422
responses before reaching the intended behavior. SSRF detection uses response
time and text heuristics without an external callback. Stored-injection probes
do not execute a browser renderer. Deep JSON serialization can fail on the
client before a request reaches the server.

The API deliberately exempts health endpoints from authentication and rate
limiting. `auth_bypass_probe` nevertheless interprets an unauthenticated health
response as authentication being disabled, and its query-string case can flag
that same public endpoint. `rate_limit_stress` targets the exempt business health
route, so a lack of 429 responses there does not establish broken rate limiting.
Review protected-route behavior separately.

## Database verification scripts

These three scripts currently import the absent
`hierachain.storage.sql_backend.SqlStorageBackend` and fail before their checks
or CLI help can run:

- `verify_storage.py`
- `security/chain_integrity_verify.py`
- `security/signature_verify.py`

Use the package CLI for persisted chain and signature verification instead.
Supply the operator-approved trusted block key map matching the stored creators:

```bash
export HRC_BLOCK_TRUSTED_KEYS_FILE="/absolute/path/to/trusted-block-keys.json"
hrc verify chain --db sqlite:///path/to/ledger.db
hrc verify signatures --db sqlite:///path/to/ledger.db --limit 100
```

The CLI also accepts PostgreSQL URLs. Signature auditing reports unsigned events
separately; their absence of a signature is not counted as a verified signature.
For adapter persistence and replay checks, use the relevant file in the
[tests README](../tests/README.md).

## Related documentation

- [Automated tests](../tests/README.md)
- [Docker infrastructure](../docker/README.md)
- [Development guide](../docs/DEV_GUIDE.md)
- [Secure deployment](../docs/en/how-to/secure-deployment.md)
