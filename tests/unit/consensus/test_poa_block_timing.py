"""PoA defaults must accept rapid signed blocks without weakening validation."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from hierachain.consensus.proof_of_authority import ProofOfAuthority
from hierachain.core.block import Block


@pytest.mark.parametrize(
    ("interval", "gap", "valid"),
    [(None, 0.0, True), (None, 0.001, True), (None, -0.001, False),
     (10.0, 4.99, False), (10.0, 5.0, True)],
)
def test_signed_block_timing(interval: float | None, gap: float, valid: bool) -> None:
    poa = ProofOfAuthority(block_interval=interval)
    poa.add_authority("local")
    previous = Block(index=0, events=[], timestamp=1000.0)
    block = Block(
        index=1,
        previous_hash=previous.hash,
        timestamp=previous.timestamp + gap,
        events=[{"event": "updated", "entity_id": "record-1", "timestamp": 1000.0}],
    )
    finalized = poa.finalize_block(block, "local")
    signature = finalized.to_event_list()[-1]["details"]["authority_signature"]
    assert signature and not signature.startswith("valid_")
    assert poa.validate_block(finalized, previous) is valid


def test_zero_interval_still_rejects_missing_and_untrusted_signatures() -> None:
    poa = ProofOfAuthority()
    poa.add_authority("trusted")
    previous = Block(index=0, events=[], timestamp=1000.0)
    block = Block(
        index=1,
        previous_hash=previous.hash,
        timestamp=1000.001,
        events=[{"event": "updated", "entity_id": "record-1", "timestamp": 1000.0}],
    )
    assert poa.validate_block(block, previous) is False
    attacker = ProofOfAuthority()
    attacker.add_authority("trusted")
    assert poa.validate_block(attacker.finalize_block(block, "trusted"), previous) is False


@pytest.mark.parametrize("interval", [-1.0, float("nan"), float("inf"), float("-inf")])
def test_invalid_interval_is_rejected(interval: float) -> None:
    with pytest.raises(ValueError, match="finite and nonnegative"):
        ProofOfAuthority(block_interval=interval)


@pytest.mark.parametrize("interval", [None, "0", "10", "0.2"])
def test_runtime_interval_default_and_override(interval: str | None, tmp_path: Path) -> None:
    env = dict(os.environ, HRC_ENV="test", HRC_ENV_FILE=str(tmp_path / "absent.env"))
    env.pop("HRC_BLOCK_INTERVAL", None)
    if interval is not None:
        env["HRC_BLOCK_INTERVAL"] = interval
    expected = float(interval) if interval is not None else 0.0
    code = (
        "from hierachain.config.settings import settings; "
        "from hierachain.consensus import ProofOfAuthority, ProofOfFederation; "
        f"assert settings.BLOCK_INTERVAL == {expected!r}; "
        "poa = ProofOfAuthority(block_interval=settings.BLOCK_INTERVAL); "
        f"assert poa.config['block_interval'] == {expected!r}; "
        "assert ProofOfFederation().config['block_interval'] == 5.0"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
