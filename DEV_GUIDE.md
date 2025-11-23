# Developer Guide

This guide contains all the information developers need to work with the Hierarchical Blockchain framework.

---

## Installation

### Prerequisites

- Python 3.10, 3.11, 3.12, or 3.13

### Quick Start

- Install the required dependencies:
    ```bash
    pip install -r requirements.txt
    ```

- Install the package:
    ```bash
    pip install -e .  # Development mode
    pip install .     # Production mode
    ```

This will set up your environment to work with the framework.

## Running server

```bash
python -m hierarchical_blockchain.api.server
```

---

## Using the package

After installation, you can import components from the package:

```python
from hierarchical_blockchain.core.block import Block
from hierarchical_blockchain.core.blockchain import Blockchain
```

---

## Running Demos

- Run the main framework demonstration:
    ```bash
    python demo/demo.py
    ```

- Run the key backup and recovery demonstration:
    ```bash
    python demo/demo_key_backup.py
    ```

-   Run the API demo:
    ```bash
    python demo/demo_api.py
    ```

---

## Running Tests

- To run all unit tests:
    ```bash
    python -m pytest tests/unit -v
    ```

- To run all integration tests:
    ```bash
    python -m pytest tests/integration -v
    ```

- To run all tests:
    ```bash
    python -m pytest tests -v
    ```

---

## Static Analysis

- To run static code analysis:
    ```bash
    python -m hierarchical_blockchain.testing.static_analysis
    ```

- To run static codeanalysis with text output:
    ```bash
    python -m hierarchical_blockchain.testing.static_analysis --format text
    ```

- To run static code analysis and save results to a file:
    ```bash
    python -m hierarchical_blockchain.testing.static_analysis --output analysis_report.json
    python -m hierarchical_blockchain.testing.static_analysis --format text --output analysis_report.txt
    ```

---

## Automated Tests

- To run automated risk management tests:
    ```bash
    python -m testing.automated_tests
    ```

  - To run with verbose output:
      ```bash
      python -m testing.automated_tests -v
      ```

- To run automated recovery tests:
    ```bash
    python -m testing.recovery_tests
    ```

- To run priority-based validation tests:
    ```bash
    python -m testing.validation_suites
    ```

- To run static analysis:
    ```bash
    python -m testing.static_analysis
    ```

  - To run static analysis with text output:
      ```bash
      python -m testing.static_analysis --format text
      ```

  - To run static analysis and save results to a file:
      ```bash
      python -m testing.static_analysis --output analysis_report.json
      python -m testing.static_analysis --format text --output analysis_report.txt
      ```

---