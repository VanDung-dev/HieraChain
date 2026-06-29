"""
Merkle Tree implementation for HieraChain Ledger.

Provides Merkle Tree construction, hash computation, and standalone
picklable hash functions for multiprocessing support.
"""

import hashlib
import orjson
from typing import Any


def compute_hash_standalone(data_string: str) -> str:
    return hashlib.sha256(data_string.encode()).hexdigest()


def compute_leaves_from_events_standalone(events: list[dict[str, Any]]) -> list[str]:
    leaves = []
    for event in events:
        data_bytes = orjson.dumps(event, option=orjson.OPT_SORT_KEYS)
        leaves.append(hashlib.sha256(data_bytes).hexdigest())
    return leaves


def generate_hash(data: str | dict[str, Any]) -> str:
    if isinstance(data, dict):
        data_bytes = orjson.dumps(data, option=orjson.OPT_SORT_KEYS)
        return hashlib.sha256(data_bytes).hexdigest()
    else:
        return compute_hash_standalone(str(data))


class MerkleTree:
    __slots__ = ('leaves', 'root')

    def __init__(
        self,
        data_list: list[str | dict[str, Any]] | None = None,
        leaves: list[str] | None = None
    ):
        if leaves is not None:
            self.leaves = leaves
        elif data_list is not None:
            self.leaves = [generate_hash(data) for data in data_list]
        else:
            self.leaves = []
        self.root = self._build_tree(self.leaves)

    @staticmethod
    def _build_tree(nodes: list[str]) -> str:
        if not nodes:
            return hashlib.sha256(b"").hexdigest()
        
        current_level = nodes
        while len(current_level) > 1:
            new_level = []
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                right = current_level[i+1] if i+1 < len(current_level) else left
                combined = left + right
                new_level.append(hashlib.sha256(combined.encode()).hexdigest())
            current_level = new_level
            
        return current_level[0]

    def get_root(self) -> str:
        return self.root
