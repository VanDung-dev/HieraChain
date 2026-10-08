# Repository Guidelines

## Project Structure

- `hierachain/` contains the Python package. Runtime areas include `core/`, `hierarchical/`, `consensus/`, `state/`, `security/`, `network/`, `api/`, `sdk/`, `integration/`, and `adapters/`.
- `tests/unit/`, `tests/integration/`, and `tests/scenarios/` contain the pytest suites. Stress and deployment tests live under `docker/stress/`.
- `scripts/` provides static analysis, benchmarks, storage checks, and security probes. Documentation is split between `docs/en/` and `docs/vi/`; keep corresponding pages synchronized.
- `docker/` contains Compose and Kubernetes assets. Do not commit generated build, cache, log, database, or report files.

## Build, Test, and Development Commands

Use the repository environment whenever possible:

```bash
uv sync
source .venv/bin/activate
python -m pytest tests/unit/path/to/test_file.py -v
python -m scripts.static_analysis
python -m hierachain
```

`uv sync` installs the locked dependencies, the focused pytest command runs one test file, static analysis checks code quality and security, and `python -m hierachain` starts the API server locally. If `uv` is unavailable, install development dependencies with `python -m pip install -e ".[dev]"`.

## Coding Style and Naming

Follow PEP 8 with four-space indentation and the repository’s 120-character Flake8 limit. Add type hints to all function signatures. Use `snake_case` for modules, functions, and variables; `PascalCase` for classes; and `UPPER_CASE` for constants. Use logging instead of `print()` in library code, keep secrets in environment variables, and route persistence through storage adapters. Use domain terminology such as `event` and `entity_id`, not cryptocurrency terms.

## Testing Guidelines

Name tests `test_*.py` and test functions `test_*`; use pytest markers such as `integration`, `critical`, `slow`, and `security` where appropriate. Add regression coverage with each behavior change and prefer running tests per file to avoid resource contention. Run security probes only against an isolated local server.

## Commits and Pull Requests

Use Conventional Commit prefixes found in the history, such as `feat:`, `fix:`, `docs:`, `refactor:`, and `test:`. Keep commits focused. PRs should explain the change, list verification commands, note configuration or security impact, link an issue when applicable, and include synchronized English/Vietnamese documentation updates when behavior or user-facing APIs change.

## Repository Rules

Read the applicable files in `.agents/rules/` before changing terminology, architecture, changelogs, or documentation. Treat the implementation under `hierachain/` as the source of truth and never commit `.env` or credentials.
