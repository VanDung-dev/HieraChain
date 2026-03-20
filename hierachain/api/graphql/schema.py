"""
GraphQL Schema for HieraChain Ledger

This module provides GraphQL types, queries, and mutations for the HieraChain system.

IPFS Integration:
- Event details can be stored on-chain (details field) or off-chain (details_cid)
- GraphQL resolvers support lazy-loading of off-chain data
- Clients control CID resolution via query arguments
"""

import time
import json
import graphene
from graphene import (
    ObjectType, String, Int, Float, List, Field, InputObjectType, Boolean
)

from hierachain.api.v1.endpoints import get_hierarchy_manager
from hierachain.api.storage.endpoint_helpers import (
    is_ipfs_enabled, resolve_event_details
)
from hierachain.api.storage.utils import is_cid_string


# ===== GraphQL Types =====


class EventType(ObjectType):
    """
    Event type for GraphQL with IPFS support.

    Fields:
    - details: Event details (inline or resolved from IPFS)
    - details_cid: IPFS CID if data is stored off-chain
    - details_nonce: Encryption nonce for IPFS data
    - is_offchain: Indicator if event uses off-chain storage
    """
    entity_id = String()
    event_type = String()
    details = String()  # JSON string (inline or resolved from CID)
    details_cid = String()  # IPFS CID if off-chain storage
    details_nonce = String()  # Encryption nonce
    is_offchain = Boolean()  # Indicator for off-chain storage
    timestamp = Float()
    signature = String()

    async def resolve_details(self, info, resolve_cid=True):
        """
        Lazy resolver for event details with CID support.

        Args:
            resolve_cid: If True, automatically resolve CIDs to actual data

        Returns:
            JSON string of event details
        """
        # Check if data is already inline
        if hasattr(self, 'details') and self.details and not is_cid_string(str(self.details)):
            return self.details

        # Check if we have CID info for off-chain data
        if hasattr(self, 'details_cid') and self.details_cid and resolve_cid:
            if not is_ipfs_enabled():
                return json.dumps({"error": "IPFS not enabled", "cid": self.details_cid})

            try:
                # Build event dict for resolver
                event_dict = {
                    "entity_id": getattr(self, 'entity_id', None),
                    "event": getattr(self, 'event_type', None),
                    "details_cid": self.details_cid,
                    "details_nonce": getattr(self, 'details_nonce', None),
                    "details_metadata": getattr(self, 'details_metadata', None),
                }

                # Resolve from IPFS
                resolved = await resolve_event_details(event_dict, resolve=True)

                # Return resolved details as JSON string
                if 'details' in resolved:
                    return json.dumps(resolved['details'])

            except Exception as e:
                return json.dumps({
                    "error": f"Failed to resolve CID: {str(e)}",
                    "cid": self.details_cid
                })

        # Return CID reference if not resolving
        if hasattr(self, 'details_cid') and self.details_cid:
            return json.dumps({
                "cid": self.details_cid,
                "nonce": getattr(self, 'details_nonce', None),
                "note": "Set resolve_cid=true to fetch actual data"
            })

        return self.details if hasattr(self, 'details') else None

    def resolve_is_offchain(self, info):
        """Check if event uses off-chain storage."""
        return hasattr(self, 'details_cid') and bool(self.details_cid)


class BlockMetadataType(ObjectType):
    """Block metadata for GraphQL"""
    chain_name = String()
    events_count = Int()
    validator_signatures = List(String)


class BlockType(ObjectType):
    """Block type for GraphQL"""
    index = Int()
    hash = String()
    previous_hash = String()
    timestamp = Float()
    nonce = String()
    events = List(EventType)
    metadata = Field(BlockMetadataType)
    
    def resolve_events(self):
        """Resolve events field - expects parent to be BlockType"""
        if hasattr(self, 'events'):
            return self.events
        return []
    
    def resolve_metadata(self):
        """Resolve metadata field - expects parent to be BlockType"""
        if hasattr(self, 'metadata'):
            return self.metadata
        return None


class ChainStatusType(ObjectType):
    """Chain status for GraphQL"""
    chain_name = String()
    block_count = Int()
    latest_block_index = Int()
    latest_block_hash = String()
    status = String()


# ===== Input Types =====


class AddEventInput(InputObjectType):
    """Input for adding an event"""
    chain_name = String(required=True)
    entity_id = String(required=True)
    event_type = String(required=True)
    details = String()


# ===== Queries =====
# Note: Query resolvers are now defined inside the Query class below


def _get_block_from_chain(chain, block_index, chain_name):
    """Helper to get block from chain at given index"""
    chain_blocks = chain.chain
    if 0 <= block_index < len(chain_blocks):
        block = chain_blocks[block_index]
        if block is None or not hasattr(block, 'index'):
            return None
        return _to_block_type(block, chain_name)  # type: ignore[arg-type]
    return None


