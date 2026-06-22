"""
K8s operations — real and mock implementations for namespace lifecycle management.
"""

import logging
from typing import Any

from kubernetes import client, config

from hierachain.hierarchical.k8s_namespace_manager.types import (
    NamespaceInfo,
    NamespaceStatus,
    DeploymentConfig,
)

logger = logging.getLogger(__name__)


def _prepare_namespace_labels(
    sub_chain_id: str, labels: dict[str, str] | None = None
) -> dict[str, str]:
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
    return {
        "namespace": namespace_name,
        "status": ns_info.status.value,
        "pods": ns_info.pod_count,
        "resource_quota": ns_info.resource_quota,
    }


def _load_kubeconfig_file(manager: Any) -> bool:
    import os
    if not os.path.exists(manager.kubeconfig_path):
        logger.info(
            "Kubeconfig not found at %s, falling back to mock mode",
            manager.kubeconfig_path
        )
        manager.use_mock = True
        return True
    config.load_kube_config(config_file=manager.kubeconfig_path)
    return False


def _load_default_kubeconfig(manager: Any) -> bool:
    try:
        config.load_incluster_config()
        return False
    except config.ConfigException:
        import os
        default_kubeconfig = os.path.expanduser("~/.kube/config")
        if not os.path.exists(default_kubeconfig):
            logger.info(
                "No kubeconfig found (not in cluster, no ~/.kube/config), using mock mode"
            )
            manager.use_mock = True
            return True
        config.load_kube_config()
        return False


def _setup_k8s_api_clients(manager: Any) -> None:
    core_v1_api = getattr(client, "CoreV1Api")
    apps_v1_api = getattr(client, "AppsV1Api")
    manager.k8s_client = core_v1_api()
    manager.apps_client = apps_v1_api()


def _fallback_to_mock(manager: Any, warning: str | None = None, info: str | None = None) -> bool:
    if warning:
        logger.warning(warning)
    elif info:
        logger.info(info)
    else:
        logger.debug("Using mock K8s client")
    manager.use_mock = True
    return True


def _init_k8s_client_impl(manager: Any) -> bool:
    if manager.use_mock:
        return _fallback_to_mock(manager)

    if client is None:
        return _fallback_to_mock(manager, warning="kubernetes package not installed, using mock mode")

    try:
        has_failed = (
            _load_kubeconfig_file(manager)
            if manager.kubeconfig_path
            else _load_default_kubeconfig(manager)
        )
        if has_failed:
            return True

        _setup_k8s_api_clients(manager)
        logger.info("K8s client initialized successfully")
        return True
    except ImportError:
        return _fallback_to_mock(manager, warning="kubernetes package not installed, using mock mode")
    except Exception as e:
        return _fallback_to_mock(
            manager, info=f"Failed to initialize K8s client ({e}), using mock mode"
        )


def _create_namespace_real_impl(
    manager: Any,
    name: str,
    labels: dict[str, str],
    ns_info: NamespaceInfo,
) -> bool:
    k8s = manager.k8s_client
    if k8s is None:
        raise RuntimeError("K8s client not initialized")
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
    k8s = manager.k8s_client
    if k8s is None:
        raise RuntimeError("K8s client not initialized")
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
    k8s = manager.k8s_client
    if k8s is None:
        raise RuntimeError("K8s client not initialized")
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
    k8s = manager.k8s_client
    if k8s is None:
        raise RuntimeError("K8s client not initialized")
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


def _build_container(deploy_config: Any) -> Any:
    return client.V1Container(
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


def _build_deployment(deploy_config: Any, namespace_name: str, container: Any) -> Any:
    return client.V1Deployment(
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


def _create_k8s_deployment(manager: Any, deploy_config: Any, namespace_name: str) -> bool:
    apps = manager.apps_client
    if apps is None:
        raise RuntimeError("K8s apps client not initialized")
    try:
        container = _build_container(deploy_config)
        deployment = _build_deployment(deploy_config, namespace_name, container)

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


def _provision_sub_chain_deployment_impl(
    manager: Any, deploy_config: DeploymentConfig
) -> bool:
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

    return _create_k8s_deployment(manager, deploy_config, namespace_name)
