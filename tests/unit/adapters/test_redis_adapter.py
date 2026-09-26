from types import SimpleNamespace
from unittest.mock import patch

import redis
from redis.connection import Connection

from hierachain.adapters.database.redis_adapter import RedisChainManager
from hierachain.hierarchical.main_chain.base import MainChain


def test_store_main_chain_encodes_hset_metadata_without_none_values() -> None:
    client = redis.Redis()
    connection = Connection()
    encoded_commands = []

    def encode_command(*args, **kwargs):
        encoded_commands.append((args, b"".join(connection.pack_command(*args))))
        return 1

    manager = RedisChainManager(SimpleNamespace(client=client))
    with patch.object(client, "_execute_command", side_effect=encode_command):
        assert manager.store_chain(MainChain("main")) is True

    assert len(encoded_commands) == 1
    args, encoded = encoded_commands[0]
    assert args[0] == "HSET"
    fields = dict(zip(args[2::2], args[3::2]))
    assert fields["name"] == "main"
    assert fields["chain_type"] == "main"
    assert "domain_type" not in fields
    assert b"domain_type" not in encoded
