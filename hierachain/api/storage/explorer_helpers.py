"""
Explorer Helper Functions for IPFS Integration.

This module provides utilities for displaying and resolving CIDs
in the Blockchain Explorer UI.
"""

import json
from typing import Any
from functools import lru_cache

from hierachain.api.storage.endpoint_helpers import (
    is_ipfs_enabled, resolve_event_details
)
from hierachain.api.storage.utils import (
    format_cid_display, detect_data_location
)


# LRU cache for resolved CIDs (avoids repeated IPFS calls)
@lru_cache(maxsize=1000)
def _cache_key(cid: str, nonce: str) -> str:
    """Generate cache key for CID resolution."""
    return f"{cid}:{nonce}"


def format_event_for_display(event: dict[str, Any], resolve_cid: bool = False) -> dict[str, Any]:
    """
    Format event for Explorer display with CID indicators.

    Args:
        event: Event dictionary
        resolve_cid: If True, resolve CIDs to actual data

    Returns:
        Formatted event dict with display-friendly structure
    """
    formatted = dict(event)

    # Detect storage location
    storage_type = detect_data_location(event)

    if storage_type == "offchain":
        # Add visual indicators for off-chain data
        formatted["_storage"] = {
            "type": "offchain",
            "ipfs": True,
            "cid": event.get("details_cid"),
            "cid_display": format_cid_display(event.get("details_cid", ""), max_length=12)
        }

        # If not resolving, replace details with CID info
        if not resolve_cid:
            formatted["details"] = {
                "_type": "ipfs_reference",
                "cid": format_cid_display(event.get("details_cid", ""), max_length=15),
                "full_cid": event.get("details_cid"),
                "nonce": event.get("details_nonce"),
                "resolved": False,
                "note": "Click to load full details"
            }
    else:
        formatted["_storage"] = {
            "type": "onchain",
            "ipfs": False
        }

    return formatted


async def resolve_event_for_explorer(event: dict[str, Any]) -> dict[str, Any]:
    """
    Resolve event CID for Explorer display.

    Args:
        event: Event dictionary with potential CID

    Returns:
        Event with resolved details
    """
    if not is_ipfs_enabled():
        return event

    storage_type = detect_data_location(event)

    if storage_type == "offchain":
        try:
            resolved = await resolve_event_details(event, resolve=True)
            resolved["_storage"] = {
                "type": "offchain",
                "ipfs": True,
                "cid": event.get("details_cid"),
                "resolved": True
            }
            return resolved
        except Exception as e:
            # Return original with error info
            error_event = dict(event)
            error_event["_resolution_error"] = str(e)
            return error_event

    return event


def build_cid_badge_html(cid: str, resolved: bool = False) -> str:
    """
    Build HTML badge for CID display.

    Args:
        cid: IPFS CID
        resolved: If True, show as resolved

    Returns:
        HTML string for badge
    """
    badge_class = "cid-badge-resolved" if resolved else "cid-badge-unresolved"
    icon = "✓" if resolved else "📦"

    return f'''
    <span class="{badge_class}" title="IPFS CID: {cid}">
        {icon} IPFS: {format_cid_display(cid, max_length=10)}
    </span>
    '''


def build_cid_resolution_button_html(cid: str, nonce: str) -> str:
    """
    Build HTML button for CID resolution.

    Args:
        cid: IPFS CID
        nonce: Encryption nonce

    Returns:
        HTML string for button
    """
    return f'''
    <button
        class="btn-resolve-cid"
        data-cid="{cid}"
        data-nonce="{nonce}"
        onclick="resolveCID(this)">
        📥 Load Details
    </button>
    '''


def get_explorer_css_styles() -> str:
    """
    Get CSS styles for IPFS indicators in Explorer.

    Returns:
        CSS string
    """
    return '''
    <style>
    .cid-badge-unresolved {
        display: inline-block;
        padding: 2px 8px;
        background: #ffc107;
        color: #000;
        border-radius: 3px;
        font-size: 0.85em;
        font-family: monospace;
        cursor: help;
    }

    .cid-badge-resolved {
        display: inline-block;
        padding: 2px 8px;
        background: #28a745;
        color: #fff;
        border-radius: 3px;
        font-size: 0.85em;
        font-family: monospace;
    }

    .btn-resolve-cid {
        padding: 4px 12px;
        background: #007bff;
        color: #fff;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        font-size: 0.9em;
    }

    .btn-resolve-cid:hover {
        background: #0056b3;
    }

    .btn-resolve-cid:disabled {
        background: #6c757d;
        cursor: not-allowed;
    }

    .ipfs-indicator {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px;
        background: #f8f9fa;
        border-left: 3px solid #ffc107;
        margin: 8px 0;
    }

    .ipfs-indicator.resolved {
        border-left-color: #28a745;
    }

    .cid-details {
        font-family: monospace;
        font-size: 0.9em;
        color: #6c757d;
    }

    .storage-type-badge {
        display: inline-block;
        padding: 2px 6px;
        border-radius: 2px;
        font-size: 0.75em;
        text-transform: uppercase;
        font-weight: bold;
    }

    .storage-type-badge.onchain {
        background: #e7f3ff;
        color: #0056b3;
    }

    .storage-type-badge.offchain {
        background: #fff3cd;
        color: #856404;
    }
    </style>
    '''


