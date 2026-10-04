"""Default PoA MainChain must accept rapid proof blocks with real signatures."""

from types import SimpleNamespace

import pytest

from hierachain.config.settings import settings
from hierachain.consensus.proof_of_authority import ProofOfAuthority
from hierachain.core import blockchain as blockchain_module
from hierachain.hierarchical.main_chain.base import MainChain
from hierachain.security.verify.block_verifier import get_block_verifier


def test_default_poa_accepts_consecutive_proof_blocks(
    isolated_chain_storage: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "BLOCK_INTERVAL", ProofOfAuthority().block_interval)
    chain = MainChain(consensus_type="proof_of_authority")
    assert chain.consensus.config["block_interval"] == 0.0
    chain.register_sub_chain("domain")
    clock = [chain.get_latest_block().timestamp]
    monkeypatch.setattr(blockchain_module, "time", SimpleNamespace(time=lambda: clock[0]))

    for index in (1, 2):
        previous = chain.get_latest_block()
        clock[0] += 0.01
        assert chain.add_proof("domain", f"{index:064x}", {"domain_type": "generic"})
        block = chain.finalize_block()
        assert block is not None
        assert block.index == index
        assert block.timestamp - previous.timestamp == pytest.approx(0.01)
        assert chain.consensus.validate_block(block, previous)
        assert get_block_verifier().verify_block(block, previous, chain.trusted_public_keys[block.creator_id])