def resolve_block(_root, _info, chain_name, block_index):
    """Resolve a single block"""
    manager = get_hierarchy_manager()

    # Try to get from sub-chains first
    sub_chains = manager.get_all_sub_chains()
    if chain_name in sub_chains:
        chain = sub_chains[chain_name]
        return _get_block_from_chain(chain, block_index, chain_name)

    # Try main chain
    main_chain = manager.get_main_chain()
    if main_chain:
        return _get_block_from_chain(main_chain, block_index, "main_chain")

    return None


def _get_blocks_from_chain(chain, from_index, to_index, limit, chain_name):
    """Helper to get multiple blocks from chain"""
    chain_blocks = chain.chain
    start = from_index if from_index is not None else 0
    end = to_index if to_index is not None else len(chain_blocks)
    blocks = []
    for block in chain_blocks[start:end][:limit]:
        if block is None or not hasattr(block, 'index'):
            continue
        blocks.append(_to_block_type(block, chain_name))  # type: ignore[arg-type]
    return blocks


def resolve_blocks(
    _root, _info, chain_name, from_index=None, to_index=None, limit=100
):
    """Resolve multiple blocks"""
    chain = _get_chain_for_name(chain_name)
    if not chain:
        return []
    return _get_blocks_from_chain(chain, from_index, to_index, limit, chain_name)


def _filter_event_by_entity_id(event, entity_id):
    """Filter event by entity_id"""
    if not entity_id:
        return True
    return getattr(event, 'entity_id', None) == entity_id


def _filter_event_by_type(event, event_type):
    """Filter event by event_type"""
    if not event_type:
        return True
    event_type_value = getattr(event, 'event_type', None) or getattr(event, 'event', None)
    return event_type_value == event_type


def _filter_event_by_time(event_time, from_timestamp, to_timestamp):
    """Filter event by timestamp range"""
    if not from_timestamp and not to_timestamp:
        return True
    if from_timestamp and event_time < from_timestamp:
        return False
    if to_timestamp and event_time > to_timestamp:
        return False
    return True


def _filter_event(event, entity_id, event_type, from_timestamp, to_timestamp):
    """Helper to check if event matches filter criteria"""
    event_time = getattr(event, 'timestamp', 0)
    
    return (
        _filter_event_by_entity_id(event, entity_id) and
        _filter_event_by_type(event, event_type) and
        _filter_event_by_time(event_time, from_timestamp, to_timestamp)
    )


def _get_chain_for_name(chain_name):
    """Helper to get chain by name from sub-chains or main chain"""
    manager = get_hierarchy_manager()
    sub_chains = manager.get_all_sub_chains()
    if chain_name in sub_chains:
        return sub_chains[chain_name]
    main_chain = manager.get_main_chain()
    return main_chain


def _get_filtered_events_from_block(
    block, entity_id, event_type, from_timestamp, to_timestamp
):
    """Get filtered events from a single block"""
    if not hasattr(block, 'events') or not block.events:
        return []
    
    filtered = []
    for event in block.events:
        if _filter_event(
            event, entity_id, event_type, from_timestamp, to_timestamp
        ):
            filtered.append(_to_event_type(event))
    return filtered


def _get_events_from_chain(
    chain, entity_id, event_type, from_timestamp, to_timestamp
):
    """Generator to get filtered events from chain blocks"""
    for block in chain.chain:
        block_events = _get_filtered_events_from_block(
            block, entity_id, event_type, from_timestamp, to_timestamp
        )
        for event in block_events:
            yield event


def resolve_events(
    _root,
    _info,
    chain_name,
    entity_id=None,
    event_type=None,
    from_timestamp=None,
    to_timestamp=None,
    limit=100
):
    """Resolve events"""
    chain = _get_chain_for_name(chain_name)
    if not chain:
        return []

    # Use generator to collect events up to limit
    events = []
    for event in _get_events_from_chain(chain, entity_id, event_type, from_timestamp, to_timestamp):
        events.append(event)
        if len(events) >= limit:
            break

    return events


def resolve_chain_status(_root, _info, chain_name):
    """Resolve chain status"""
    manager = get_hierarchy_manager()

    # Try sub-chains first
    sub_chains = manager.get_all_sub_chains()
    if chain_name in sub_chains:
        chain = sub_chains[chain_name]
        return _to_chain_status(chain, chain_name)

    # Try main chain
    main_chain = manager.get_main_chain()
    if main_chain and chain_name == "main_chain":
        return _to_chain_status(main_chain, "main_chain")

    return None


def resolve_all_chains(_root, _info):
    """Resolve all chains status"""
    manager = get_hierarchy_manager()
    statuses = []

    # Main chain
    main_chain = manager.get_main_chain()
    if main_chain:
        statuses.append(_to_chain_status(main_chain, "main_chain"))

    # Sub-chains
    sub_chains = manager.get_all_sub_chains()
    for chain_name, chain in sub_chains.items():
        statuses.append(_to_chain_status(chain, chain_name))

    return statuses


