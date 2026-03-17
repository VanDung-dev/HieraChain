"""
SQL Storage Backend for HieraChain.

This module implements the persistent storage layer using SQLAlchemy.
It connects the application logic (OrderingService) with the database models.
"""

from typing import Any
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

from hierachain.storage.models import Base, BlockModel, EventModel, ChainStateModel
from hierachain.config.settings import settings
from hierachain.security.secure_logging import get_storage_logger

logger = get_storage_logger()


def _to_block_dict(block_model: BlockModel) -> dict[str, Any]:
    """Convert ORM model to dictionary format expected by HieraChain."""
    events_list = [e.data for e in block_model.events]
    # Safely get merkle_root from metadata
    metadata = block_model.metadata_json or {}
    return {
        "index": block_model.index,
        "hash": block_model.hash,
        "previous_hash": block_model.previous_hash,
        "timestamp": block_model.timestamp,
        "events": events_list,
        "metadata": metadata,
        "merkle_root": metadata.get("merkle_root")
    }


def _build_block_model(block_data: dict[str, Any]) -> BlockModel:
    """Create a BlockModel instance from block data dictionary."""
    # Preserve existing merkle_root in metadata if not provided
    metadata = block_data.get('metadata', {})
    if 'merkle_root' not in metadata and block_data.get('merkle_root'):
        metadata['merkle_root'] = block_data['merkle_root']
    
    return BlockModel(
        index=block_data['index'],
        hash=block_data['hash'],
        previous_hash=block_data['previous_hash'],
        timestamp=block_data['timestamp'],
        metadata_json=metadata,
        chain_name=block_data.get('chain_name')
    )


def _build_event_models(block_data: dict[str, Any]) -> list[EventModel]:
    """Create a list of EventModel instances from block data dictionary."""
    block_hash = block_data['hash']
    chain_name = block_data.get('chain_name')

    events = []
    for event_data in block_data.get('events', []):
        event_model = EventModel(
            block_hash=block_hash,
            event_id=event_data.get("event_id"),
            event_type=event_data.get('event', 'unknown'),
            timestamp=event_data.get('timestamp', 0.0),
            sender_id=event_data.get('sender', None),
            data=event_data,  # Store full JSON
            chain_name=chain_name,
            entity_id=event_data.get("entity_id")
        )
        events.append(event_model)
    return events


class SqlStorageBackend:
    """
    Persistent storage backend using SQL Database.
    Replaces the previous in-memory storage.
    """
    
    def __init__(self, connection_string: str = None):
        """
        Initialize the SQL Storage Backend.
        
        Args:
            connection_string: SQL connection string (e.g., sqlite:///hierachain.db)
                               Defaults to settings.DATABASE_URL
        """
        self.db_url = connection_string or settings.DATABASE_URL
        # Control SQL echo via settings to prevent schema leaks in production
        sql_echo = getattr(settings, 'LOG_SQL_DETAIL', False)
        self.engine = create_engine(self.db_url, echo=sql_echo)

        # Create all tables (if they don't exist)
        Base.metadata.create_all(self.engine)

        # Create thread-safe session factory
        self.Session = scoped_session(sessionmaker(bind=self.engine))

        logger.info("SqlStorageBackend initialized",
                    backend_type=self.db_url.split("://")[0]
                    if "://" in self.db_url else "unknown")

    def save_block(self, block_data: dict[str, Any]) -> bool:
        """
        Save a block and its events to the database.
        
        Args:
            block_data: Dictionary containing block data.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        session = self.Session()
        try:
            new_block = _build_block_model(block_data)
            new_block.events = _build_event_models(block_data)
            
            session.add(new_block)
            session.commit()
            
            if getattr(settings, 'LOG_SQL_DETAIL', False):
                logger.debug(
                    "Block saved to DB",
                    block_index=new_block.index,
                    events_count=len(new_block.events)
                )
            return True

        except Exception as e:
            session.rollback()
            
            # Idempotency: Treat unique constraint violation as success
            if "UNIQUE constraint" in str(e):
                return True
                
            logger.error("Database operation failed", operation="save_block")
            if getattr(settings, 'LOG_SQL_DETAIL', False):
                logger.debug("Save block error detail", error_type=type(e).__name__)
            return False
        finally:
            session.close()

    def get_event_by_id(self, event_id: str) -> dict[str, Any] | None:
        """
        Retrieve an event by its unique ID.
        
        Args:
            event_id: The unique event ID.
            
        Returns:
            Dictionary containing event data and status info, or None if not found.
        """
        session = self.Session()
        try:
            event_model = session.query(EventModel).filter_by(event_id=event_id).first()
            if not event_model:
                return None
            
            # Reconstruct status info
            return {
                "event_id": event_model.event_id,
                "status": "ordered",
                "block_hash": event_model.block_hash,
                "timestamp": event_model.timestamp,
                "data": event_model.data
            }
        finally:
            session.close()

    def get_latest_block(self, chain_name: str | None = None) -> dict[str, Any] | None:
        """Retrieve the latest block from DB."""
        session = self.Session()
        try:
            query = session.query(BlockModel)
            if chain_name:
                query = query.filter_by(chain_name=chain_name)
            block = query.order_by(BlockModel.index.desc()).first()
            if not block:
                return None
            return _to_block_dict(block)  # type: ignore[arg-type]
        finally:
            session.close()

    def get_block_by_index(
        self, index: int, chain_name: str | None = None
    ) -> dict[str, Any] | None:
        """Retrieve block by index."""
        session = self.Session()
        try:
            query = session.query(BlockModel).filter_by(index=index)
            if chain_name:
                query = query.filter_by(chain_name=chain_name)
            block = query.first()
            if not block:
                return None
            return _to_block_dict(block)  # type: ignore[arg-type]
        finally:
            session.close()

    def update_state(self, key: str, value: Any, last_block_hash: str):
        """Update a key-value in global state."""
        session = self.Session()
        try:
            session.merge(ChainStateModel(
                key=key,
                value=value,
                last_block_hash=last_block_hash
            ))
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error("Database operation failed", operation="update_state", key=key)
            if getattr(settings, 'LOG_SQL_DETAIL', False):
                logger.debug("Update state error detail", error_type=type(e).__name__)
        finally:
            session.close()

    def delete_chain(self, chain_name: str) -> bool:
        """Delete all blocks and events for a given chain from the database.
        
        Used for testing/cleanup to ensure a fresh state before test runs.
        
        Args:
            chain_name: The name of the chain to delete.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        session = self.Session()
        try:
            # Delete events first (foreign key dependency)
            events_deleted = session.query(EventModel).filter_by(
                chain_name=chain_name
            ).delete()
            blocks_deleted = session.query(BlockModel).filter_by(
                chain_name=chain_name
            ).delete()
            session.commit()
            logger.info(
                "Chain data deleted from DB",
                chain_name=chain_name,
                blocks_deleted=blocks_deleted,
                events_deleted=events_deleted
            )
            return True
        except Exception as e:
            session.rollback()
            logger.error("Failed to delete chain data", operation="delete_chain")
            if getattr(settings, 'LOG_SQL_DETAIL', False):
                logger.debug("Delete chain error detail", error_type=type(e).__name__)
            return False
        finally:
            session.close()

    def close(self):
        """Close connection pool."""
        self.Session.remove()
        self.engine.dispose()