def get_explorer_javascript() -> str:
    """
    Get JavaScript for CID resolution in Explorer.

    Returns:
        JavaScript string
    """
    return '''
    <script>
    async function resolveCID(button) {
        const cid = button.dataset.cid;
        const nonce = button.dataset.nonce;

        // Disable button during resolution
        button.disabled = true;
        button.textContent = '⏳ Loading...';

        try {
            // Call API to resolve CID
            const response = await fetch(
                `/api/v1/chains/${chainName}/blocks?resolve_cid=true`,
                {method: 'GET'}
            );

            if (!response.ok) {
                throw new Error('Failed to resolve CID');
            }

            const data = await response.json();

            // Update UI with resolved data
            updateEventDetails(cid, data);

            button.textContent = '✓ Loaded';
            button.classList.add('resolved');

        } catch (error) {
            console.error('CID resolution error:', error);
            button.textContent = '❌ Error';
            button.disabled = false;

            setTimeout(() => {
                button.textContent = '📥 Retry';
            }, 2000);
        }
    }

    function updateEventDetails(cid, data) {
        // Find and update the event details section
        const detailsElement = document.querySelector(`[data-cid="${cid}"]`)
            ?.closest('.event-item')
            ?.querySelector('.event-details');

        if (detailsElement && data.details) {
            detailsElement.innerHTML = `
                <pre>${JSON.stringify(data.details, null, 2)}</pre>
            `;

            // Update storage badge
            const badge = detailsElement.closest('.event-item')
                ?.querySelector('.cid-badge-unresolved');
            if (badge) {
                badge.className = 'cid-badge-resolved';
                badge.textContent = '✓ IPFS: ' + cid.substring(0, 10) + '...';
            }
        }
    }

    // Auto-refresh indicators
    setInterval(() => {
        document.querySelectorAll('.cid-badge-unresolved').forEach(badge => {
            badge.style.animation = 'pulse 2s infinite';
        });
    }, 5000);
    </script>
    '''


def format_event_table_row_html(event: dict[str, Any], index: int, resolve_cid: bool = False) -> str:
    """
    Format event as HTML table row for Explorer.

    Args:
        event: Event dictionary
        index: Event index
        resolve_cid: If True, show resolved data

    Returns:
        HTML string for table row
    """
    formatted = format_event_for_display(event, resolve_cid=False)
    storage_info = formatted.get("_storage", {})

    storage_badge = f'''
    <span class="storage-type-badge {storage_info.get('type', 'onchain')}">
        {storage_info.get('type', 'onchain')}
    </span>
    '''

    cid_display = ""
    if storage_info.get("ipfs"):
        cid = event.get("details_cid", "")
        nonce = event.get("details_nonce", "")
        cid_display = f'''
        <div class="ipfs-indicator">
            {build_cid_badge_html(cid, resolved=resolve_cid)}
            {build_cid_resolution_button_html(cid, nonce) if not resolve_cid else ""}
        </div>
        '''

    if resolve_cid and "details" in event:
        details_html = f"<pre>{json.dumps(event['details'], indent=2)}</pre>"
    elif not resolve_cid and storage_info.get("ipfs"):
        details_html = "<em>Click 'Load Details' to view</em>"
    else:
        details_html = f"<pre>{json.dumps(event.get('details', {}), indent=2)}</pre>"

    return (
        f'<tr class="event-row" data-index="{index}">'
        f'<td>{index}</td>'
        f'<td>{event.get("entity_id", "N/A")}</td>'
        f'<td>{event.get("event", event.get("event_type", "N/A"))}</td>'
        f'<td>{storage_badge}</td>'
        f'<td class="event-details">{cid_display}{details_html}</td>'
        f'<td>{event.get("timestamp", "N/A")}</td>'
        f'</tr>'
    )
