"""
Shared types for the K8s Namespace Manager package.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import time


class NamespaceStatus(Enum):
    UNKNOWN = "unknown"
    CREATING = "creating"
    ACTIVE = "active"
    TERMINATING = "terminating"
    FAILED = "failed"
    NOT_FOUND = "not_found"


@dataclass
class NamespaceInfo:
    name: str
    sub_chain_id: str
    status: NamespaceStatus = NamespaceStatus.UNKNOWN
    created_at: float = field(default_factory=time.time)
    labels: dict[str, str] = field(default_factory=dict)
    resource_quota: dict[str, str] = field(default_factory=dict)
    pod_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "sub_chain_id": self.sub_chain_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "labels": self.labels,
            "resource_quota": self.resource_quota,
            "pod_count": self.pod_count,
        }


@dataclass
class DeploymentConfig:
    sub_chain_id: str
    replicas: int = 1
    image: str = "hierachain:latest"
    cpu_limit: str = "1000m"
    memory_limit: str = "1Gi"
    cpu_request: str = "250m"
    memory_request: str = "256Mi"
    node_port: int = 5001
    api_port: int = 2661
    peers: list[str] = field(default_factory=list)
    environment: dict[str, str] = field(default_factory=dict)
