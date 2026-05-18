---
title: Using the Blockchain Explorer
description: Guide to the Blockchain Explorer UI performance monitoring and Block analysis tools.
icon: material/monitor-dashboard
---

# Using the Blockchain Explorer

## Chain Explorer

Unlike peripheral Web applications, HieraChain provides a core, in-depth visual API Dashboard directly within the core (`hierachain/api/blockchain_explorer.py`). Through the JSON structure returned by the `render` module, any web-view can realize it into a real-time audit Dashboard.

### 1. Explorer Components

The interface (or API Render format) includes 4 main components:

* **Chain Overview Component (`chain_overview`)**: Displays a summary table of the structure. Shows overall metrics such as Block height, Event count across the Main-chain and Sub-chains, as well as recent activity.
* **Entity Tracer Component (`entity_tracer`)**: A tracing tool. Enter an Entity's ID or any specification to globally search which Blocks and Events are governing that entity, supporting tracing of every asset link.
* **Event Analytics Component (`event_analytics`)**: Outputs a historical Timeline of event volume distributed across Blocks (e.g., bucketed by the last 24 hours) or draws event distribution charts. Serves as high-load activity monitoring.
* **Proof Visualizer Component (`proof_visualizer`)**: A hierarchical diagram view. Shows the success rate of ZK Proofs, highlighting which chains are stuck in Mock mode versus Production verification mode.

### IPFS Features in the Explorer

The Explorer supports visualizing data stored off-chain:

* **Data Detection**: Automatically displays Badges for events stored on IPFS.

    * **Yellow**: Unresolved CID data.
    * **Green**: Data has been fetched and decrypted (Resolved).

* **Instant Data Loading**: Provides a **"Load Details"** button to fetch data from IPFS via the API Server without reloading the page.
* **Security**: Data is securely decrypted on the Server before being displayed in the user interface.

### 2. How to Invoke the Dashboard via API

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

With a highly logical JSON structure, Front-end developers (React/Vue/HTML5) can easily render card displays showing metrics and corresponding blocks without having to manually construct queries.
