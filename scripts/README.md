# HieraChain Development Scripts

This directory contains utility scripts for development, debugging, testing, and analysis of the HieraChain Ledger.

---

## Directory Structure

```
scripts/
├── benchmark_hashing.py         # Benchmark Merkle tree hashing performance
├── benchmark_throughput.py       # Benchmark OrderingService throughput
├── static_analysis.py            # Static code analysis (security, quality, compliance)
├── verify_storage.py             # Verify database storage persistence
├── sarif_analysis.py             # Parse and display SARIF analysis results
├── docker-stress-entrypoint.sh   # Docker entrypoint for stress testing
├── data/                        # Data directory for scripts
└── security/                    # Security probe scripts
    ├── base_probe.py            # Base class for security probes
    ├── auth_bypass_probe.py     # Test authentication bypass techniques
    ├── ssrf_probe.py            # Test Server-Side Request Forgery
    ├── path_traversal_probe.py  # Test path traversal attacks
    ├── stored_injection_probe.py # Test stored injection/XSS
    ├── input_fuzzer.py          # Fuzz API endpoints
    ├── http_headers_probe.py    # Test HTTP security headers
    ├── rate_limit_stress.py     # Test rate limiting
    ├── json_nested_bomb.py      # Test JSON parsing DoS
    ├── oversized_payload_probe.py # Test large payload handling
    ├── error_disclosure_verify.py # Test error message security
    ├── api_key_edge_cases_probe.py # Test API key edge cases
    ├── business_flow_sequence.py # Test business logic consistency
    ├── log_level_test.py        # Test log level behavior
    ├── slowloris_like_probe.py  # Test Slowloris DoS
    ├── chain_integrity_verify.py # Verify blockchain integrity
    └── signature_verify.py      # Verify signature validation
```

---

## Prerequisites

Before running scripts, ensure you have installed the package in development mode along with development dependencies:

```bash
pip install -e ".[dev]"
```

---

## Scripts Overview

### 1. Development & Debug Scripts

#### Benchmark Hashing
Tests Merkle tree hashing performance vs traditional JSON serialization:

```bash
python scripts/benchmark_hashing.py
```

**Output:**

* Block initialization time
* New method (Merkle) hash speed
* Old method (JSON) hash speed
* Speedup factor

#### Benchmark Throughput
Tests OrderingService event processing throughput:

```bash
python scripts/benchmark_throughput.py --events 1000 --workers 4 --batch-size 100
```

**Options:**

* `--events`: Number of events to submit (default: 1000)
* `--workers`: Number of worker threads (default: from settings)
* `--batch-size`: Events per block (default: 100)

#### Verify Storage
Verifies database persistence by saving blocks, closing backend, and re-opening:

```bash
python scripts/verify_storage.py
```

---

### 2. Static Analysis Scripts

#### Static Analysis
Performs static code analysis for security vulnerabilities, code quality, and compliance:

```bash
python scripts/static_analysis.py
python scripts/static_analysis.py hierachain -o report.json -f json
```

**Options:**

* `project_path`: Path to analyze (default: "hierachain")
* `-o, --output`: Output file path
* `-f, --format`: Output format (json or text)

**Analysis Types:**

* **Security**: Hardcoded secrets, SQL injection, insecure random, debug mode
* **Quality**: Long functions, too many parameters, missing docstrings
* **Compliance**: Crypto terminology (transaction, sender, receiver, etc.)
* **Dependencies**: Vulnerable package detection

#### SARIF Analysis
Parses SARIF (Static Analysis Results Interchange Format) files:

```bash
python scripts/sarif_analysis.py python.sarif
```

If no file is specified, defaults to `python.sarif`.

**Generate SARIF file:**
```bash
pylint hierachain --output-format=sarif > python.sarif
```

---

### 3. Security Probe Scripts

Security probes test the running API server for vulnerabilities. **Requires API server to be running**.

> ⚠️ **WARNING**: Only run security probes against local/isolated environments. Do not target external systems without permission.

