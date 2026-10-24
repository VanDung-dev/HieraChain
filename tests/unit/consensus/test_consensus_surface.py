import importlib.util

import pytest

from hierachain import consensus, error_mitigation
from hierachain.config import Settings
from hierachain.error_mitigation import ErrorCategory, ErrorClassifier, PriorityLevel


def test_supported_consensus_imports_without_removed_engine() -> None:
    assert consensus.ProofOfAuthority("authority").name == "authority"
    assert consensus.ProofOfFederation("federation").name == "federation"
    assert not hasattr(error_mitigation, "ConsensusValidator")
    assert "ConsensusValidator" not in error_mitigation.__all__
    assert not any(name.startswith("BFT_") for name in dir(Settings))


@pytest.mark.parametrize("module", [
    "hierachain.consensus.bft",
    "hierachain.error_mitigation.consensus_validator",
])
def test_removed_consensus_modules_are_not_importable(module: str) -> None:
    assert importlib.util.find_spec(module) is None


@pytest.mark.parametrize("name", [
    "BFTConsensus",
    "BFTMessage",
    "ConsensusError",
    "MessageType",
    "create_bft_network",
    "sign_message",
    "validate_consensus_message",
    "verify_message_signature",
])
def test_removed_consensus_exports_are_unavailable(name: str) -> None:
    assert not hasattr(consensus, name)
    assert name not in consensus.__all__


@pytest.mark.parametrize("priority", [PriorityLevel.HIGH, PriorityLevel.MEDIUM])
def test_consensus_advice_uses_available_operational_actions(priority: PriorityLevel) -> None:
    classifier = ErrorClassifier({})
    strategy = classifier._determine_mitigation_strategy(ErrorCategory.CONSENSUS, priority)
    assert "alert" in strategy
    assert "view_change" not in strategy
