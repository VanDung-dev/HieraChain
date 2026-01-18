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
        self,
        prefix: str = "hrc-subchain-",
        kubeconfig_path: str = "",
        use_mock: bool = True,
    ):
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
        self._namespaces: dict[str, NamespaceInfo] = {}
        
        # K8s API client (lazy loaded)
        self._k8s_client = None
        self._apps_client = None
        
        # Callbacks
        self._on_namespace_created: Callable[[str], None] | None = None
        self._on_namespace_deleted: Callable[[str], None] | None = None
        
        # Stats
        self._stats = {
            "namespaces_created": 0,
            "namespaces_deleted": 0,
            "deployments_created": 0,
            "errors": 0,
        }
        
        logger.info(f"K8sNamespaceManager initialized (mock={use_mock})")
    
    def _get_namespace_name(self, sub_chain_id: str) -> str:
        """Generate namespace name from sub-chain ID."""
        # Sanitize sub_chain_id for K8s naming conventions
        safe_id = sub_chain_id.lower().replace("_", "-").replace(" ", "-")
        return f"{self.prefix}{safe_id}"
    
    def _init_k8s_client(self) -> bool:
        """Initialize Kubernetes client."""
        if self.use_mock:
            logger.debug("Using mock K8s client")
            return True
        
        try:
            from kubernetes import client, config
            
            if self.kubeconfig_path:
                config.load_kube_config(config_file=self.kubeconfig_path)
            else:
                # Try in-cluster config first, fall back to default kubeconfig
                try:
                    config.load_incluster_config()
                except config.ConfigException:
                    config.load_kube_config()
            
            self._k8s_client = client.CoreV1Api()
            self._apps_client = client.AppsV1Api()
            logger.info("K8s client initialized successfully")
            return True
        except ImportError:
            logger.warning("kubernetes package not installed, using mock mode")
            self.use_mock = True
            return True
        except Exception as e:
            logger.warning(f"Failed to initialize K8s client ({e}), falling back to mock mode")
            self.use_mock = True
            self._stats["errors"] += 1
            return True
    
    def create_namespace(self, sub_chain_id: str, labels: dict[str, str] | None = None) -> bool:
        """
        Create a new K8s namespace for a sub-chain.
        
        Args:
            sub_chain_id: Unique identifier for the sub-chain.
            labels: Additional labels for the namespace.
        
        Returns:
            True if namespace was created successfully.
        """
        namespace_name = self._get_namespace_name(sub_chain_id)
        
        if namespace_name in self._namespaces:
            logger.warning(f"Namespace {namespace_name} already exists")
            return True
        
        default_labels = {
            "app": "hierachain",
            "component": "subchain",
            "subchain-id": sub_chain_id,
            "managed-by": "hierachain-k8s-manager",
        }
        if labels:
            default_labels.update(labels)
        
        # Create namespace info
        ns_info = NamespaceInfo(
            name=namespace_name,
            sub_chain_id=sub_chain_id,
            status=NamespaceStatus.CREATING,
            labels=default_labels,
        )
        
        if self.use_mock:
            # Mock mode - just track locally
            ns_info.status = NamespaceStatus.ACTIVE
            self._namespaces[namespace_name] = ns_info
            self._stats["namespaces_created"] += 1
            logger.info(f"[MOCK] Created namespace: {namespace_name}")
            
            if self._on_namespace_created:
                self._on_namespace_created(namespace_name)
            
            return True
        
        # Real K8s namespace creation
        if not self._k8s_client and not self._init_k8s_client():
            return False
            
        # Check mock again in case initialization forced mock mode (e.g. missing lib)
        if self.use_mock:
            ns_info.status = NamespaceStatus.ACTIVE
            self._namespaces[namespace_name] = ns_info
            self._stats["namespaces_created"] += 1
            logger.info(f"[MOCK] Created namespace (fallback): {namespace_name}")
            if self._on_namespace_created:
                self._on_namespace_created(namespace_name)
            return True
        
        try:
            from kubernetes import client
            
            namespace_manifest = client.V1Namespace(
                metadata=client.V1ObjectMeta(
                    name=namespace_name,
                    labels=default_labels,
                )
            )
            
            self._k8s_client.create_namespace(body=namespace_manifest)
            
            ns_info.status = NamespaceStatus.ACTIVE
            self._namespaces[namespace_name] = ns_info
            self._stats["namespaces_created"] += 1
            
            logger.info(f"Created K8s namespace: {namespace_name}")
            
            if self._on_namespace_created:
                self._on_namespace_created(namespace_name)
            
            return True
        except Exception as e:
            logger.error(f"Failed to create namespace {namespace_name}: {e}")
            ns_info.status = NamespaceStatus.FAILED
            self._namespaces[namespace_name] = ns_info
            self._stats["errors"] += 1
            return False
    
    def delete_namespace(self, sub_chain_id: str) -> bool:
        """
        Delete a K8s namespace for a sub-chain.
        
        Args:
            sub_chain_id: Unique identifier for the sub-chain.
        
        Returns:
            True if namespace was deleted successfully.
        """
        namespace_name = self._get_namespace_name(sub_chain_id)
        
        if namespace_name not in self._namespaces:
            logger.warning(f"Namespace {namespace_name} not found")
            return False
        
        ns_info = self._namespaces[namespace_name]
        ns_info.status = NamespaceStatus.TERMINATING
        
        if self.use_mock:
            del self._namespaces[namespace_name]
            self._stats["namespaces_deleted"] += 1
            logger.info(f"[MOCK] Deleted namespace: {namespace_name}")
            
            if self._on_namespace_deleted:
                self._on_namespace_deleted(namespace_name)
            
            return True
        
        if not self._k8s_client and not self._init_k8s_client():
            return False
            
        # Check mock again
        if self.use_mock:
            del self._namespaces[namespace_name]
            self._stats["namespaces_deleted"] += 1
            logger.info(f"[MOCK] Deleted namespace (fallback): {namespace_name}")
            if self._on_namespace_deleted:
                self._on_namespace_deleted(namespace_name)
            return True
        
        try:
            self._k8s_client.delete_namespace(name=namespace_name)
            
            del self._namespaces[namespace_name]
            self._stats["namespaces_deleted"] += 1
            
            logger.info(f"Deleted K8s namespace: {namespace_name}")
            
            if self._on_namespace_deleted:
                self._on_namespace_deleted(namespace_name)
            
            return True
        except Exception as e:
            logger.error(f"Failed to delete namespace {namespace_name}: {e}")
            self._stats["errors"] += 1
            return False
    
    def get_namespace_status(self, sub_chain_id: str) -> NamespaceStatus:
        """
        Get the status of a namespace.
        
        Args:
            sub_chain_id: Unique identifier for the sub-chain.
        
        Returns:
            Current status of the namespace.
        """
        namespace_name = self._get_namespace_name(sub_chain_id)
        
        if namespace_name not in self._namespaces:
            return NamespaceStatus.NOT_FOUND
        
        if self.use_mock:
            return self._namespaces[namespace_name].status
        
        if not self._k8s_client and not self._init_k8s_client():
            return NamespaceStatus.UNKNOWN
            
        # Check mock again
        if self.use_mock:
            return self._namespaces[namespace_name].status
        
        try:
            ns = self._k8s_client.read_namespace(name=namespace_name)
            phase = ns.status.phase
            
            if phase == "Active":
                self._namespaces[namespace_name].status = NamespaceStatus.ACTIVE
            elif phase == "Terminating":
                self._namespaces[namespace_name].status = NamespaceStatus.TERMINATING
            else:
                self._namespaces[namespace_name].status = NamespaceStatus.UNKNOWN
            
            return self._namespaces[namespace_name].status
        except Exception as e:
            logger.error(f"Failed to get namespace status: {e}")
            return NamespaceStatus.UNKNOWN
    
    def get_namespace_resources(self, sub_chain_id: str) -> dict[str, Any]:
        """
        Get resource information for a namespace.
        
        Args:
            sub_chain_id: Unique identifier for the sub-chain.
        
        Returns:
            Dictionary with resource information.
        """
        namespace_name = self._get_namespace_name(sub_chain_id)
        
        if namespace_name not in self._namespaces:
            return {"error": "Namespace not found"}
        
        ns_info = self._namespaces[namespace_name]
        
        if self.use_mock:
            return {
                "namespace": namespace_name,
                "status": ns_info.status.value,
                "pods": ns_info.pod_count,
                "resource_quota": ns_info.resource_quota,
            }
        
        if not self._k8s_client and not self._init_k8s_client():
            return {"error": "K8s client not available"}
            
        # Check mock again
        if self.use_mock:
            return {
                "namespace": namespace_name,
                "status": ns_info.status.value,
                "pods": ns_info.pod_count,
                "resource_quota": ns_info.resource_quota,
            }
        
        try:
            # Get pods in namespace
            pods = self._k8s_client.list_namespaced_pod(namespace=namespace_name)
            ns_info.pod_count = len(pods.items)
            
            # Get resource quotas
            quotas = self._k8s_client.list_namespaced_resource_quota(namespace=namespace_name)
            
            return {
                "namespace": namespace_name,
                "status": ns_info.status.value,
                "pods": ns_info.pod_count,
                "resource_quotas": [q.spec.hard for q in quotas.items] if quotas.items else [],
            }
        except Exception as e:
            logger.error(f"Failed to get namespace resources: {e}")
            return {"error": str(e)}
    
    def provision_sub_chain_deployment(
        self,
        config: DeploymentConfig,
    ) -> bool:
        """
        Create a sub-chain node deployment in the namespace.
        
        Args:
            config: Deployment configuration.
        
        Returns:
            True if deployment was created successfully.
        """
        namespace_name = self._get_namespace_name(config.sub_chain_id)
        
        if namespace_name not in self._namespaces:
            logger.error(f"Namespace {namespace_name} does not exist, create it first")
            return False
        
        if self.use_mock:
            self._namespaces[namespace_name].pod_count = config.replicas
            self._stats["deployments_created"] += 1
            logger.info(f"[MOCK] Created deployment in {namespace_name}")
            return True
        
        if not self._apps_client and not self._init_k8s_client():
            return False
            
        # Check mock again
        if self.use_mock:
            self._namespaces[namespace_name].pod_count = config.replicas
            self._stats["deployments_created"] += 1
            logger.info(f"[MOCK] Created deployment (fallback) in {namespace_name}")
            return True
        
        try:
            from kubernetes import client
            
            # Build container spec
            container = client.V1Container(
                name="hierachain-node",
                image=config.image,
                ports=[
                    client.V1ContainerPort(container_port=config.node_port, name="node-port"),
                    client.V1ContainerPort(container_port=config.api_port, name="api-port"),
                ],
                command=["hrc", "start", "--host", "0.0.0.0", "--port", str(config.api_port)],
                env=[
                    client.V1EnvVar(name="NODE_ID", value=config.sub_chain_id),
                    client.V1EnvVar(name="NODE_PORT", value=str(config.node_port)),
                    client.V1EnvVar(name="PEERS", value=",".join(config.peers)),
                ] + [
                    client.V1EnvVar(name=k, value=v)
                    for k, v in config.environment.items()
                ],
                resources=client.V1ResourceRequirements(
                    limits={"cpu": config.cpu_limit, "memory": config.memory_limit},
                    requests={"cpu": config.cpu_request, "memory": config.memory_request},
                ),
            )
            
            # Build deployment spec
            deployment = client.V1Deployment(
                metadata=client.V1ObjectMeta(
                    name=f"hierachain-{config.sub_chain_id}",
                    namespace=namespace_name,
                    labels={"app": "hierachain", "subchain-id": config.sub_chain_id},
                ),
                spec=client.V1DeploymentSpec(
                    replicas=config.replicas,
                    selector=client.V1LabelSelector(
                        match_labels={"app": "hierachain", "subchain-id": config.sub_chain_id}
                    ),
                    template=client.V1PodTemplateSpec(
                        metadata=client.V1ObjectMeta(
                            labels={"app": "hierachain", "subchain-id": config.sub_chain_id}
                        ),
                        spec=client.V1PodSpec(containers=[container]),
                    ),
                ),
            )
            
            self._apps_client.create_namespaced_deployment(
                namespace=namespace_name,
                body=deployment,
            )
            
            self._namespaces[namespace_name].pod_count = config.replicas
            self._stats["deployments_created"] += 1
            
            logger.info(f"Created deployment {config.sub_chain_id} in {namespace_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create deployment: {e}")
            self._stats["errors"] += 1
            return False
    
    def list_managed_namespaces(self) -> list[NamespaceInfo]:
        """Get list of all managed namespaces."""
        return list(self._namespaces.values())
    
    def get_stats(self) -> dict[str, Any]:
        """Get manager statistics."""
        return {
            **self._stats,
            "managed_namespaces": len(self._namespaces),
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
