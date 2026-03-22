# Contributing to HieraChain

Thank you for your interest in contributing to HieraChain! We welcome all contributions, from bug reports and feature suggestions to code submissions.

## 1. Contribution Workflow

We use the standard **Fork & Pull** workflow:

1. **Fork** the project to your GitHub account.
2. **Clone** the fork to your local machine:

    ```bash
    git clone https://github.com/VanDung-dev/HieraChain.git
    cd HieraChain
    ```

3. Create a new **Branch** for your feature or bug fix:

    ```bash
    git checkout -b feature/new-feature-name
    # or
    git checkout -b fix/bug-to-fix
    ```

4. Make changes and **Commit**. We encourage adhering to [Conventional Commits](https://www.conventionalcommits.org/):
    * `feat: ...`: New feature
    * `fix: ...`: Bug fix
    * `docs: ...`: Documentation changes
5. **Push** the branch to your fork.
6. Create a **Pull Request (PR)** from your branch to the `main` branch of HieraChain.

## 2. Development Environment

To set up the environment, install dependencies, and run tests, please see the detailed guide at:
👉 **[Developer Guide](../DEV_GUIDE.md)**

## 3. Coding Standards

* Adhere to **PEP 8** standards.
* Ensure code passes static analysis checks located in the `scripts/` directory.
* New code must have full Type Hints.

## 4. Testing

The HieraChain project maintains high standards for code quality. All contributions must pass automated tests.

### Test Structure

* `tests/unit`: Unit tests, focusing on individual functions and classes.
* `tests/integration`: Integration tests, checking interactions between components.
* `tests/scenarios`: Scenario tests, simulating real-world business flows.

### Running Tests

You can run all tests using the command:

```bash
python -m pytest tests -v
```

To run specific parts, please refer to the details in **[DEV_GUIDE.md](../DEV_GUIDE.md#running-tests)**.

### Contribution Requirements

1. **Write new tests**: If you add a new feature, write corresponding test cases in the appropriate directory (usually `tests/unit`).
2. **Do not break old tests**: Ensure your code does not cause errors in existing test cases.

## 5. Reporting Bugs and Suggestions

* Use the **Issues** tab to report bugs or request features.
* When reporting a bug, please provide:
    1. Detailed description of the error.
    2. Steps to reproduce.
    3. Environment (OS, Python version, error logs...).

## 6. Code of Conduct

We are committed to building an open, friendly, and respectful environment. Please maintain a professional and polite attitude in all interactions.

---
Thank you for your contribution!
