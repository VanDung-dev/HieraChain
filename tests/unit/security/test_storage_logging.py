"""
Tests for storage logging security.

Verifies that storage modules use SecureLogger instead of plain logging,
error logs do not leak raw exception details, and LOG_SQL_DETAIL controls
SQL echo behavior.
"""

import inspect
from unittest.mock import patch, MagicMock

from hierachain.adapters.database import SQLiteAdapter, sqlite_adapter
from hierachain.security import (
    SecureLogger,
    get_storage_logger,
)


class TestGetStorageLogger:
    """Tests for the get_storage_logger helper function."""

    def test_returns_secure_logger_instance(self):
        """get_storage_logger() returns a SecureLogger."""
        logger = get_storage_logger()
        assert isinstance(logger, SecureLogger)

    def test_logger_name(self):
        """Logger name should be 'hierachain.storage'."""
        logger = get_storage_logger()
        assert logger.name == "hierachain.storage"


class TestSQLiteAdapterUsesSecureLogger:
    """Verify that sqlite_adapter module uses SecureLogger."""

    def test_module_logger_is_secure(self):
        """sqlite_adapter.logger should be a SecureLogger instance."""
        assert isinstance(sqlite_adapter.logger, SecureLogger)

    def test_no_plain_logging_import(self):
        """sqlite_adapter should not use logging.getLogger directly."""
        source = inspect.getsource(sqlite_adapter)
        assert "logging.getLogger" not in source


class TestSQLiteAdapterErrorLogSanitization:
    """Ensure SQLiteAdapter error logs do not leak raw DB exceptions."""

    def test_store_chain_error_no_raw_exception(self, tmp_path):
        """Error log from store_chain should not contain raw exception."""

        db_path = str(tmp_path / "test.db")
        adapter = SQLiteAdapter(database_path=db_path)

        # Create a mock chain that will work until _get_connection fails
        mock_chain = MagicMock()
        mock_chain.name = "test_chain"

        with patch.object(adapter, '_get_connection', side_effect=Exception("SENSITIVE_SQL_ERROR: table xyz")):
            captured_logs = []

            with patch('hierachain.adapters.database.base.sql_adapter.SQLBase.logger') as mock_logger:
                mock_logger.error = lambda log_msg, **kw: captured_logs.append((log_msg, kw))
                mock_logger.debug = lambda log_msg, **kw: None

                result = adapter.store_chain(mock_chain)

            assert result is False
            # Verify no captured error log contains raw exception text
            for msg, kwargs in captured_logs:
                assert "SENSITIVE_SQL_ERROR" not in msg
                assert "table xyz" not in str(kwargs)
                # Should contain structured operation info
                assert kwargs.get("operation") == "store_chain"

    def test_load_chain_error_no_raw_exception(self, tmp_path):
        """Error log from load_chain should not leak DB details."""

        db_path = str(tmp_path / "test.db")
        adapter = SQLiteAdapter(database_path=db_path)

        with patch.object(adapter, '_get_connection', side_effect=Exception("no such table: secret_table")):
            captured_logs = []

            with patch('hierachain.adapters.database.base.sql_adapter.SQLBase.logger') as mock_logger:
                mock_logger.error = lambda log_msg, **kw: captured_logs.append((log_msg, kw))
                mock_logger.debug = lambda log_msg, **kw: None

                result = adapter.load_chain("test")

            assert result is None
            for msg, kwargs in captured_logs:
                assert "secret_table" not in msg
                assert "secret_table" not in str(kwargs)
