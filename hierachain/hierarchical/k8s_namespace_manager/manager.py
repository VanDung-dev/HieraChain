"""
K8sNamespaceManager — manages Kubernetes namespaces for sub-chain isolation.
"""

import logging
from typing import Any, Callable

from hierachain.hierarchical.k8s_namespace_manager.types import (
    DeploymentConfig,
    NamespaceInfo,
    NamespaceStatus,
)
from hierachain.hierarchical.k8s_namespace_manager.operations import (
    _create_namespace_real_impl,
    _delete_namespace_real_impl,
    _get_k8s_resources_real_impl,
    _get_k8s_status_real_impl,
    _get_namespace_resources_mock,
    _init_k8s_client_impl,
    _prepare_namespace_labels,
    _provision_sub_chain_deployment_impl,
)

logger = logging.getLogger(__name__)


class K8sNamespaceManager:
    def __init__(
        self, prefix: str = "hrc-subchain-",
        kubeconfig_path: str = "", use_mock: bool = True
    ):
        self.prefix = prefix
        self.kubeconfig_path = kubeconfig_path
        self.use_mock = use_mock

        self.namespaces: dict[str, NamespaceInfo] = {}

        self.k8s_client = None
        self.apps_client = None

        self._on_namespace_created: Callable[[str], None] | None = None
        self._on_namespace_deleted: Callable[[str], None] | None = None

        self.stats = {
            "namespaces_created": 0,
            "namespaces_deleted": 0,
            "deployments_created": 0,
            "errors": 0,
        }

        logger.info("K8sNamespaceManager initialized (mock=%s)", use_mock)

    def get_namespace_name(self, sub_chain_id: str) -> str:
        safe_id = sub_chain_id.lower().replace("_", "-").replace(" ", "-")
        return f"{self.prefix}{safe_id}"

    def init_k8s_client(self) -> bool:
        return _init_k8s_client_impl(self)

    def _ensure_k8s_client(self) -> bool:
        if self.k8s_client:
            return True
        return self.init_k8s_client() and not self.use_mock

    def record_namespace_active(self, name: str, ns_info: NamespaceInfo) -> None:
        ns_info.status = NamespaceStatus.ACTIVE
        self.namespaces[name] = ns_info
        self.stats["namespaces_created"] += 1
        if self._on_namespace_created:
            self._on_namespace_created(name)

    def _create_namespace_mock(self, name: str, ns_info: NamespaceInfo) -> bool:
        self.record_namespace_active(name, ns_info)
        logger.info("[MOCK] Created namespace: %s", name)
        return True

    def _create_namespace_real(
        self, name: str, labels: dict[str, str], ns_info: NamespaceInfo
    ) -> bool:
        return _create_namespace_real_impl(self, name, labels, ns_info)

    def delete_namespace_local(self, name: str) -> None:
        if name in self.namespaces:
            del self.namespaces[name]
        self.stats["namespaces_deleted"] += 1
        if self._on_namespace_deleted:
            self._on_namespace_deleted(name)

    def _delete_namespace_mock(self, name: str) -> bool:
        self.delete_namespace_local(name)
        logger.info("[MOCK] Deleted namespace: %s", name)
        return True

    def _delete_namespace_real(self, name: str) -> bool:
        return _delete_namespace_real_impl(self, name)

    def create_namespace(
        self, sub_chain_id: str, labels: dict[str, str] | None = None
    ) -> bool:
        namespace_name = self.get_namespace_name(sub_chain_id)

        if namespace_name in self.namespaces:
            logger.warning("Namespace %s already exists", namespace_name)
            return True

        ns_info = NamespaceInfo(
            name=namespace_name,
            sub_chain_id=sub_chain_id,
            status=NamespaceStatus.CREATING,
            labels=_prepare_namespace_labels(sub_chain_id, labels),
        )

        if self.use_mock or not self._ensure_k8s_client():
            return self._create_namespace_mock(namespace_name, ns_info)

        return self._create_namespace_real(namespace_name, ns_info.labels, ns_info)

    def delete_namespace(self, sub_chain_id: str) -> bool:
        namespace_name = self.get_namespace_name(sub_chain_id)

        if namespace_name not in self.namespaces:
            logger.warning("Namespace %s not found", namespace_name)
            return False

        self.namespaces[namespace_name].status = NamespaceStatus.TERMINATING

        if self.use_mock or not self._ensure_k8s_client():
            return self._delete_namespace_mock(namespace_name)

        return self._delete_namespace_real(namespace_name)

    def get_namespace_status(self, sub_chain_id: str) -> NamespaceStatus:
        namespace_name = self.get_namespace_name(sub_chain_id)

        if namespace_name not in self.namespaces:
            return NamespaceStatus.NOT_FOUND

        if self.use_mock or not self._ensure_k8s_client():
            return self.namespaces[namespace_name].status

        return self._get_k8s_status_real(namespace_name)

    def _get_k8s_status_real(self, name: str) -> NamespaceStatus:
        return _get_k8s_status_real_impl(self, name)

    def get_namespace_resources(self, sub_chain_id: str) -> dict[str, Any]:
        namespace_name = self.get_namespace_name(sub_chain_id)

        if namespace_name not in self.namespaces:
            return {"error": "Namespace not found"}

        ns_info = self.namespaces[namespace_name]

        if self.use_mock or not self._ensure_k8s_client():
            return _get_namespace_resources_mock(namespace_name, ns_info)

        return self._get_k8s_resources_real(namespace_name, ns_info)

    def _get_k8s_resources_real(
        self, namespace_name: str, ns_info: NamespaceInfo
    ) -> dict[str, Any]:
        return _get_k8s_resources_real_impl(self, namespace_name, ns_info)

    def provision_sub_chain_deployment(
        self, deploy_config: DeploymentConfig
    ) -> bool:
        return _provision_sub_chain_deployment_impl(self, deploy_config)

    def list_managed_namespaces(self) -> list[NamespaceInfo]:
        return list(self.namespaces.values())

    def get_stats(self) -> dict[str, Any]:
        return {
            **self.stats,
            "managed_namespaces": len(self.namespaces),
            "use_mock": self.use_mock,
        }

    def set_callbacks(
        self,
        on_created: Callable[[str], None] | None = None,
        on_deleted: Callable[[str], None] | None = None,
    ) -> None:
        self._on_namespace_created = on_created
        self._on_namespace_deleted = on_deleted
