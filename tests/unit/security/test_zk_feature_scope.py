"""Production ZK placeholders must not return successful proofs or verification."""

import pytest

from hierachain.config.settings import settings
from hierachain.security.verify.zk_verifier import ZKVerificationError, ZKVerifier
from hierachain.security.zk_prover import ZKProver


def test_production_proving_reports_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ZK_PROVING_KEY_PATH", "")
    monkeypatch.setattr(settings, "ZK_CIRCUIT_PATH", "")
    prover = ZKProver(mode="production")

    result = prover.generate_proof("a" * 64, "b" * 64, 1)

    assert result.success is False
    assert result.proof == b""
    assert result.error is not None
    assert "not yet implemented" in result.error
    assert prover.get_stats()["successful_generations"] == 0


def test_production_verification_reports_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ZK_VERIFICATION_KEY_PATH", "")
    verifier = ZKVerifier(mode="production")

    with pytest.raises(ZKVerificationError, match="not yet implemented"):
        verifier.verify(
            b"unsupported-proof",
            {"old_state_root": "a" * 64, "new_state_root": "b" * 64, "block_index": 1},
        )

    assert verifier.get_stats()["successful_verifications"] == 0
