"""
Secret Manager for HieraChain.

Provides a unified, backend-agnostic interface for retrieving secrets.
Supports the following backends, configured via HRC_SECRET_BACKEND:

- ``env``  (default): Read from environment variables. No extra dependencies.
- ``vault``: HashiCorp Vault via the ``hvac`` package (optional).
- ``aws``:  AWS Secrets Manager via the ``boto3`` package (optional).

Usage::

    from hierachain.config.secret_manager import SecretManager

    manager = SecretManager()
    cluster_secret = manager.get_secret("HRC_CLUSTER_SECRET")
"""

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def _get_from_env(key: str) -> str | None:
    """Read secret from environment variable (default backend)."""
    return os.environ.get(key)


def _get_from_vault(key: str, vault_url: str, vault_token: str, vault_path: str) -> str | None:
    """
    Read secret from HashiCorp Vault (KV v2).

    Args:
        key:         The secret key name (used as the data field within the path).
        vault_url:   Vault server URL, e.g. 'https://vault.example.com'.
        vault_token: Vault token (short-lived, rotated by CI/CD).
        vault_path:  KV-v2 path, e.g. 'hiera/cluster'.

    Returns:
        Secret string value, or None if not found / on error.
    """
    try:
        import hvac  # type: ignore[import]
    except ImportError:
        logger.error(
            "hvac is not installed. Install it with: pip install hvac"
        )
        return None

    try:
        client = hvac.Client(url=vault_url, token=vault_token)
        if not client.is_authenticated():
            logger.error("Vault authentication failed — check HRC_VAULT_TOKEN")
            return None

        response = client.secrets.kv.v2.read_secret_version(path=vault_path)
        data: dict[str, Any] = response["data"]["data"]
        value = data.get(key)
        if value is None:
            masked_key = key[:4] + "****" if len(key) > 4 else "****"
            logger.warning("Secret '%s' not found at Vault path", masked_key)
        return str(value) if value is not None else None
    except Exception as exc:  # noqa: BLE001
        logger.error("Error reading from Vault: %s", type(exc).__name__)
        return None


def _get_from_aws(secret_name: str, region: str) -> str | None:
    """
    Read a secret from AWS Secrets Manager.

    Args:
        secret_name: The full SecretId (e.g. 'prod/HieraChain/cluster_secret').
        region:      AWS region, e.g. 'ap-southeast-1'.

    Returns:
        The ``SecretString`` value, or None on error.
    """
    try:
        import boto3  # type: ignore[import]
        from botocore.exceptions import ClientError  # type: ignore[import]
    except ImportError:
        logger.error(
            "boto3 is not installed. Install it with: pip install boto3"
        )
        return None

    try:
        client = boto3.client("secretsmanager", region_name=region)
        response = client.get_secret_value(SecretId=secret_name)
        return response.get("SecretString")
    except ClientError as exc:  # noqa: BLE001
        logger.error("AWS Secrets Manager error for '%s': %s", secret_name, type(exc).__name__)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected error fetching AWS secret '%s': %s", secret_name, type(exc).__name__)
        return None


class SecretManager:
    """
    Unified secret retrieval interface.

    Reads configuration from environment variables at instantiation time:

    * ``HRC_SECRET_BACKEND``   — ``env`` | ``vault`` | ``aws``  (default: ``env``)
    * ``HRC_VAULT_URL``        — Vault server URL  (vault backend)
    * ``HRC_VAULT_TOKEN``      — Vault token       (vault backend)
    * ``HRC_VAULT_PATH``       — KV-v2 secret path (vault backend, default: ``hiera/secrets``)
    * ``HRC_AWS_REGION``       — AWS region        (aws backend, default: ``us-east-1``)
    * ``HRC_AWS_SECRET_NAME``  — AWS secret name   (aws backend)

    Example::

        manager = SecretManager()
        cluster_secret = manager.get_secret("HRC_CLUSTER_SECRET")
    """

    def __init__(self) -> None:
        self._backend: str = os.environ.get("HRC_SECRET_BACKEND", "env").lower().strip()

        # Vault config
        self._vault_url: str = os.environ.get("HRC_VAULT_URL", "")
        self._vault_token: str = os.environ.get("HRC_VAULT_TOKEN", "")
        self._vault_path: str = os.environ.get("HRC_VAULT_PATH", "hiera/secrets")

        # AWS config
        self._aws_region: str = os.environ.get("HRC_AWS_REGION", "us-east-1")
        self._aws_secret_name: str = os.environ.get("HRC_AWS_SECRET_NAME", "")

        logger.debug("SecretManager initialised")

    def get_secret(self, key: str, default: str | None = None) -> str | None:
        """
        Retrieve a secret by key.

        Args:
            key:     The environment variable name (used as-is for ``env`` backend,
                     and as the data field name for Vault/AWS backends).
            default: Value to return if the secret is not found.

        Returns:
            Secret string value, or *default* if not found.
        """
        value: str | None = None

        if self._backend == "vault":
            value = self._get_vault(key)
        elif self._backend == "aws":
            value = self._get_aws(key)
        else:
            if self._backend != "env":
                logger.warning(
                    "Unknown HRC_SECRET_BACKEND, falling back to 'env'"
                )
            value = _get_from_env(key)

        if value is None:
            if default is None:
                masked_key = key[:4] + "****" if len(key) > 4 else "****"
                logger.warning(
                    "Secret '%s' not found in backend '%s'", masked_key, self._backend
                )
            return default

        return value

    @property
    def backend(self) -> str:
        """Return the active backend name."""
        return self._backend

    def _get_vault(self, key: str) -> str | None:
        if not self._vault_url or not self._vault_token:
            logger.error(
                "Vault backend selected but HRC_VAULT_URL or HRC_VAULT_TOKEN is not set. "
                "Falling back to env."
            )
            return _get_from_env(key)
        return _get_from_vault(key, self._vault_url, self._vault_token, self._vault_path)

    def _get_aws(self, key: str) -> str | None:
        secret_name = self._aws_secret_name or key
        return _get_from_aws(secret_name, self._aws_region)
