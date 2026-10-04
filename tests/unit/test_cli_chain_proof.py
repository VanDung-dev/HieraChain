"""Regression coverage for proof submission through the CLI boundary."""

from click.testing import CliRunner

from hierachain.cli import chain as chain_cli


def test_submit_proof_requires_authenticated_api_path() -> None:
    result = CliRunner().invoke(chain_cli.chain_group, ["submit-proof", "orders"])

    assert result.exit_code != 0
    assert "requires a durable HierarchyManager" in result.output
    assert "Successfully submitted" not in result.output
