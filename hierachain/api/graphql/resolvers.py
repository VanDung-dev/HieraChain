import time
import orjson
import graphene
from graphene import ObjectType

from hierachain.api.ledger.depds import get_hierarchy_manager
from hierachain.api.graphql.types import (
    EventType, BlockType, BlockMetadataType, ChainStatusType, AddEventInput
)


def _get_chain_for_name(chain_name):
    manager = get_hierarchy_manager()
    sub_chains = manager.get_all_sub_chains()
    if chain_name in sub_chains:
        return sub_chains[chain_name]
    main_chain = manager.get_main_chain()
    return main_chain


def _get_block_from_chain(chain, block_index, chain_name):
    chain_blocks = chain.chain
    if 0 <= block_index < len(chain_blocks):
        block = chain_blocks[block_index]
        if block is None or not hasattr(block, 'index'):
            return None
        return _to_block_type(block, chain_name)
    return None


def resolve_block(_root, _info, chain_name, block_index):
    manager = get_hierarchy_manager()

    sub_chains = manager.get_all_sub_chains()
    if chain_name in sub_chains:
        chain = sub_chains[chain_name]
        return _get_block_from_chain(chain, block_index, chain_name)

    main_chain = manager.get_main_chain()
    if main_chain:
        return _get_block_from_chain(main_chain, block_index, "main_chain")

    return None


def _get_blocks_from_chain(chain, from_index, to_index, limit, chain_name):
    chain_blocks = chain.chain
    start = from_index if from_index is not None else 0
    end = to_index if to_index is not None else len(chain_blocks)
    blocks = []
    for block in chain_blocks[start:end][:limit]:
        if block is None or not hasattr(block, 'index'):
            continue
        blocks.append(_to_block_type(block, chain_name))
    return blocks


def resolve_blocks(
    _root, _info, chain_name, from_index=None, to_index=None, limit=100
):
    chain = _get_chain_for_name(chain_name)
    if not chain:
        return []
    return _get_blocks_from_chain(chain, from_index, to_index, limit, chain_name)


def _filter_event_by_entity_id(event, entity_id):
    if not entity_id:
        return True
    return getattr(event, 'entity_id', None) == entity_id


def _filter_event_by_type(event, event_type):
    if not event_type:
        return True
    event_type_value = getattr(event, 'event_type', None) or getattr(event, 'event', None)
    return event_type_value == event_type


def _filter_event_by_time(event_time, from_timestamp, to_timestamp):
    if not from_timestamp and not to_timestamp:
        return True
    if from_timestamp and event_time < from_timestamp:
        return False
    if to_timestamp and event_time > to_timestamp:
        return False
    return True


def _filter_event(event, entity_id, event_type, from_timestamp, to_timestamp):
    event_time = getattr(event, 'timestamp', 0)
    return (
        _filter_event_by_entity_id(event, entity_id) and
        _filter_event_by_type(event, event_type) and
        _filter_event_by_time(event_time, from_timestamp, to_timestamp)
    )


def _get_filtered_events_from_block(
    block, entity_id, event_type, from_timestamp, to_timestamp
):
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
    chain = _get_chain_for_name(chain_name)
    if not chain:
        return []

    events = []
    for event in _get_events_from_chain(chain, entity_id, event_type, from_timestamp, to_timestamp):
        events.append(event)
        if len(events) >= limit:
            break

    return events


def resolve_chain_status(_root, _info, chain_name):
    manager = get_hierarchy_manager()

    sub_chains = manager.get_all_sub_chains()
    if chain_name in sub_chains:
        chain = sub_chains[chain_name]
        return _to_chain_status(chain, chain_name)

    main_chain = manager.get_main_chain()
    if main_chain and chain_name == "main_chain":
        return _to_chain_status(main_chain, "main_chain")

    return None


def resolve_all_chains(_root, _info):
    manager = get_hierarchy_manager()
    statuses = []

    main_chain = manager.get_main_chain()
    if main_chain:
        statuses.append(_to_chain_status(main_chain, "main_chain"))

    sub_chains = manager.get_all_sub_chains()
    for chain_name, chain in sub_chains.items():
        statuses.append(_to_chain_status(chain, chain_name))

    return statuses


class AddEventMutation(graphene.Mutation):
    class Arguments:
        event = AddEventInput(required=True)

    success = graphene.Boolean()
    block_index = graphene.Int()
    error = graphene.String()

    @classmethod
    def mutate(cls, _root, _info, event):
        manager = get_hierarchy_manager()

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
            details = {}
            if event.details:
                try:
                    details = orjson.loads(event.details)
                except orjson.JSONDecodeError:
                    result = AddEventMutation()
                    result.success = False
                    result.error = "Invalid JSON in details"
                    return result

            event_obj = {
                "entity_id": event.entity_id,
                "event": event.event_type,
                "timestamp": time.time(),
                "details": details
            }

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
    add_event = AddEventMutation.Field()


def _extract_events(block):
    if hasattr(block, 'events') and block.events:
        return [_to_event_type(event) for event in block.events]
    return []


def _build_block_metadata(block, chain_name, events_count):
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
    block_type = BlockType()
    block_type.index = getattr(block, 'index', 0)
    block_type.hash = getattr(block, 'hash', '')
    block_type.previous_hash = getattr(block, 'previous_hash', '')
    block_type.timestamp = getattr(block, 'timestamp', 0)
    block_type.nonce = getattr(block, 'nonce', '')
    block_type.events = events
    block_type.metadata = metadata
    return block_type


def _to_block_type(block, chain_name):
    if block is None or not hasattr(block, 'index'):
        return None

    events = _extract_events(block)
    metadata = _build_block_metadata(block, chain_name, len(events))
    block_type = _create_block_type(block, events, metadata)
    return block_type


def _to_event_type(event):
    details = ""
    if hasattr(event, 'data') and event.data:
        details = orjson.dumps(event.data).decode()

    event_type = getattr(event, 'event_type', None) or getattr(event, 'event', '')

    event_obj = EventType()
    event_obj.entity_id = getattr(event, 'entity_id', '')
    event_obj.event_type = event_type
    event_obj.details = details
    event_obj.timestamp = getattr(event, 'timestamp', 0)
    event_obj.signature = getattr(event, 'signature', '')
    return event_obj


def _to_chain_status(chain, chain_name):
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
