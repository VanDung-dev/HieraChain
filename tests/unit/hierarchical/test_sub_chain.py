"""
Unit tests for SubChain class and its consensus initialization behavior.
"""

from pathlib import Path

import pytest

from hierachain.config.settings import settings
from hierachain.consensus.proof_of_authority import ProofOfAuthority
from hierachain.consensus.proof_of_federation import ProofOfFederation
from hierachain.hierarchical.sub_chain.base import SubChain


@pytest.fixture(autouse=True)
def isolated_ordering_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{tmp_path / 'ordering.db'}")


def test_sub_chain_default_consensus_is_poa():
    """Verify SubChain defaults to ProofOfAuthority regardless of global setting."""
    sub_chain = SubChain(name="pharmacy", domain_type="healthcare")
    assert isinstance(sub_chain.consensus, ProofOfAuthority)
    assert sub_chain.consensus.name == "pharmacy_PoA"
    sub_chain.stop()


def test_sub_chain_default_consensus_with_pof_global_setting(monkeypatch):
    """Verify SubChain still defaults to ProofOfAuthority even when settings.CONSENSUS_TYPE is proof_of_federation."""
    monkeypatch.setattr(settings, "CONSENSUS_TYPE", "proof_of_federation")
    
    sub_chain = SubChain(name="pharmacy", domain_type="healthcare")
    # SubChain must remain PoA for intra-organization operations
    assert isinstance(sub_chain.consensus, ProofOfAuthority)
    sub_chain.stop()


def test_sub_chain_explicit_pof_override():
    """Verify SubChain allows explicit override to ProofOfFederation via config dict."""
    config = {"consensus_type": "proof_of_federation"}
    sub_chain = SubChain(name="federated_sub", domain_type="healthcare", config=config)
    assert isinstance(sub_chain.consensus, ProofOfFederation)
    sub_chain.stop()
