"""
Unit tests for HieraChain Blockchain Explorer.

Verifies components, rendering logic, and IPFS formatting helpers.
"""

import time
import pytest
from typing import Any

from hierachain.api.blockchain_explorer import (
    BlockchainExplorer,
    ChainOverviewComponent,
    EntityTracerComponent,
    EventAnalyticsComponent,
    ProofVisualizerComponent,
    ExplorerError
)
from hierachain.api.storage.explorer_helpers import (
    format_event_for_display,
    build_cid_badge_html,
    build_cid_resolution_button_html,
    format_event_table_row_html
)


# ==============================================================================
# Mock Objects
# ==============================================================================

class MockBlock:
    def __init__(self, index: int, events: list[dict[str, Any]], timestamp: float | None = None):
        self.index = index
        self.events = events
        self.timestamp = timestamp or time.time()


class MockMainChain:
    def __init__(self):
        self.chain = [
            MockBlock(0, [{"entity_id": "sys-0", "event": "genesis", "details": {}}], time.time() - 7200),
            MockBlock(1, [
                {"entity_id": "entity-123", "event": "quality_check", "details": {"status": "passed"}},
                {"entity_id": "entity-456", "event": "packaging", "details_cid": "QmXyz123", "details_nonce": "nonce123"}
            ], time.time() - 3600)
        ]
        self.total_events = 3
        self.recent_proofs = [
            {"sub_chain": "logistics", "proof": "proof-hash-1", "timestamp": time.time() - 100}
        ]
        self.proof_count = 1
        self.latest_proofs = {
            "logistics": {"proof": "proof-hash-1", "timestamp": time.time() - 100}
        }

    def get_indexed_entity_events(self, entity_id: str) -> list[dict[str, Any]]:
        events = []
        for block in self.chain:
            for event in block.events:
                if event.get("entity_id") == entity_id:
                    events.append({
                        "block_index": block.index,
                        "event": event
                    })
        return events


class MockSubChain:
    def __init__(self, name: str):
        self.name = name
        self.chain = [
            MockBlock(0, [{"entity_id": "entity-123", "event": "shipping", "details": {"carrier": "DHL"}}], time.time() - 1800)
        ]
        self.total_events = 1
        self.event_type_counts = {"shipping": 1}

    def get_indexed_entity_events(self, entity_id: str) -> list[dict[str, Any]]:
        events = []
        for block in self.chain:
            for event in block.events:
                if event.get("entity_id") == entity_id:
                    events.append({
                        "block_index": block.index,
                        "event": event
                    })
        return events


class MockHierarchyManager:
    def __init__(self):
        self.main_chain = MockMainChain()
        self.sub_chains = {
            "logistics": MockSubChain("logistics")
        }


# ==============================================================================
# Test Cases
# ==============================================================================

def test_blockchain_explorer_init():
    """Test explorer initialization and registration."""
    chain = MockHierarchyManager()
    explorer = BlockchainExplorer(chain)

    assert explorer.chain == chain
    assert "chain_overview" in explorer.ui_components
    assert "entity_tracer" in explorer.ui_components
    assert "event_analytics" in explorer.ui_components
    assert "proof_visualizer" in explorer.ui_components

    # Verify custom registration
    explorer.register_component("custom", "mock_component")
    assert explorer.get_component("custom") == "mock_component"


def test_explorer_render_dashboard():
    """Test main dashboard rendering."""
    chain = MockHierarchyManager()
    explorer = BlockchainExplorer(chain)

    dashboard = explorer.render()
    assert dashboard["title"] == "HieraChain Explorer"
    assert len(dashboard["components"]) == 3
    assert dashboard["components"][0]["id"] == "chain_overview"
    assert dashboard["components"][1]["id"] == "entity_tracer"
    assert dashboard["components"][2]["id"] == "event_analytics"
    assert "css" in dashboard["assets"]
    assert "js" in dashboard["assets"]


def test_explorer_render_specific_component():
    """Test specific component rendering and errors."""
    chain = MockHierarchyManager()
    explorer = BlockchainExplorer(chain)

    # Valid rendering of overview via chain instance
    result = explorer.render("chain_overview")
    assert "main_chain" in result
    assert "sub_chains" in result

    # Invalid component ID should raise error
    with pytest.raises(ExplorerError):
        explorer.render("invalid_component_id")


