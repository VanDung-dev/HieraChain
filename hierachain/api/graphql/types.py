"""
GraphQL types for Hierachain API
"""


from typing import Any, cast

from graphene import (
    Boolean,
    Field,
    Float,
    InputObjectType,
    Int,
    List,
    ObjectType,
    String,
)

from hierachain.api.storage.endpoint_helpers import (
    is_ipfs_enabled,
    resolve_event_details,
)
from hierachain.api.storage.utils import is_cid_string
from hierachain.serialization import dumps_json


class EventType(ObjectType):
    cursor = cast(str | None, String())
    entity_id = cast(str | None, String())
    event_type = cast(str | None, String())
    details = cast(str | None, String())
    details_cid = cast(str | None, String())
    details_nonce = cast(str | None, String())
    is_offchain = cast(bool | None, Boolean())
    timestamp = cast(float | None, Float())
    signature = cast(str | None, String())

    details_metadata: dict[str, Any] | None = None

    async def resolve_details(self, _info, resolve_cid=True):
        if self._has_inline_details():
            return self.details

        if self._should_resolve_cid(resolve_cid):
            return await self._resolve_offchain_details()

        if self._has_cid_reference():
            return self._get_cid_reference()

        return self.details if hasattr(self, 'details') else None

    def _has_inline_details(self) -> bool:
        if not hasattr(self, 'details') or not self.details:
            return False
        details_val = self.details
        if isinstance(details_val, str):
            return not is_cid_string(details_val)
        return True

    def _should_resolve_cid(self, resolve_cid):
        return hasattr(self, 'details_cid') and self.details_cid and resolve_cid

    def _has_cid_reference(self):
        return hasattr(self, 'details_cid') and self.details_cid

    async def _resolve_offchain_details(self):
        if not is_ipfs_enabled():
            return dumps_json({"error": "IPFS not enabled", "cid": self.details_cid})

        try:
            event_dict = self._build_event_dict()
            resolved = await resolve_event_details(event_dict, resolve=True)
            if 'details' in resolved:
                return dumps_json(resolved['details'])
        except Exception as e:
            return dumps_json({"error": f"Failed to resolve CID: {e!s}", "cid": self.details_cid})

        return None

    def _build_event_dict(self):
        return {
            "entity_id": getattr(self, 'entity_id', None),
            "event": getattr(self, 'event_type', None),
            "details_cid": self.details_cid,
            "details_nonce": getattr(self, 'details_nonce', None),
            "details_metadata": getattr(self, 'details_metadata', None),
        }

    def _get_cid_reference(self):
        return dumps_json({
            "cid": self.details_cid,
            "nonce": getattr(self, 'details_nonce', None),
            "note": "Set resolve_cid=true to fetch actual data"
        })

    def resolve_is_offchain(self, _info):
        return hasattr(self, 'details_cid') and bool(self.details_cid)


class BlockMetadataType(ObjectType):
    chain_name = cast(str | None, String())
    events_count = cast(int | None, Int())
    validator_signatures = cast(list[str] | None, List(String))


class BlockType(ObjectType):
    index = cast(int | None, Int())
    hash = cast(str | None, String())
    previous_hash = cast(str | None, String())
    timestamp = cast(float | None, Float())
    nonce = cast(str | None, String())
    events = cast(list[EventType] | None, List(EventType))
    metadata = cast(BlockMetadataType | None, Field(BlockMetadataType))

    def resolve_events(self, _info: Any) -> list[EventType] | None:
        if hasattr(self, 'events'):
            return self.events
        return []

    def resolve_metadata(self, _info: Any) -> Any:
        if hasattr(self, 'metadata'):
            return self.metadata
        return None


class ChainStatusType(ObjectType):
    chain_name = cast(str | None, String())
    block_count = cast(int | None, Int())
    latest_block_index = cast(int | None, Int())
    latest_block_hash = cast(str | None, String())
    status = cast(str | None, String())


class AddEventInput(InputObjectType):
    chain_name = cast(str | None, String(required=True))
    entity_id = cast(str | None, String(required=True))
    event_type = cast(str | None, String(required=True))
    details = cast(str | None, String())
