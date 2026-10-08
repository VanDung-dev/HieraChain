"""Regression coverage for proof submission through the hierarchy manager."""

import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from hierachain.api.ledger.proofs import submit_proof


def test_submit_proof_uses_manager_result() -> None:
    direct_submit = Mock(return_value=True)
    sub_chain = SimpleNamespace(name="orders", chain=[object()], submit_proof_to_main=direct_submit)
    manager = SimpleNamespace(
        get_sub_chain=lambda _name: sub_chain,
        get_main_chain=lambda: object(),
        submit_proof_to_main_chain=Mock(return_value=False),
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(submit_proof("orders", manager))

    assert exc_info.value.status_code == 500
    manager.submit_proof_to_main_chain.assert_called_once_with("orders")
    direct_submit.assert_not_called()
