"""
SQLAlchemy Models for HieraChain Storage.

This module defines the database schema for the HieraChain Ledger,
allowing persistent storage of blocks, events, and world state.
"""

import time
from sqlalchemy import Column, Integer, String, Float, ForeignKey, JSON
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class BlockModel(Base):
    """
    Represents a block in the blockchain.
    """
    __tablename__ = 'blocks'

    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Block Header Data
    index = Column(Integer, nullable=False, index=True)
    hash = Column(String(64), unique=True, nullable=False, index=True)
    previous_hash = Column(String(64), nullable=False)
    timestamp = Column(Float, nullable=False, default=time.time)
    creator_id: str | None = Column(String(128), nullable=True)
    signature: str | None = Column(String(256), nullable=True)
    
    # Metadata (stored as JSON)
    metadata_json = Column(JSON, nullable=True)
    chain_name: str | None = Column(String(64), nullable=True, index=True)
    
    # Relationship to Events
    events = relationship(
        "EventModel", back_populates="block", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Block(index={self.index}, hash='{self.hash[:8]}...')>"


class EventModel(Base):
    """
    Represents a single event/transaction within a block.
    """
    __tablename__ = 'events'

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(64), unique=True, index=True) # If events have unique IDs
    
    # Link to Block
    block_hash = Column(String(64), ForeignKey('blocks.hash'), nullable=False)
    block = relationship("BlockModel", back_populates="events")
    
    # Event Data
    event_type = Column(String(50), nullable=False)
    timestamp = Column(Float, nullable=False)
    data = Column(JSON, nullable=False) # The full payload
    
    # Identity (Sender)
    sender_id: str | None = Column(String(64), nullable=True)
    
    # Context
    chain_name: str | None = Column(String(64), nullable=True, index=True)
    entity_id: str | None = Column(String(64), nullable=True, index=True)

    def __repr__(self):
        return f"<Event(type='{self.event_type}', block='{self.block_hash[:8]}...')>"


class ChainStateModel(Base):
    """
    Represents the current world state (Key-Value Store).
    Used for quick lookups of current ledger state without replaying all blocks.
    """
    __tablename__ = 'chain_state'

    key = Column(String(255), primary_key=True)
    value = Column(JSON, nullable=False)
    updated_at = Column(Float, default=time.time)
    last_block_hash = Column(String(64), nullable=True)

    def __repr__(self):
        return f"<ChainState(key='{self.key}')>"
