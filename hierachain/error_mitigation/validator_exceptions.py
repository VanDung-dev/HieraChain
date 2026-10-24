"""
Validator exceptions for HieraChain Ledger.
"""

LOCALIZED_MESSAGES = {
    "default": "Unknown error occurred",
    "invalid_input": "Invalid input provided",
    "security_violation": "Security policy violation detected",
}


class ValidationError(Exception):
    def __init__(self, msg_code):
        self.message = LOCALIZED_MESSAGES.get(msg_code, 'Unknown error')
        super().__init__(self.message)


class SecurityError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message
