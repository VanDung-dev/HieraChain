"""Exercise consensus spacing in the real signed, persisted SubChain commit path."""

from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest

from hierachain.consensus.proof_of_authority import ProofOfAuthority
from hierachain.core.block import Block
from hierachain.hierarchical.sub_chain import base as sub_chain_base
from hierachain.hierarchical.sub_chain.base import SubChain
from hierachain.security.verify.block_verifier import get_block_verifier


@pytest.fixture
def chain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[SubChain]:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sub_chain_base.settings, "BLOCK_INTERVAL", ProofOfAuthority().block_interval)
    monkeypatch.setattr(sub_chain_base, "_consumer_loop", lambda _chain: None)
    sub_chain = SubChain("rapid_blocks", config={"db_url": f"sqlite:///{tmp_path / 'chain.db'}"})
    try:
        yield sub_chain
    finally:
        sub_chain.shutdown()


def test_default_commits_consecutive_signed_blocks_without_spacing_wait(
    chain: SubChain, monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = chain.ordering_service
    previous = service.storage_handler.last_block
    assert previous is not None
    assert chain.consensus.config["block_interval"] == 0.0
    clock = [previous.timestamp]
    monkeypatch.setattr(sub_chain_base, "time", SimpleNamespace(time=lambda: clock[0]))

    def reject_wait(delay: float) -> bool:
        pytest.fail(f"Default PoA unexpectedly waited {delay} seconds")

    monkeypatch.setattr(chain._shutdown_event, "wait", reject_wait)
    for index in (1, 2):
        clock[0] += 0.01
        service.processor.block_manager.commit_block(Block(
            index=0,
            events=[{"entity_id": "record-1", "event": "updated", "timestamp": clock[0]}],
        ))
        assert service.blocks_created == index + 1

    blocks = service.storage_handler.get_blocks_from_db(0)
    assert [block.index for block in blocks] == [0, 1, 2]
    for previous, block in zip(blocks, blocks[1:]):
        assert block.previous_hash == previous.hash
        assert block.timestamp - previous.timestamp == pytest.approx(0.01)
        assert chain.consensus.validate_block(block, previous)
        assert get_block_verifier().verify_block_signature(block, chain.trusted_public_keys[block.creator_id])


@pytest.mark.parametrize("cancel", [False, True])
def test_explicit_spacing_preserves_wait_and_shutdown_cancellation(
    chain: SubChain, monkeypatch: pytest.MonkeyPatch, cancel: bool,
) -> None:
    chain.consensus.config["block_interval"] = 10.0
    previous = chain.ordering_service.storage_handler.last_block
    assert previous is not None
    clock = [previous.timestamp + 0.01]
    waits: list[float] = []
    monkeypatch.setattr(sub_chain_base, "time", SimpleNamespace(time=lambda: clock[0]))

    def advance_clock(delay: float) -> bool:
        waits.append(delay)
        clock[0] += delay
        return cancel

    monkeypatch.setattr(chain._shutdown_event, "wait", advance_clock)
    block = Block(index=1, events=[], previous_hash=previous.hash)
    if cancel:
        with pytest.raises(RuntimeError, match="stopped during consensus finalization"):
            chain._finalize_ordered_block(block, previous)
    else:
        finalized = chain._finalize_ordered_block(block, previous)
        assert finalized.timestamp - previous.timestamp == pytest.approx(5.0)
        assert chain.consensus.validate_block(finalized, previous)
    assert waits == pytest.approx([4.99])