#### Running Security Probes

All probes use the same interface:

```bash
python -m scripts.security.<probe_name> --base-url http://localhost:2661
```

**Common Options:**

* `--base-url`: Base URL of the API server (default: http://127.0.0.1:2661)
* `--api-key`: API key for authentication (optional)
* `--output`: Output file for JSON report (default: stdout)
* `--timeout`: Request timeout in seconds (default: 10)

#### Available Probes

| Probe | Description | Example |
|-------|-------------|---------|
| `auth_bypass_probe` | Test authentication bypass techniques | `python -m scripts.security.auth_bypass_probe` |
| `ssrf_probe` | Test Server-Side Request Forgery | `python -m scripts.security.ssrf_probe` |
| `path_traversal_probe` | Test path traversal attacks | `python -m scripts.security.path_traversal_probe` |
| `stored_injection_probe` | Test stored injection/XSS | `python -m scripts.security.stored_injection_probe` |
| `input_fuzzer` | Fuzz API endpoints | `python -m scripts.security.input_fuzzer` |
| `http_headers_probe` | Test HTTP security headers | `python -m scripts.security.http_headers_probe` |
| `rate_limit_stress` | Test rate limiting | `python -m scripts.security.rate_limit_stress --count 100` |
| `json_nested_bomb` | Test JSON parsing DoS | `python -m scripts.security.json_nested_bomb` |
| `oversized_payload_probe` | Test large payload handling | `python -m scripts.security.oversized_payload_probe` |
| `error_disclosure_verify` | Test error message security | `python -m scripts.security.error_disclosure_verify` |
| `api_key_edge_cases_probe` | Test API key edge cases | `python -m scripts.security.api_key_edge_cases_probe` |
| `business_flow_sequence` | Test business logic | `python -m scripts.security.business_flow_sequence` |
| `log_level_test` | Test log level behavior | `python -m scripts.security.log_level_test` |
| `slowloris_like_probe` | Test Slowloris DoS | `python -m scripts.security.slowloris_like_probe` |

#### Chain Integrity Verify
Verifies blockchain integrity in the database:

```bash
python -m scripts.security.chain_integrity_verify
python -m scripts.security.chain_integrity_verify --db sqlite:///hierachain.db
```

---

### 4. Docker Support

#### Docker Stress Entrypoint
The `docker-stress-entrypoint.sh` script is used as an entrypoint for Docker stress testing. It:

* Patches kubeconfig for host networking
* Handles network routing for Docker/Kubernetes

See [`docker/README.md`](../docker/README.md) for stress testing with Docker.

---

## Quick Reference

| Task | Command |
|------|---------|
| Run hashing benchmark | `python scripts/benchmark_hashing.py` |
| Run throughput benchmark | `python scripts/benchmark_throughput.py --events 1000` |
| Verify storage | `python scripts/verify_storage.py` |
| Run static analysis | `python scripts/static_analysis.py` |
| Parse SARIF | `python scripts/sarif_analysis.py` |
| Run auth bypass probe | `python -m scripts.security.auth_bypass_probe` |
| Run SSRF probe | `python -m scripts.security.ssrf_probe` |
| Run all security probes | `for p in auth_bypass ssrf path_traversal; do python -m scripts.security.${p}_probe; done` |

---

## Notes

* **Security probes** require the API server to be running. They test runtime behavior, unlike unit tests which use mocks.
* **Static analysis** can be run without the full project being functional - it's meant for pre-commit checks.
* **Benchmarks** are for development/testing purposes - not production performance measurement.
* All scripts follow the project's coding conventions and **do not use cryptocurrency terminology** (transaction, sender, receiver, amount, wallet, etc.).

---

## Related Documentation

* **Tests**: See [`tests/README.md`](../tests/README.md) for automated test execution
* **Docker**: See [`docker/README.md`](../docker/README.md) for containerized testing
* **Development Guide**: See [`docs/DEV_GUIDE.md`](../docs/DEV_GUIDE.md) for full development guide