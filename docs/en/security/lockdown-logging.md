---
title: "Secure Logging"
description: "Structured JSON logging, sanitization and sensitive-field redaction."
icon: material/lock-alert
---

# Secure logging

`SecureLogger` in `hierachain/security/secure_logging.py` writes structured JSON logs for security-sensitive operations. It sanitizes strings and masks sensitive named fields, including nested data. Separate logger instances let applications configure handlers and levels per module.

JSON structure alone does not detect record modification or deletion. `SecureLogger` has no hash chain, signature or trusted manifest. Centralized logging and retention controls belong to the deployment's logging system.

For audit verification, use the separate `AuditLogger` and its trusted manifest workflow described in [Risk management](../modules/risk-management.md). Keep that manifest independently of the log being verified.

## Related

* [Input sanitization](./risk-analyzer.md)
* [Security module](../modules/security.md)
