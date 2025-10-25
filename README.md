# Hierarchical-blockchain

A hierarchical blockchain framework inspired by Hyperledger Fabric architecture, designed for enterprise applications with a focus on business operations rather than cryptocurrency.

## License

This project is licensed under the Apache License, Version 2.0 - see the [LICENSE](LICENSE) file for details.

## Installation

```bash
pip install -r requirements.txt
```

## Running server

```bash
python api/server.py
```

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

## Static Analysis

- To run static code analysis:
    ```bash
    python testing/static_analysis.py
    ```

- To run static code analysis with text output:
    ```bash
    python testing/static_analysis.py --format text
    ```

- To run static code analysis and save results to a file:
    ```bash
    python testing/static_analysis.py --output analysis_report.json
    python testing/static_analysis.py --format text --output analysis_report.txt
    ```

## Automated Tests

- To run automated risk management tests:
    ```bash
    python testing/automated_tests.py
    ```

  - To run with verbose output:
      ```bash
      python testing/automated_tests.py -v
      ```

- To run automated recovery tests:
    ```bash
    python testing/recovery_tests.py
    ```

- To run priority-based validation tests:
    ```bash
    python testing/validation_suites.py
    ```