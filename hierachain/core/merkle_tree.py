"""
Merkle Tree implementation for HieraChain Ledger.

Provides Merkle Tree construction, hash computation, and standalone
picklable hash functions for multiprocessing support.
"""

import hashlib
import json
from typing import Any


def compute_hash_standalone(data_string: str) -> str:
    return hashlib.sha256(data_string.encode()).hexdigest()


def compute_merkle_leaves_standalone(data_list_strings: list[str]) -> list[str]:
    return [hashlib.sha256(s.encode()).hexdigest() for s in data_list_strings]


def compute_leaves_from_events_standalone(events: list[dict[str, Any]]) -> list[str]:
    leaves = []
    for event in events:
        data_string = json.dumps(event, sort_keys=True, separators=(',', ':'))
        leaves.append(hashlib.sha256(data_string.encode()).hexdigest())
    return leaves


def generate_hash(data: str | dict[str, Any]) -> str:
    if isinstance(data, dict):
        data_string = json.dumps(data, sort_keys=True, separators=(',', ':'))
    else:
        data_string = str(data)
    return compute_hash_standalone(data_string)


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

    def _build_tree(self, nodes: list[str]) -> str:
        if not nodes:
            return hashlib.sha256(b"").hexdigest()
        if len(nodes) == 1:
            return nodes[0]
        new_level = []
        for i in range(0, len(nodes), 2):
            left = nodes[i]
            right = nodes[i+1] if i+1 < len(nodes) else left
            combined = left + right
            new_level.append(hashlib.sha256(combined.encode()).hexdigest())
        return self._build_tree(new_level)

    def get_root(self) -> str:
        return self.root
