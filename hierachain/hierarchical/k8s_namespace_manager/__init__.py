"""
K8s Namespace Manager package — Kubernetes namespace isolation for sub-chains.
"""

from hierachain.hierarchical.k8s_namespace_manager.manager import K8sNamespaceManager
from hierachain.hierarchical.k8s_namespace_manager.types import (
    DeploymentConfig,
    NamespaceInfo,
    NamespaceStatus,
)

__all__ = [
    "K8sNamespaceManager",
    "NamespaceStatus",
    "NamespaceInfo",
    "DeploymentConfig",
]
