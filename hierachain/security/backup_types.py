"""
Backup exception types for HieraChain Ledger.
"""


class BackupError(Exception):
    pass


class RestoreError(Exception):
    pass


class IntegrityError(Exception):
    pass


class ValidationError(Exception):
    pass
