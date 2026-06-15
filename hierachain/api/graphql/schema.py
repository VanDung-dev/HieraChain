"""
GraphQL Schema for HieraChain Ledger

This module provides GraphQL types, queries, and mutations for the HieraChain system.

IPFS Integration:
- Event details can be stored on-chain (details field) or off-chain (details_cid)
- GraphQL resolvers support lazy-loading of off-chain data
- Clients control CID resolution via query arguments
"""

import graphene
from graphene import ObjectType, List, Field, String, Int, Float

from hierachain.api.graphql.types import (
    EventType, BlockType, ChainStatusType,
)
from hierachain.api.graphql.resolvers import (
    resolve_block, resolve_blocks, resolve_events,
    resolve_chain_status, resolve_all_chains,
    Mutations,
)


class Query(ObjectType):
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


schema = graphene.Schema(
    query=Query,
    mutation=Mutations,
    types=[EventType, BlockType, ChainStatusType]
)
