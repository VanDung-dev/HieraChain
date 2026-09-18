"""Unit tests for API ledger event endpoints."""

from unittest.mock import patch

import pytest
from fastapi import BackgroundTasks

from hierachain.api.ledger.events import add_event
from hierachain.api.ledger.schemas import EventRequest


class _SubChain:
    chain = []
    pending_events = []

    def add_event(self, event: dict) -> str:
        return "evt-authoritative-id"


class _Manager:
    def __init__(self, sub_chain: _SubChain) -> None:
        self.sub_chain = sub_chain

    def get_sub_chain(self, chain_name: str) -> _SubChain:
        return self.sub_chain


@pytest.mark.asyncio
async def test_add_event_returns_authoritative_event_id() -> None:
    sub_chain = _SubChain()
    request = EventRequest(entity_id="ENTITY-001", event_type="quality_check")

    with patch(
        "hierachain.api.ledger.events.process_event_details",
        return_value=({}, None),
    ):
        response = await add_event(
            "test-chain",
            request,
            BackgroundTasks(),
            _Manager(sub_chain),
        )

    assert response.event_id == "evt-authoritative-id"
