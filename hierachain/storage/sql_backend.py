"""
SQL Storage Backend for HieraChain.

This module implements the persistent storage layer using SQLAlchemy.
It connects the application logic (OrderingService) with the database models.
"""

import logging
from typing import Any
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

from hierachain.storage.models import Base, BlockModel, EventModel, ChainStateModel
from hierachain.config.settings import settings

logger = logging.getLogger(__name__)


def _to_block_dict(block_model: BlockModel) -> dict[str, Any]:
    """Convert ORM model to dictionary format expected by HieraChain."""
    events_list = [e.data for e in block_model.events]
    return {
        "index": block_model.index,
        "hash": block_model.hash,
        "previous_hash": block_model.previous_hash,
        "timestamp": block_model.timestamp,
        "events": events_list,
        "metadata": block_model.metadata_json
    }


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
        self.engine = create_engine(self.db_url, echo=False)  # set echo=True for debug SQL
        
        # Create all tables (if they don't exist)
        Base.metadata.create_all(self.engine)
        
        # Create thread-safe session factory
        self.Session = scoped_session(sessionmaker(bind=self.engine))
        
        logger.info(f"SqlStorageBackend initialized with {self.db_url}")

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
            # 1. Create Block Record
            new_block = BlockModel(
                index=block_data['index'],
                hash=block_data['hash'],
                previous_hash=block_data['previous_hash'],
                timestamp=block_data['timestamp'],
                metadata_json=block_data.get('metadata', {}),
                chain_name=block_data.get('chain_name')
            )
            
            # 2. Create Event Records
            events = []
            for event_data in block_data.get('events', []):
                evt_id = event_data.get("event_id")
                # Extract entity_id from data if available
                entity_id = event_data.get("entity_id")
                
                event_model = EventModel(
                    block_hash=block_data['hash'],
                    event_id=evt_id,
                    event_type=event_data.get('event', 'unknown'),
                    timestamp=event_data.get('timestamp', 0.0),
                    sender_id=event_data.get('sender', None),
                    data=event_data, # Store full JSON
                    chain_name=block_data.get('chain_name'),
                    entity_id=entity_id
                )
                events.append(event_model)
            
            new_block.events = events
            
            session.add(new_block)
            try:
                session.commit()
                logger.debug(f"Saved Block #{new_block.index} ({len(events)} events) to DB.")
            except Exception as commit_error:
                # Handle unique constraint violation or other commit errors
                if "UNIQUE constraint" in str(commit_error):
                    session.rollback()
                    return True # Treat as success (idempotent)
                else:
                    raise commit_error
            return True
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to save block to DB: {e}")
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

    def get_block_by_index(self, index: int, chain_name: str | None = None) -> dict[str, Any] | None:
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
            logger.error(f"Failed to update state: {e}")
        finally:
            session.close()

    def close(self):
        """Close connection pool."""
        self.Session.remove()
        self.engine.dispose()