def test_chain_overview_component():
    """Test ChainOverviewComponent stats calculation."""
    chain = MockHierarchyManager()
    component = ChainOverviewComponent(chain)

    summary = component.render_summary()
    assert "main_chain" in summary
    assert summary["main_chain"]["block_count"] == 2
    assert summary["main_chain"]["total_events"] == 3

    assert len(summary["sub_chains"]) == 1
    assert summary["sub_chains"][0]["name"] == "logistics"
    assert summary["sub_chains"][0]["events"] == 1

    assert len(summary["recent_activity"]) == 2
    assert summary["recent_activity"][0]["type"] == "block_created"


def test_entity_tracer_component():
    """Test EntityTracerComponent path search logic."""
    chain = MockHierarchyManager()
    component = EntityTracerComponent(chain)

    # Test trace form structure
    form = component.render_input_form()
    assert form["type"] == "form"
    assert len(form["fields"]) == 2

    # Trace entity on both chains
    trace = component.trace_entity("entity-123", chain_type="all")
    assert trace["entity_id"] == "entity-123"
    assert trace["total_events"] == 2
    assert "main_chain" in trace["chains_found"]
    assert "logistics" in trace["chains_found"]


def test_event_analytics_component():
    """Test EventAnalyticsComponent stats tracking."""
    chain = MockHierarchyManager()
    component = EventAnalyticsComponent(chain)

    summary = component.render_summary()
    assert "event_types" in summary
    assert "activity_timeline" in summary
    assert summary["chain_distribution"]["main_chain"] == 3
    assert summary["chain_distribution"]["logistics"] == 1


def test_proof_visualizer_component():
    """Test ProofVisualizerComponent visual map structure."""
    chain = MockHierarchyManager()
    component = ProofVisualizerComponent(chain)

    flow = component.render_proof_flow()
    assert flow["validation_status"]["total_proofs"] == 1
    assert len(flow["proof_submissions"]) == 1
    assert flow["hierarchy_view"]["main_chain"]["blocks"] == 2
    assert len(flow["hierarchy_view"]["main_chain"]["sub_chains"]) == 1


# ==============================================================================
# Helper Verification
# ==============================================================================

def test_ipfs_event_formatting():
    """Test IPFS indicators in event formatting."""
    # On-chain event
    onchain_event = {
        "entity_id": "product-123",
        "event": "quality_check",
        "details": {"status": "passed"}
    }
    formatted_onchain = format_event_for_display(onchain_event)
    assert formatted_onchain["_storage"]["type"] == "onchain"
    assert formatted_onchain["_storage"]["ipfs"] is False

    # Off-chain IPFS event (unresolved display)
    offchain_event = {
        "entity_id": "product-456",
        "event": "audit",
        "details_cid": "QmXyz1234567890",
        "details_nonce": "nonce123"
    }
    formatted_offchain = format_event_for_display(offchain_event, resolve_cid=False)
    assert formatted_offchain["_storage"]["type"] == "offchain"
    assert formatted_offchain["_storage"]["ipfs"] is True
    assert formatted_offchain["details"]["_type"] == "ipfs_reference"
    assert formatted_offchain["details"]["resolved"] is False


def test_html_components():
    """Test HTML layout helpers for badges and buttons."""
    cid = "QmXyz123"
    nonce = "nonce123"

    badge_html = build_cid_badge_html(cid, resolved=False)
    assert "cid-badge-unresolved" in badge_html
    assert "IPFS" in badge_html

    button_html = build_cid_resolution_button_html(cid, nonce)
    assert "btn-resolve-cid" in button_html
    assert "Load Details" in button_html


def test_format_event_table_row_html():
    """Test rendering of single row HTML structure."""
    event = {
        "entity_id": "entity-123",
        "event": "packaging",
        "timestamp": 12345678.9,
        "details": {"status": "success"}
    }

    row_html = format_event_table_row_html(event, index=1, resolve_cid=False)
    assert "<tr" in row_html
    assert "entity-123" in row_html
    assert "packaging" in row_html
    assert "success" in row_html
