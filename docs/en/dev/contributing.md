---
title: "Contributing Guide"
description: "Guide to contributing to HieraChain: Fork & Pull workflow, coding standards, testing, and code of conduct."
icon: material/account-group
---

# Contributing guide

!!! note "Note"
    This document is a detailed guide for developers. For a summary of contribution rules (original English), please see [CONTRIBUTING.md](https://github.com/VanDung-dev/HieraChain/blob/main/CONTRIBUTING.md).

Thank you for your interest in contributing to HieraChain! We welcome all contributions, from bug reports, feature suggestions, documentation improvements, to source code submissions.

## Contribution workflow

We use the standard Fork & Pull workflow:

1. Fork the project to your GitHub account.
2. Clone your fork to your local machine:

    ```bash
    git clone https://github.com/VanDung-dev/HieraChain.git
    cd HieraChain
    ```

3. Create a new Branch for your feature or bug fix:

    ```bash
    git checkout -b feature/your-feature-name
    # or
    git checkout -b fix/bug-to-fix
    ```

4. Make changes and Commit. We encourage following [Conventional Commits](https://www.conventionalcommits.org/):

    * `feat: ...`: New feature
    * `fix: ...`: Bug fix
    * `docs: ...`: Documentation changes
    * `style: ...`: Code formatting (no logic impact)
    * `refactor: ...`: Code restructuring
    * `test: ...`: Adding or modifying tests

5. Push the branch to your fork.
6. Create a Pull Request (PR) from your branch to the `main` branch of the original HieraChain repo.

## Development environment

To set up the environment, install dependencies, and run tests, please see the detailed guide at: [Installation](../getting-started/install.md) or [Testing](testing.md).

## Coding standards

* Follow PEP 8 standards.
* Ensure code passes static analysis checks in the `scripts/` directory.
* New code must have complete Type Hints (Python >= 3.10).

## Forbidden patterns

To ensure consistency and philosophy of HieraChain, developers must ABSOLUTELY NOT:

* ❌ Use cryptocurrency terminology: Do not use words like `transaction`, `mining`, `coin`, `token`, `wallet`, `address`, `amount`, `fee`. Instead, use `event`, `entity_id`, `details`.
* ❌ **Use `print()`**: Always use `logging.getLogger(__name__)`.
* ❌ Direct DB access: Do not directly call `sqlite3` or `redis` outside the `adapters/database/` directory.
* ❌ Skip Journal: Do not skip the `TransactionJournal` write step when setting up new ordering flows.
* ❌ Store secrets in code: Always use environment variables or Secret Manager.

## Testing

HieraChain maintains high standards for code quality. All contributions must pass automated tests.

### Test structure

* `tests/unit`: Unit tests, testing individual functions/classes.
* `tests/integration`: Integration tests, testing interactions between components.
* `tests/scenarios`: Scenario tests, simulating real business flows.

### Running tests

Run relevant test files sequentially using the repository environment:

```bash
.venv/bin/python -m pytest tests/unit/test_reported_issue_regressions.py -v
```

Choose the file covering your change. Avoid running the entire suite at once because tests can contend for shared resources.

To run specific parts or learn more, please see details at [Testing](testing.md).

### Contribution requirements

1. Write new tests: If you add a new feature, write corresponding test cases (typically in `tests/unit`).
2. Don't break existing tests: Ensure your code does not break existing tests.
3. Docs: Related docs must be updated and links must not be broken.

## Bug reports and suggestions

Use the Issues tab on GitHub to report bugs or request features.

When reporting a bug, please provide:

1. Detailed description of the bug.
2. Steps to reproduce.
3. Environment (OS, Python version, error logs...).

## Security policy

If you discover a security issue in HieraChain, please DO NOT report it through public Issues.

### Reporting process

Send a confidential security bug report through the [Security Advisories page](https://github.com/VanDung-dev/HieraChain/security). See GitHub's guide on [privately reporting a security vulnerability](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability).

### Handling process

Upon receiving a report, we will:

1. Confirm the issue and assess severity.
2. Develop a fix as soon as possible.
3. Release the fix and publish a security bulletin, including credit to the discoverer (if applicable).

### Security fix contributions

If you want to contribute a security fix, please coordinate through the Security Advisories process before creating a Pull Request to ensure user safety.

## Code of conduct

We are committed to building an open, friendly, and respectful environment. Please maintain a professional and courteous attitude in all interactions.
