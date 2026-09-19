---
title: "Secure Logging"
description: "Tamper-evident secure logging system."
icon: material/lock-alert
---

# Secure Logging

This security layer provides tamper-evident structured logs for security-sensitive operations.

## Secure Logging

**File**: `hierachain/security/secure_logging.py`

A logging system specifically designed for security:

*   **Tamper-evident**: Each log record has a strict structure, supporting detection of log deletion or modification.
*   **Structured Logs**: Logs are recorded in JSON format for easy integration with centralized monitoring systems (SIEM).
*   **Log Segmentation**: Sensitive modules (such as `security`, `consensus`) use separate `SecureLogger` instances with higher protection levels.

## Related

*   [Input sanitization](./risk-analyzer.md)
*   [Security module](../modules/security.md)
