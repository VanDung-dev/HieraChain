"""
Unit tests for hierachain.config.secret_manager.SecretManager.

Tests cover:
- env backend (mocking os.environ)
- vault backend fallback when hvac is not configured
- aws backend fallback when boto3 is not configured
- default value handling
- unknown backend fallback to env
"""
import os
from unittest.mock import MagicMock, patch


def _make_manager(backend: str = "env", **extra_env):
    """Create a SecretManager with a controlled environment."""
    env = {"HRC_SECRET_BACKEND": backend, **extra_env}
    with patch.dict(os.environ, env, clear=False):
        from hierachain.config.secret_manager import SecretManager
        return SecretManager()


class TestEnvBackend:
    def test_reads_existing_variable(self):
        with patch.dict(os.environ, {"HRC_SECRET_BACKEND": "env", "MY_SECRET": "s3cr3t"}):
            from hierachain.config.secret_manager import SecretManager
            mgr = SecretManager()
            assert mgr.get_secret("MY_SECRET") == "s3cr3t"

    def test_returns_none_for_missing_key(self):
        with patch.dict(os.environ, {"HRC_SECRET_BACKEND": "env"}, clear=False):
            os.environ.pop("DEFINITELY_NOT_SET", None)
            from hierachain.config.secret_manager import SecretManager
            mgr = SecretManager()
            assert mgr.get_secret("DEFINITELY_NOT_SET") is None

    def test_returns_default_for_missing_key(self):
        with patch.dict(os.environ, {"HRC_SECRET_BACKEND": "env"}, clear=False):
            os.environ.pop("MISSING_KEY_DEFAULT", None)
            from hierachain.config.secret_manager import SecretManager
            mgr = SecretManager()
            assert mgr.get_secret("MISSING_KEY_DEFAULT", default="fallback") == "fallback"

    def test_backend_property(self):
        with patch.dict(os.environ, {"HRC_SECRET_BACKEND": "env"}):
            from hierachain.config.secret_manager import SecretManager
            mgr = SecretManager()
            assert mgr.backend == "env"


class TestVaultBackend:
    def test_falls_back_to_env_when_vault_url_missing(self):
        env = {
            "HRC_SECRET_BACKEND": "vault",
            "HRC_VAULT_TOKEN": "tok",
            # HRC_VAULT_URL intentionally absent
            "HRC_CLUSTER_SECRET": "env_fallback",
        }
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("HRC_VAULT_URL", None)
            from hierachain.config.secret_manager import SecretManager
            mgr = SecretManager()
            # Without URL it falls back to env backend
            assert mgr.get_secret("HRC_CLUSTER_SECRET") == "env_fallback"

    def test_falls_back_to_env_when_vault_token_missing(self):
        env = {
            "HRC_SECRET_BACKEND": "vault",
            "HRC_VAULT_URL": "http://vault:8200",
            # HRC_VAULT_TOKEN intentionally absent
            "HRC_CLUSTER_SECRET": "env_fallback",
        }
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("HRC_VAULT_TOKEN", None)
            from hierachain.config.secret_manager import SecretManager
            mgr = SecretManager()
            assert mgr.get_secret("HRC_CLUSTER_SECRET") == "env_fallback"

    def test_uses_vault_when_configured(self):
        """Mock hvac client and verify we call it correctly."""
        env = {
            "HRC_SECRET_BACKEND": "vault",
            "HRC_VAULT_URL": "http://vault:8200",
            "HRC_VAULT_TOKEN": "test-token",
            "HRC_VAULT_PATH": "hiera/secrets",
        }
        mock_hvac = MagicMock()
        mock_hvac.Client.return_value.is_authenticated.return_value = True
        mock_hvac.Client.return_value.secrets.kv.business.read_secret_version.return_value = {
            "data": {"data": {"HRC_CLUSTER_SECRET": "vault_secret_value"}}
        }

        with (
            patch.dict(os.environ, env),
            patch.dict("sys.modules", {"hvac": mock_hvac}),
        ):
            # Re-import to pick up mocked hvac
            import importlib
            import hierachain.config.secret_manager as sm_module
            importlib.reload(sm_module)
            mgr = sm_module.SecretManager()
            result = mgr.get_secret("HRC_CLUSTER_SECRET")

        assert result == "vault_secret_value"


class TestAwsBackend:
    def test_uses_aws_when_configured(self):
        """Mock boto3 and verify we call it correctly."""
        env = {
            "HRC_SECRET_BACKEND": "aws",
            "HRC_AWS_REGION": "ap-southeast-1",
            "HRC_AWS_SECRET_NAME": "prod/HieraChain/cluster_secret",
        }
        mock_boto3 = MagicMock()
        mock_boto3.client.return_value.get_secret_value.return_value = {
            "SecretString": "aws_secret_value"
        }

        with (
            patch.dict(os.environ, env),
            patch.dict(
                "sys.modules",
                {"boto3": mock_boto3, "botocore.exceptions": MagicMock()}
            )
        ):
            import importlib
            import hierachain.config.secret_manager as sm_module
            importlib.reload(sm_module)
            mgr = sm_module.SecretManager()
            result = mgr.get_secret("HRC_AWS_SECRET_NAME")

        assert result == "aws_secret_value"


class TestUnknownBackend:
    def test_falls_back_to_env_with_warning(self, caplog):
        import logging
        env = {"HRC_SECRET_BACKEND": "gcp", "MY_KEY": "my_value"}
        with patch.dict(os.environ, env, clear=False):
            from hierachain.config.secret_manager import SecretManager
            mgr = SecretManager()
            with caplog.at_level(logging.WARNING, logger="hierachain.config.secret_manager"):
                result = mgr.get_secret("MY_KEY")

        assert result == "my_value"
        assert any("Unknown HRC_SECRET_BACKEND" in m for m in caplog.messages)



