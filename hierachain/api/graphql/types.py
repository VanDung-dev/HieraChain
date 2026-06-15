import json
from graphene import (
    ObjectType, String, Int, Float, List, Boolean, Field,
    InputObjectType
)

from hierachain.api.storage.endpoint_helpers import (
    is_ipfs_enabled, resolve_event_details
)
from hierachain.api.storage.utils import is_cid_string


class EventType(ObjectType):
    entity_id = String()
    event_type = String()
    details = String()
    details_cid = String()
    details_nonce = String()
    is_offchain = Boolean()
    timestamp = Float()
    signature = String()

    async def resolve_details(self, _info, resolve_cid=True):
        if self._has_inline_details():
            return self.details

        if self._should_resolve_cid(resolve_cid):
            return await self._resolve_offchain_details()

        if self._has_cid_reference():
            return self._get_cid_reference()

        return self.details if hasattr(self, 'details') else None

    def _has_inline_details(self):
        details_val = getattr(self, 'details', None)
        if not details_val:
            return False
        details_str = details_val if isinstance(details_val, str) else str(details_val)
        return not is_cid_string(details_str)

    def _should_resolve_cid(self, resolve_cid):
        return hasattr(self, 'details_cid') and self.details_cid and resolve_cid

    def _has_cid_reference(self):
        return hasattr(self, 'details_cid') and self.details_cid

    async def _resolve_offchain_details(self):
        if not is_ipfs_enabled():
            return json.dumps({"error": "IPFS not enabled", "cid": self.details_cid})

        try:
            event_dict = self._build_event_dict()
            resolved = await resolve_event_details(event_dict, resolve=True)
            if 'details' in resolved:
                return json.dumps(resolved['details'])
        except Exception as e:
            return json.dumps({"error": f"Failed to resolve CID: {str(e)}", "cid": self.details_cid})

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
        return json.dumps({
            "cid": self.details_cid,
            "nonce": getattr(self, 'details_nonce', None),
            "note": "Set resolve_cid=true to fetch actual data"
        })

    def resolve_is_offchain(self, _info):
        return hasattr(self, 'details_cid') and bool(self.details_cid)


class BlockMetadataType(ObjectType):
    chain_name = String()
    events_count = Int()
    validator_signatures = List(String)


class BlockType(ObjectType):
    index = Int()
    hash = String()
    previous_hash = String()
    timestamp = Float()
    nonce = String()
    events = List(EventType)
    metadata = Field(BlockMetadataType)

    def resolve_events(self):
        if hasattr(self, 'events'):
            return self.events
        return []

    def resolve_metadata(self):
        if hasattr(self, 'metadata'):
            return self.metadata
        return None


class ChainStatusType(ObjectType):
    chain_name = String()
    block_count = Int()
    latest_block_index = Int()
    latest_block_hash = String()
    status = String()


class AddEventInput(InputObjectType):
    chain_name = String(required=True)
    entity_id = String(required=True)
    event_type = String(required=True)
    details = String()
