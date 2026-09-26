---
title: Using the Blockchain Explorer
description: Guide to the Blockchain Explorer UI performance monitoring and Block analysis tools.
icon: material/monitor-dashboard
---

# Using the Blockchain Explorer

## Chain Explorer

`BlockchainExplorer` in `hierachain/api/blockchain_explorer.py` returns dashboard data as JSON. A web view can use this data to display chain activity and verification results.

### 1. Explorer Components

The rendered data can include these four components:

* **Chain Overview Component (`chain_overview`)**: Displays block height, event counts across Main-Chain and Sub-Chains, and recent activity.
* **Entity Tracer Component (`entity_tracer`)**: Searches for an entity ID and shows related blocks and events.
* **Event Analytics Component (`event_analytics`)**: Shows event counts by type, an hourly timeline for the last 24 hours based on Main-Chain blocks, and total event counts by chain.
* **Proof Visualizer Component (`proof_visualizer`)**: Shows recent proof submissions, a validation summary, and the block hierarchy for Main-Chain and Sub-Chains.

### IPFS Features in the Explorer

The Explorer supports visualizing data stored off-chain:

* **Data Detection**: Displays badges for events stored on IPFS.

    * **Yellow**: Unresolved CID data.
    * **Green**: Data has been fetched and decrypted (Resolved).

* **Data Loading**: The **"Load Details"** button fetches data from IPFS through the API Server without reloading the page.
* **Decryption**: The Server decrypts data before displaying it in the user interface.

### 2. Render the Dashboard via API

Developers can integrate the Dashboard directly into their Server-side Rendering:

```python
from hierachain.api.blockchain_explorer import BlockchainExplorer

# Attach the module to the existing Core structure
explorer = BlockchainExplorer(chain=my_hierarchy_manager_instance)

# Render a full dashboard page containing Chain Overview, Entity Tracer, Event Analytics
dashboard_data = explorer.render()

# Or render just the "Entity Tracer" section
tracer_form_ui = explorer.render(component_id="entity_tracer")
```

The returned JSON lets front-end developers (React/Vue/HTML5) render cards with metrics and related blocks.
