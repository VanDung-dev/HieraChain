from hierachain.adapters.database import (
    LedgerStorage,
    RedisStorageAdapter,
    SQLiteAdapter,
)


def test_sqlite_adapter_satisfies_ledger_storage_contract(tmp_path):
    adapter = SQLiteAdapter(str(tmp_path / "contract.db"))
    try:
        assert isinstance(adapter, LedgerStorage)
    finally:
        adapter.close()


def test_redis_adapter_satisfies_ledger_storage_contract():
    adapter = RedisStorageAdapter()
    assert isinstance(adapter, LedgerStorage)
