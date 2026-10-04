"""
Unit tests for hierachain.config.secret_manager.SecretManager.

Tests cover:
- env backend (mocking os.environ)
- Vault failure handling when configuration is missing
- aws JSON field selection and rejection of invalid payloads
- default value handling
- unsupported backend rejection
"""
import os
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from hierachain.config.secret_manager import SecretManager


def _make_manager(backend: str = "env", **extra_env: str) -> SecretManager:
    """Create a SecretManager with a controlled environment."""
    env = {"HRC_SECRET_BACKEND": backend, **extra_env}
    with patch.dict(os.environ, env, clear=True):
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
    def test_missing_vault_url_uses_default_without_reading_env(self):
        env = {
            "HRC_SECRET_BACKEND": "vault",
            "HRC_VAULT_TOKEN": "tok",
            # HRC_VAULT_URL intentionally absent
            "HRC_CLUSTER_SECRET": "ambient-test-secret",
        }
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("HRC_VAULT_URL", None)
            from hierachain.config.secret_manager import SecretManager
            mgr = SecretManager()
            assert mgr.get_secret("HRC_CLUSTER_SECRET") is None
            assert mgr.get_secret("HRC_CLUSTER_SECRET", default="unavailable") == "unavailable"

    def test_missing_vault_token_uses_default_without_reading_env(self):
        env = {
            "HRC_SECRET_BACKEND": "vault",
            "HRC_VAULT_URL": "http://vault:8200",
            # HRC_VAULT_TOKEN intentionally absent
            "HRC_CLUSTER_SECRET": "ambient-test-secret",
        }
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("HRC_VAULT_TOKEN", None)
            from hierachain.config.secret_manager import SecretManager
            mgr = SecretManager()
            assert mgr.get_secret("HRC_CLUSTER_SECRET") is None
            assert mgr.get_secret("HRC_CLUSTER_SECRET", default="unavailable") == "unavailable"

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
        mock_hvac.Client.return_value.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"HRC_CLUSTER_SECRET": "vault_secret_value"}}
        }

        with (
            patch.dict(os.environ, env),
            patch("hierachain.config.secret_manager.hvac", mock_hvac),
        ):
            mgr = SecretManager()
            result = mgr.get_secret("HRC_CLUSTER_SECRET")

        assert result == "vault_secret_value"


class TestAwsBackend:
    def test_returns_only_requested_field(self, caplog: pytest.LogCaptureFixture) -> None:
        mgr = _make_manager(
            "aws", HRC_AWS_REGION="ap-southeast-1", HRC_AWS_SECRET_NAME="hiera/test"
        )
        blob = '{"FIRST":"first-test-value","SECOND":"second-test-value","EMPTY":""}'
        with patch("hierachain.config.secret_manager.boto3.client") as client:
            client.return_value.get_secret_value.return_value = {"SecretString": blob}
            assert mgr.get_secret("FIRST") == "first-test-value"
            assert mgr.get_secret("SECOND") == "second-test-value"
            assert mgr.get_secret("EMPTY", default="fallback") == ""
            assert mgr.get_secret("MISSING") is None
            assert mgr.get_secret("MISSING", default="fallback") == "fallback"
            client.assert_called_with("secretsmanager", region_name="ap-southeast-1")
            assert client.return_value.get_secret_value.call_count == 5
            client.return_value.get_secret_value.assert_called_with(SecretId="hiera/test")
        assert blob not in caplog.text
        assert "first-test-value" not in caplog.text
        assert "second-test-value" not in caplog.text

    @pytest.mark.parametrize("payload", [
        {}, {"SecretBinary": b"binary-test-value"}, {"SecretString": None},
        {"SecretString": b"bytes-test-value"}, {"SecretString": "invalid-test-json"},
        {"SecretString": '"scalar-test-value"'}, {"SecretString": "[]"},
        {"SecretString": "null"}, {"SecretString": "123"},
        {"SecretString": '{"FIRST":null}'}, {"SecretString": '{"FIRST":false}'},
        {"SecretString": '{"FIRST":123}'}, {"SecretString": '{"FIRST":["nested-test-value"]}'},
        {"SecretString": '{"FIRST":{"SECOND":"nested-test-value"}}'},
    ])
    def test_invalid_payload_returns_default(
        self, payload: dict[str, object], caplog: pytest.LogCaptureFixture
    ) -> None:
        mgr = _make_manager("aws", HRC_AWS_SECRET_NAME="hiera/test")
        with (
            patch("hierachain.config.secret_manager.boto3.client") as client,
            patch.dict(os.environ, {"FIRST": "env-test-value"}),
        ):
            client.return_value.get_secret_value.return_value = payload
            assert mgr.get_secret("FIRST") is None
            assert mgr.get_secret("FIRST", default="fallback") == "fallback"
        assert "test-value" not in caplog.text
        assert "invalid-test-json" not in caplog.text
        assert "hiera/test" not in caplog.text

    def test_missing_secret_id_does_not_use_key_as_id(self) -> None:
        mgr = _make_manager("aws")
        with patch("hierachain.config.secret_manager.boto3.client") as client:
            assert mgr.get_secret("FIRST", default="fallback") == "fallback"
            client.assert_not_called()

    @pytest.mark.parametrize("error", [
        ClientError({"Error": {"Code": "AccessDeniedException", "Message": "private-test-value"}},
                    "GetSecretValue"),
        RuntimeError("private-test-value"),
    ])
    def test_service_error_returns_default_without_logging_details(
        self, error: Exception, caplog: pytest.LogCaptureFixture
    ) -> None:
        mgr = _make_manager("aws", HRC_AWS_SECRET_NAME="hiera/test")
        with patch("hierachain.config.secret_manager.boto3.client") as client:
            client.return_value.get_secret_value.side_effect = error
            assert mgr.get_secret("FIRST", default="fallback") == "fallback"
        assert "private-test-value" not in caplog.text


class TestUnknownBackend:
    def test_unsupported_backend_is_rejected(self):
        with patch.dict(os.environ, {"HRC_SECRET_BACKEND": "gcp"}, clear=True):
            from hierachain.config.secret_manager import SecretManager
            with pytest.raises(ValueError, match="Unsupported HRC_SECRET_BACKEND"):
                SecretManager()