class Query(ObjectType):
    """Root Query for GraphQL"""
    
    block = Field(
        BlockType,
        chain_name=String(required=True),
        block_index=Int(required=True),
        resolver=resolve_block
    )
    
    blocks = List(
        BlockType,
        chain_name=String(required=True),
        from_index=Int(),
        to_index=Int(),
        limit=Int(),
        resolver=resolve_blocks
    )
    
    events = List(
        EventType,
        chain_name=String(required=True),
        entity_id=String(),
        event_type=String(),
        from_timestamp=Float(),
        to_timestamp=Float(),
        limit=Int(),
        resolver=resolve_events
    )
    
    chain_status = Field(
        ChainStatusType,
        chain_name=String(required=True),
        resolver=resolve_chain_status
    )
    
    all_chains = List(ChainStatusType, resolver=resolve_all_chains)


# ===== Mutations =====


class AddEventMutation(graphene.Mutation):
    """Mutation to add an event to a chain"""
    class Arguments:
        event = AddEventInput(required=True)
    
    success = graphene.Boolean()
    block_index = graphene.Int()
    error = graphene.String()
    
    @classmethod
    def mutate(cls, _root, _info, event):
        manager = get_hierarchy_manager()

        # Get chain
        sub_chains = manager.get_all_sub_chains()
        if event.chain_name in sub_chains:
            chain = sub_chains[event.chain_name]
        else:
            main_chain = manager.get_main_chain()
            chain = main_chain
            if not main_chain:
                result = AddEventMutation()
                result.success = False
                result.error = f"Chain {event.chain_name} not found"
                return result

        try:
            # Parse details JSON if provided
            import json
            details = {}
            if event.details:
                try:
                    details = json.loads(event.details)
                except json.JSONDecodeError:
                    result = AddEventMutation()
                    result.success = False
                    result.error = "Invalid JSON in details"
                    return result

            # Create event dictionary (same as v1 endpoints)
            event_obj = {
                "entity_id": event.entity_id,
                "event": event.event_type,
                "timestamp": time.time(),
                "details": details
            }

            # Add event to chain
            block_index = chain.add_event(event_obj)

            result = AddEventMutation()
            result.success = True
            result.block_index = block_index
            return result
        except Exception as e:
            result = AddEventMutation()
            result.success = False
            result.error = str(e)
            return result


class Mutations(ObjectType):
    """Root Mutations"""
    add_event = AddEventMutation.Field()


# ===== Helper Functions =====


def _to_block_type(block, chain_name):
    """Convert block to GraphQL type"""
    # Skip if block is None or doesn't have required attributes
    if block is None or not hasattr(block, 'index'):
        return None
    
    # Extract events using list comprehension for better performance
    events = _extract_events(block)
    
    # Build metadata if available
    metadata = _build_block_metadata(block, chain_name, len(events))
    
    # Create and populate block type
    block_type = _create_block_type(block, events, metadata)
    return block_type


def _extract_events(block):
    """Extract events from block"""
    if hasattr(block, 'events') and block.events:
        return [_to_event_type(event) for event in block.events]
    return []


def _build_block_metadata(block, chain_name, events_count):
    """Build block metadata if available"""
    if hasattr(block, 'metadata') and block.metadata:
        metadata = BlockMetadataType()
        metadata.chain_name = chain_name
        metadata.events_count = events_count
        metadata.validator_signatures = (
            getattr(block.metadata, 'validator_signatures', []) or []
        )
        return metadata
    return None


def _create_block_type(block, events, metadata):
    """Create and populate BlockType instance"""
    block_type = BlockType()
    block_type.index = getattr(block, 'index', 0)
    block_type.hash = getattr(block, 'hash', '')
    block_type.previous_hash = getattr(block, 'previous_hash', '')
    block_type.timestamp = getattr(block, 'timestamp', 0)
    block_type.nonce = getattr(block, 'nonce', '')
    block_type.events = events
    block_type.metadata = metadata
    return block_type


def _to_event_type(event):
    """Convert event to GraphQL type"""
    import json
    details = ""
    if hasattr(event, 'data') and event.data:
        details = json.dumps(event.data)
    
    # Handle both 'event' and 'event_type' attributes
    event_type = getattr(event, 'event_type', None) or getattr(event, 'event', '')
    
    event_obj = EventType()
    event_obj.entity_id = getattr(event, 'entity_id', '')
    event_obj.event_type = event_type
    event_obj.details = details
    event_obj.timestamp = getattr(event, 'timestamp', 0)
    event_obj.signature = getattr(event, 'signature', '')
    return event_obj


def _to_chain_status(chain, chain_name):
    """Convert chain to GraphQL type"""
    latest_block = None
    if hasattr(chain, 'get_latest_block'):
        latest_block = chain.get_latest_block()
    
    block_count = 0
    if hasattr(chain, 'chain') and chain.chain:
        block_count = len(chain.chain)
    
    status = ChainStatusType()
    status.chain_name = chain_name
    status.block_count = block_count
    status.latest_block_index = getattr(latest_block, 'index', 0) if latest_block else 0
    status.latest_block_hash = getattr(latest_block, 'hash', '') if latest_block else ''
    status.status = "active"
    return status


# ===== Schema =====

schema = graphene.Schema(
    query=Query,
    mutation=Mutations,
    types=[EventType, BlockType, ChainStatusType]
)
