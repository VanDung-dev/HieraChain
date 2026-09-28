"""Regression coverage for the CLI proof submission result."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from click.testing import CliRunner

from hierachain.cli import chain as chain_cli


def test_submit_proof_reports_rejection_as_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    sub_chain = SimpleNamespace(submit_proof_to_main=Mock(return_value=False))
    save = Mock()
    monkeypatch.setattr(chain_cli, "get_sub_chain", lambda _name: sub_chain)
    monkeypatch.setattr(chain_cli, "get_main_chain", lambda: object())
    monkeypatch.setattr(chain_cli, "save_chains_to_file", save)

    result = CliRunner().invoke(chain_cli.chain_group, ["submit-proof", "orders"])

    assert result.exit_code != 0
    assert "Successfully submitted" not in result.output
    save.assert_not_called()


def test_submit_proof_reports_save_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    sub_chain = SimpleNamespace(submit_proof_to_main=Mock(return_value=True))
    monkeypatch.setattr(chain_cli, "get_sub_chain", lambda _name: sub_chain)
    monkeypatch.setattr(chain_cli, "get_main_chain", lambda: object())
    monkeypatch.setattr(
        chain_cli, "save_chains_to_file", Mock(side_effect=OSError("save unavailable"))
    )

    result = CliRunner().invoke(chain_cli.chain_group, ["submit-proof", "orders"])

    assert result.exit_code != 0
    assert "Successfully submitted" not in result.output
