# Developer Guide

This guide contains all the information developers need to work with the HieraChain framework.

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
python -m hierachain.api.server
```

---

## Using the package

After installation, you can import components from the package:

```python
from hierachain.core.block import Block
from hierachain.core.blockchain import Blockchain
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

- Run the API demo:

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

- To run all scenario tests:
    ```bash
    python -m pytest tests/scenarios -v
    ```

- To run only benchmark tests:

    ```bash
    python -m pytest tests --benchmark-only -v --benchmark-save=benchmark_report
    python -m pytest tests --benchmark-only -v --benchmark-histogram=benchmark_report
    ```

- To run all tests:

    ```bash
    python -m pytest tests -v
    ```

    > **WARNING**: Running all tests (over 340 tests) simultaneously may cause failures due to resource constraints. I recommend to run tests by separate project directories to ensure accurate results.

---

## Static Analysis

- To run static code analysis:

    ```bash
    python -m scripts.static_analysis
    ```

- To run static code analysis with text output:

    ```bash
    python -m scripts.static_analysis --format text
    ```

- To run static code analysis and save results to a file:

    ```bash
    python -m scripts.static_analysis --output analysis_report.json
    python -m scripts.static_analysis --format text --output analysis_report.txt
    ```

---
