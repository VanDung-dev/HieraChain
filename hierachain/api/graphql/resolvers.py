import json
import time
from collections.abc import Iterator
from typing import Any

import graphene
from graphene import ObjectType

from hierachain.api.graphql.types import (
    AddEventInput,
    BlockMetadataType,
    BlockType,
    ChainStatusType,
    EventType,
)
from hierachain.api.ledger.depds import get_hierarchy_manager
from hierachain.core.utils import get_block_events
from hierachain.serialization import dumps_json, loads_json

MAX_QUERY_RESULTS = 100


def _bounded_limit(limit: int | None) -> int:
    return MAX_QUERY_RESULTS if limit is None else max(0, min(limit, MAX_QUERY_RESULTS))


def _get_chain_for_name(chain_name: str) -> Any | None:
    manager = get_hierarchy_manager()
    sub_chains = manager.get_all_sub_chains()
    if chain_name in sub_chains:
        return sub_chains[chain_name]
    return manager.get_main_chain() if chain_name == "main_chain" else None


def _get_block_from_chain(chain, block_index, chain_name):
    chain_blocks = chain.chain
    if 0 <= block_index < len(chain_blocks):
        block = chain_blocks[block_index]
        if block is None or not hasattr(block, 'index'):
            return None
        return _to_block_type(block, chain_name)
    return None


def resolve_block(_root: Any, _info: Any, chain_name: str, block_index: int) -> BlockType | None:
    chain = _get_chain_for_name(chain_name)
    if chain is None:
        return None
    return _get_block_from_chain(chain, block_index, chain_name)


def _get_blocks_from_chain(
    chain: Any, from_index: int | None, to_index: int | None, limit: int, chain_name: str,
) -> list[BlockType]:
    chain_blocks = chain.chain
    start = max(0, from_index) if from_index is not None else 0
    end = min(len(chain_blocks), start + limit)
    if to_index is not None:
        end = max(0, min(end, to_index))
    blocks = []
    for block in chain_blocks[start:end]:
        if block is None or not hasattr(block, 'index'):
            continue
        blocks.append(_to_block_type(block, chain_name))
    return blocks


def resolve_blocks(
    _root: Any, _info: Any, chain_name: str,
    from_index: int | None = None, to_index: int | None = None, limit: int | None = None,
) -> list[BlockType]:
    chain = _get_chain_for_name(chain_name)
    if not chain:
        return []
    return _get_blocks_from_chain(chain, from_index, to_index, _bounded_limit(limit), chain_name)


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


def _get_events_from_chain(
    chain: Any, entity_id: str | None, event_type: str | None,
    from_timestamp: float | None, to_timestamp: float | None,
) -> Iterator[EventType]:
    for block in chain.chain:
        for row in get_block_events(block):
            event = _to_event_type(row)
            if _filter_event(event, entity_id, event_type, from_timestamp, to_timestamp):
                yield event


def resolve_events(
    _root: Any,
    _info: Any,
    chain_name: str,
    entity_id: str | None = None,
    event_type: str | None = None,
    from_timestamp: float | None = None,
    to_timestamp: float | None = None,
    limit: int | None = None,
) -> list[EventType]:
    chain = _get_chain_for_name(chain_name)
    effective_limit = _bounded_limit(limit)
    if not chain or effective_limit == 0:
        return []

    events = []
    for event in _get_events_from_chain(chain, entity_id, event_type, from_timestamp, to_timestamp):
        events.append(event)
        if len(events) >= effective_limit:
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
            chain = manager.get_main_chain() if event.chain_name == "main_chain" else None
            if chain is None:
                result = AddEventMutation()
                result.success = False
                result.error = f"Chain {event.chain_name} not found"
                return result

        try:
            details = {}
            if event.details:
                try:
                    details = loads_json(event.details)
                except json.JSONDecodeError:
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

            res = chain.add_event(event_obj)
            block_idx = res if isinstance(res, int) else getattr(chain.get_latest_block(), "index", None)

            result = AddEventMutation()
            result.success = True
            result.block_index = block_idx
            return result
        except Exception as e:
            result = AddEventMutation()
            result.success = False
            result.error = str(e)
            return result


class Mutations(ObjectType):
    add_event = AddEventMutation.Field()


def _extract_events(block: Any) -> list[EventType]:
    return [_to_event_type(event) for event in get_block_events(block)]


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


def _to_event_type(event: Any) -> EventType:
    if isinstance(event, dict):
        converted = EventType(
            entity_id=event.get("entity_id", ""),
            event_type=event.get("event_type") or event.get("event", ""),
            details=dumps_json(event["details"]) if event.get("details") is not None else "",
            details_cid=event.get("details_cid"),
            details_nonce=event.get("details_nonce"),
            timestamp=event.get("timestamp", 0),
            signature=event.get("signature", ""),
        )
        converted.details_metadata = event.get("details_metadata")
        return converted
    details = ""
    if hasattr(event, 'data') and event.data:
        details = dumps_json(event.data)

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
