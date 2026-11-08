"""
Error mitigation module for HieraChain Ledger.

This module provides transaction journaling for durability.
"""

from hierachain.error_mitigation.journal import TransactionJournal

__all__ = [
    "TransactionJournal",
]
