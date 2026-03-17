"""
Kubernetes Namespace Manager for HieraChain Sub-chain Isolation.

This module provides K8s namespace lifecycle management for isolating
sub-chains in separate Kubernetes namespaces, ensuring complete resource
and fault isolation between different hierarchical chain levels.
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable
from kubernetes import client, config


logger = logging.getLogger(__name__)


class NamespaceStatus(Enum):
    """Status of a K8s namespace."""
    UNKNOWN = "unknown"
    CREATING = "creating"
    ACTIVE = "active"
    TERMINATING = "terminating"
    FAILED = "failed"
    NOT_FOUND = "not_found"


@dataclass
class NamespaceInfo:
    """Information about a managed namespace."""
    name: str
    sub_chain_id: str
    status: NamespaceStatus = NamespaceStatus.UNKNOWN
    created_at: float = field(default_factory=time.time)
    labels: dict[str, str] = field(default_factory=dict)
    resource_quota: dict[str, str] = field(default_factory=dict)
    pod_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
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
    """Configuration for sub-chain deployment."""
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


def _prepare_namespace_labels(
    sub_chain_id: str, labels: dict[str, str] | None = None
) -> dict[str, str]:
    """Prepare default and custom labels for a namespace."""
    full_labels = {
        "app": "hierachain",
        "component": "subchain",
        "subchain-id": sub_chain_id,
        "managed-by": "hierachain-k8s-manager",
    }
    if labels:
        full_labels.update(labels)
    return full_labels


def _get_namespace_resources_mock(
    namespace_name: str, ns_info: NamespaceInfo
) -> dict[str, Any]:
    """Get mock resource information for a namespace."""
    return {
        "namespace": namespace_name,
        "status": ns_info.status.value,
        "pods": ns_info.pod_count,
        "resource_quota": ns_info.resource_quota,
    }


def _init_k8s_client_impl(manager: Any) -> bool:
    """Initialize Kubernetes client."""
    if manager.use_mock:
        logger.debug("Using mock K8s client")
        return True

    if client is None:
        logger.warning("kubernetes package not installed, using mock mode")
        manager.use_mock = True
        return True

    try:
        if manager.kubeconfig_path:
            config.load_kube_config(config_file=manager.kubeconfig_path)
        else:
            try:
                config.load_incluster_config()
            except config.ConfigException:
                config.load_kube_config()

        manager.k8s_client = client.CoreV1Api()
        manager.apps_client = client.AppsV1Api()
        logger.info("K8s client initialized successfully")
        return True
    except ImportError:
        logger.warning("kubernetes package not installed, using mock mode")
        manager.use_mock = True
        return True
    except Exception as e:
        logger.warning(
            "Failed to initialize K8s client (%s), falling back to mock mode", e
        )
        manager.use_mock = True
        manager.stats["errors"] += 1
        return True


def _create_namespace_real_impl(
    manager: Any,
    name: str,
    labels: dict[str, str],
    ns_info: NamespaceInfo,
) -> bool:
    """Create a K8s namespace."""
    k8s = manager.k8s_client
    assert k8s is not None
    try:
        manifest = client.V1Namespace(
            metadata=client.V1ObjectMeta(name=name, labels=labels)
        )
        k8s.create_namespace(body=manifest)
        manager.record_namespace_active(name, ns_info)
        logger.info(f"Created K8s namespace: {name}")
        return True
    except (ImportError, RuntimeError, ValueError) as e:
        logger.error(f"Failed to create namespace {name}: {e}")
        ns_info.status = NamespaceStatus.FAILED
        manager.namespaces[name] = ns_info
        manager.stats["errors"] += 1
        return False
    except Exception as e:
        logger.error(f"Unexpected error creating namespace {name}: {e}")
        manager.stats["errors"] += 1
        return False


def _delete_namespace_real_impl(manager: Any, name: str) -> bool:
    """Delete a K8s namespace."""
    k8s = manager.k8s_client
    assert k8s is not None
    try:
        k8s.delete_namespace(name=name)
        manager.delete_namespace_local(name)
        logger.info("Deleted K8s namespace: %s", name)
        return True
    except (RuntimeError, ValueError) as e:
        logger.error("Failed to delete namespace %s: %s", name, e)
        manager.stats["errors"] += 1
        return False
    except Exception as e:
        logger.error("Unexpected error deleting namespace %s: %s", name, e)
        manager.stats["errors"] += 1
        return False


def _get_k8s_status_real_impl(manager: Any, name: str) -> NamespaceStatus:
    """Get official K8s namespace status."""
    k8s = manager.k8s_client
    assert k8s is not None
    try:
        ns = k8s.read_namespace(name=name)
        phase = ns.status.phase

        status_map = {
            "Active": NamespaceStatus.ACTIVE,
            "Terminating": NamespaceStatus.TERMINATING,
        }
        status = status_map.get(phase, NamespaceStatus.UNKNOWN)
        manager.namespaces[name].status = status
        return status
    except (RuntimeError, ValueError) as e:
        logger.error("Failed to get namespace status for %s: %s", name, e)
        return NamespaceStatus.UNKNOWN
    except Exception as e:
        logger.error("Unexpected error getting status for %s: %s", name, e)
        return NamespaceStatus.UNKNOWN


def _get_k8s_resources_real_impl(
    manager: Any,
    namespace_name: str,
    ns_info: NamespaceInfo,
) -> dict[str, Any]:
    """Get real resource information for a namespace."""
    k8s = manager.k8s_client
    assert k8s is not None
    try:
        pods = k8s.list_namespaced_pod(namespace=namespace_name)
        ns_info.pod_count = len(pods.items)

        quotas = k8s.list_namespaced_resource_quota(namespace=namespace_name)

        resource_quotas = []
        if quotas.items:
            resource_quotas = [q.spec.hard for q in quotas.items]

        return {
            "namespace": namespace_name,
            "status": ns_info.status.value,
            "pods": ns_info.pod_count,
            "resource_quotas": resource_quotas,
        }
    except (RuntimeError, ValueError) as e:
        logger.error(f"Failed to get namespace resources: {e}")
        return {"error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error getting namespace resources: {e}")
        return {"error": str(e)}


def _provision_sub_chain_deployment_impl(
    manager: Any, deploy_config: DeploymentConfig
) -> bool:
    """Provision a sub-chain deployment in the namespace."""
    namespace_name = manager.get_namespace_name(deploy_config.sub_chain_id)

    if namespace_name not in manager.namespaces:
        logger.error("Namespace %s does not exist, create it first", namespace_name)
        return False

    if manager.use_mock:
        manager.namespaces[namespace_name].pod_count = deploy_config.replicas
        manager.stats["deployments_created"] += 1
        logger.info("[MOCK] Created deployment in %s", namespace_name)
        return True

    if not manager.apps_client and not manager.init_k8s_client():
        return False

    if manager.use_mock:
        manager.namespaces[namespace_name].pod_count = deploy_config.replicas
        manager.stats["deployments_created"] += 1
        logger.info("[MOCK] Created deployment (fallback) in %s", namespace_name)
        return True

    apps = manager.apps_client
    assert apps is not None
    try:
        container = client.V1Container(
            name="hierachain-node",
            image=deploy_config.image,
            ports=[
                client.V1ContainerPort(
                    container_port=deploy_config.node_port, name="node-port",
                ),
                client.V1ContainerPort(
                    container_port=deploy_config.api_port, name="api-port",
                ),
            ],
            command=[
                "hrc", "start", "--host", "0.0.0.0", "--port",
                str(deploy_config.api_port),
            ],
            env=[
                client.V1EnvVar(name="NODE_ID", value=deploy_config.sub_chain_id),
                client.V1EnvVar(
                    name="NODE_PORT", value=str(deploy_config.node_port),
                ),
                client.V1EnvVar(
                    name="PEERS", value=",".join(deploy_config.peers),
                ),
            ]
            + [
                client.V1EnvVar(name=k, value=v)
                for k, v in deploy_config.environment.items()
            ],
            resources=client.V1ResourceRequirements(
                limits={
                    "cpu": deploy_config.cpu_limit,
                    "memory": deploy_config.memory_limit,
                },
                requests={
                    "cpu": deploy_config.cpu_request,
                    "memory": deploy_config.memory_request,
                },
            ),
        )

        deployment = client.V1Deployment(
            metadata=client.V1ObjectMeta(
                name=f"hierachain-{deploy_config.sub_chain_id}",
                namespace=namespace_name,
                labels={
                    "app": "hierachain",
                    "subchain-id": deploy_config.sub_chain_id,
                },
            ),
            spec=client.V1DeploymentSpec(
                replicas=deploy_config.replicas,
                selector=client.V1LabelSelector(
                    match_labels={
                        "app": "hierachain",
                        "subchain-id": deploy_config.sub_chain_id,
                    }
                ),
                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(
                        labels={
                            "app": "hierachain",
                            "subchain-id": deploy_config.sub_chain_id,
                        }
                    ),
                    spec=client.V1PodSpec(containers=[container]),
                ),
            ),
        )

        apps.create_namespaced_deployment(
            namespace=namespace_name,
            body=deployment,
        )

        manager.namespaces[namespace_name].pod_count = deploy_config.replicas
        manager.stats["deployments_created"] += 1
        logger.info(
            "Created deployment %s in namespace %s",
            deploy_config.sub_chain_id, namespace_name
        )
        return True
    except (ImportError, RuntimeError, ValueError) as e:
        logger.error(
            "Failed to create deployment %s: %s",
            deploy_config.sub_chain_id, e
        )
        manager.stats["errors"] += 1
        return False
    except Exception as e:
        logger.error(
            "Unexpected error creating deployment %s: %s",
            deploy_config.sub_chain_id, e
        )
        manager.stats["errors"] += 1
        return False


class K8sNamespaceManager:
    """
    Manages Kubernetes namespaces for sub-chain isolation.

    Each sub-chain is deployed to a separate namespace for:
    - Complete resource isolation
    - Fault isolation (one sub-chain failure doesn't affect others)
    - Independent scaling and resource quotas
    - Easier monitoring and management
    """

    def __init__(
        self, prefix: str = "hrc-subchain-",
        kubeconfig_path: str = "", use_mock: bool = True
    ) -> None:
        """
        Initialize K8sNamespaceManager.

        Args:
            prefix: Namespace name prefix.
            kubeconfig_path: Path to kubeconfig file (empty for in-cluster).
            use_mock: Use mock mode (no real K8s calls).
        """
        self.prefix = prefix
        self.kubeconfig_path = kubeconfig_path
        self.use_mock = use_mock

        # Managed namespaces
        self.namespaces: dict[str, NamespaceInfo] = {}

        # K8s API client (lazy loaded)
        self.k8s_client = None
        self.apps_client = None

        # Callbacks
        self._on_namespace_created: Callable[[str], None] | None = None
        self._on_namespace_deleted: Callable[[str], None] | None = None

        # Stats
        self.stats = {
            "namespaces_created": 0,
            "namespaces_deleted": 0,
            "deployments_created": 0,
            "errors": 0,
        }

        logger.info("K8sNamespaceManager initialized (mock=%s)", use_mock)

    def get_namespace_name(self, sub_chain_id: str) -> str:
        """Generate namespace name from sub-chain ID."""
        safe_id = sub_chain_id.lower().replace("_", "-").replace(" ", "-")
        return f"{self.prefix}{safe_id}"

    def init_k8s_client(self) -> bool:
        """Initialize Kubernetes client."""
        return _init_k8s_client_impl(self)

    def _ensure_k8s_client(self) -> bool:
        """Ensure K8s client is initialized, fallback to mock if fails."""
        if self.k8s_client:
            return True
        return self.init_k8s_client() and not self.use_mock

    def record_namespace_active(self, name: str, ns_info: NamespaceInfo) -> None:
        """Record namespace as active in local state."""
        ns_info.status = NamespaceStatus.ACTIVE
        self.namespaces[name] = ns_info
        self.stats["namespaces_created"] += 1
        if self._on_namespace_created:
            self._on_namespace_created(name)

    def _create_namespace_mock(self, name: str, ns_info: NamespaceInfo) -> bool:
        """Handle namespace creation in mock mode."""
        self.record_namespace_active(name, ns_info)
        logger.info("[MOCK] Created namespace: %s", name)
        return True

    def _create_namespace_real(
        self, name: str, labels: dict[str, str], ns_info: NamespaceInfo
    ) -> bool:
        """Handle real K8s namespace creation."""
        return _create_namespace_real_impl(self, name, labels, ns_info)

    def delete_namespace_local(self, name: str) -> None:
        """Remove namespace record from local state."""
        if name in self.namespaces:
            del self.namespaces[name]
        self.stats["namespaces_deleted"] += 1
        if self._on_namespace_deleted:
            self._on_namespace_deleted(name)

    def _delete_namespace_mock(self, name: str) -> bool:
        """Handle namespace deletion in mock mode."""
        self.delete_namespace_local(name)
        logger.info("[MOCK] Deleted namespace: %s", name)
        return True

    def _delete_namespace_real(self, name: str) -> bool:
        """Handle real K8s namespace deletion."""
        return _delete_namespace_real_impl(self, name)

    def create_namespace(
        self, sub_chain_id: str, labels: dict[str, str] | None = None
    ) -> bool:
        """Create a new K8s namespace for a sub-chain."""
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
        """Delete a K8s namespace for a sub-chain."""
        namespace_name = self.get_namespace_name(sub_chain_id)

        if namespace_name not in self.namespaces:
            logger.warning("Namespace %s not found", namespace_name)
            return False

        self.namespaces[namespace_name].status = NamespaceStatus.TERMINATING

        if self.use_mock or not self._ensure_k8s_client():
            return self._delete_namespace_mock(namespace_name)

        return self._delete_namespace_real(namespace_name)

    def get_namespace_status(self, sub_chain_id: str) -> NamespaceStatus:
        """Get the status of a namespace."""
        namespace_name = self.get_namespace_name(sub_chain_id)

        if namespace_name not in self.namespaces:
            return NamespaceStatus.NOT_FOUND

        if self.use_mock or not self._ensure_k8s_client():
            return self.namespaces[namespace_name].status

        return self._get_k8s_status_real(namespace_name)

    def _get_k8s_status_real(self, name: str) -> NamespaceStatus:
        """Get official K8s namespace status."""
        return _get_k8s_status_real_impl(self, name)

    def get_namespace_resources(self, sub_chain_id: str) -> dict[str, Any]:
        """
        Get resource information for a namespace.

        Args:
            sub_chain_id: Unique identifier for the sub-chain.

        Returns:
            Dictionary with resource information.
        """
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
        """Get real K8s resource information for a namespace."""
        return _get_k8s_resources_real_impl(self, namespace_name, ns_info)

    def provision_sub_chain_deployment(
        self, deploy_config: DeploymentConfig
    ) -> bool:
        """
        Create a sub-chain node deployment in the namespace.

        Args:
            deploy_config: Deployment configuration.

        Returns:
            True if deployment was created successfully.
        """
        return _provision_sub_chain_deployment_impl(self, deploy_config)

    def list_managed_namespaces(self) -> list[NamespaceInfo]:
        """Get list of all managed namespaces."""
        return list(self.namespaces.values())

    def get_stats(self) -> dict[str, Any]:
        """Get manager statistics."""
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
        """Set callback functions for namespace events."""
        self._on_namespace_created = on_created
        self._on_namespace_deleted = on_deleted
