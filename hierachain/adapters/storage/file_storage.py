"""
File storage adapter for HieraChain Framework

This module provides a file-based storage implementation for the HieraChain system.
It stores blockchain data in a structured directory layout with separate folders for different
types of data
"""

import json
import os
import logging
from typing import Optional, Union
from pathlib import Path
import time
import pyarrow as pa
import pyarrow.parquet as pq
import pyarrow.dataset as ds
import pyarrow.compute as pc

from hierachain.core.block import Block

logger = logging.getLogger(__name__)

class FileStorageAdapter:
    """File-based storage adapter for blockchain data"""
    
    def __init__(self, storage_path: str = "blockchain_data"):
        """
        Initialize file storage adapter
        
        Args:
            storage_path: Base directory for storing blockchain data
        """
        self.storage_path = Path(storage_path)
        self.chains_path = self.storage_path / "chains"
        self.blocks_path = self.storage_path / "blocks"
        self.events_path = self.storage_path / "events"
        self.proofs_path = self.storage_path / "proofs"
        
        self._create_directories()
        logger.info(f"File storage initialized at: {self.storage_path}")

    @staticmethod
    def _validate_filename(name: str) -> None:
        """
        Validate filename against strict security rules (CWE-22).
        Allowed: alphanumeric, underscore, hyphen.
        """
        import re
        if not re.match(r'^[a-zA-Z0-9_\-]+$', name):
            raise ValueError(f"Security: Invalid name '{name}'. Only alphanumeric, underscore, and hyphen are allowed.")
    
    def _create_directories(self):
        """Create necessary directories for storage"""
        directories = [
            self.storage_path,
            self.chains_path,
            self.blocks_path,
            self.events_path,
            self.proofs_path
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def _get_chain_file(self, chain_name: str) -> Path:
        """Get file path for chain metadata"""
        self._validate_filename(chain_name)
        return self.chains_path / f"{chain_name}.json"
    
    def _get_block_file(self, chain_name: str, block_index: int) -> Path:
        """Get file path for a specific block (Parquet)"""
        self._validate_filename(chain_name)
        chain_dir = self.blocks_path / chain_name
        chain_dir.mkdir(exist_ok=True)
        return chain_dir / f"block_{block_index:06d}.parquet"
    
    def _get_events_dir(self, chain_name: str) -> Path:
        """Get directory for chain events dataset"""
        self._validate_filename(chain_name)
        path = self.events_path / chain_name
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    def store_chain_metadata(self, chain_name: str, chain_type: str, parent_chain: str = None, metadata: dict = None):
        """Store chain metadata"""
        try:
            chain_data = {
                "name": chain_name,
                "type": chain_type,
                "parent_chain": parent_chain,
                "metadata": metadata or {},
                "created_at": time.time(),
                "updated_at": time.time()
            }
            
            chain_file = self._get_chain_file(chain_name)
            with open(chain_file, 'w') as f:
                json.dump(chain_data, f, indent=2)
            
            logger.debug(f"Stored chain metadata: {chain_name}")
            
        except Exception as e:
            logger.error(f"Failed to store chain metadata {chain_name}: {e}")
            raise
    
    def store_block(self, chain_name: str, block_data: Union[dict, Block]):
        """
        Store block data using Parquet for high performance.
        
        Args:
            chain_name: Name of the chain
            block_data: Block object or Dictionary
        """
        try:
            # Convert to Block object if it's a dict (inefficient but safe fallback)
            if isinstance(block_data, dict):
                # We assume it follows Block.to_dict() structure
                block = Block.from_dict(block_data)
            else:
                block = block_data

            # Prepare metadata for the Parquet file
            # Parquet metadata keys must be bytes or strings
            metadata = {
                b'index': str(block.index).encode(),
                b'timestamp': str(block.timestamp).encode(),
                b'previous_hash': str(block.previous_hash).encode(),
                b'nonce': str(block.nonce).encode(),
                b'hash': str(block.hash).encode(),
                b'stored_at': str(time.time()).encode()
            }
            
            # Get the Arrow Table from the block
            table = block.events
            
            # Merge existing schema metadata with block header metadata
            existing_meta = table.schema.metadata or {}
            combined_meta = {**existing_meta, **metadata}
            
            # Create a new table with updated metadata
            table_with_meta = table.replace_schema_metadata(combined_meta)
            
            # Store block file as Parquet with optimized compression
            block_file = self._get_block_file(chain_name, block.index)
            pq.write_table(
                table_with_meta,
                block_file,
                compression='zstd',
                compression_level=3,
                use_dictionary=True,
                write_statistics=True
            )

            self._update_events_index(chain_name, block.to_dict())
            
            logger.debug(f"Stored block {block.index} for chain {chain_name} as Parquet")
            
        except Exception as e:
            logger.error(f"Failed to store block: {e}")
            raise
    
    def _update_events_index(self, chain_name: str, block_data: dict):
        """
        Update events index using Arrow Dataset (Append-only).
        Writes a small parquet file for the block's events.
        """
        try:
            events_list = block_data.get("events", [])
            
            if not events_list:
                return

            # Extract columns for index
            indices = []
            for event in events_list:
                entity_id = event.get("entity_id")
                if entity_id:
                    indices.append({
                        "entity_id": entity_id,
                        "block_index": block_data["index"],
                        "event_type": event.get("event", event.get("event_type", "unknown")),
                        "timestamp": event.get("timestamp", block_data["timestamp"]),
                        "block_hash": block_data["hash"]
                    })
            
            if not indices:
                return

            # Create Table
            schema = pa.schema([
                ("entity_id", pa.string()),
                ("block_index", pa.int64()),
                ("event_type", pa.string()),
                ("timestamp", pa.float64()),
                ("block_hash", pa.string())
            ])
            
            table = pa.Table.from_pylist(indices, schema=schema)
            
            # Write partition file
            events_dir = self._get_events_dir(chain_name)
            # Use block index to ensure unique filenames and easy ordering
            file_path = events_dir / f"events_{block_data['index']:09d}.parquet"
            
            pq.write_table(
                table,
                file_path,
                compression='zstd',
                compression_level=3,
                use_dictionary=True,
                write_statistics=True
            )
                 
        except Exception as e:
            logger.error(f"Failed to update events index: {e}")
            # Don't raise - this is not critical for block storage
    
    def get_chain_metadata(self, chain_name: str) -> Optional[dict]:
        """Get chain metadata"""
        try:
            chain_file = self._get_chain_file(chain_name)
            if not chain_file.exists():
                return None
            
            with open(chain_file, 'r') as f:
                return json.load(f)
                
        except Exception as e:
            logger.error(f"Failed to get chain metadata {chain_name}: {e}")
            return None
    
    def get_block(self, chain_name: str, block_index: int) -> Optional[dict]:
        """
        Get a specific block.
        Returns a Dictionary suitable for Block.from_dict(), with 'events' as a pyarrow.Table.
        """
        try:
            block_file = self._get_block_file(chain_name, block_index)
            if not block_file.exists():
                return None
            
            # Read Parquet file
            table = pq.read_table(block_file)
            
            # Extract metadata
            meta = table.schema.metadata
            if not meta:
                logger.warning(f"Block {block_index} missing metadata in Parquet file")
                return None
                
            # Decode metadata
            # Keys are bytes, values are bytes
            index = int(meta.get(b'index', b'0'))
            timestamp = float(meta.get(b'timestamp', b'0.0'))
            previous_hash = meta.get(b'previous_hash', b'').decode('utf-8')
            nonce = int(meta.get(b'nonce', b'0'))
            block_hash = meta.get(b'hash', b'').decode('utf-8')

            block_data = {
                "index": index,
                "events": table,  # Zero-copy access
                "timestamp": timestamp,
                "previous_hash": previous_hash,
                "nonce": nonce,
                "hash": block_hash
            }
            
            return block_data
                
        except Exception as e:
            logger.error(f"Failed to get block {block_index} for chain {chain_name}: {e}")
            return None
    
    def get_chain_blocks(self, chain_name: str, limit: int = None, offset: int = 0) -> list[dict]:
        """Get blocks for a specific chain"""
        try:
            self._validate_filename(chain_name)
            chain_dir = self.blocks_path / chain_name
            if not chain_dir.exists():
                return []
            
            # Get all block files and sort by index
            block_files = sorted(
                [f for f in chain_dir.glob("block_*.parquet")],
                key=lambda x: int(x.stem.split('_')[1])
            )
            
            # Apply offset and limit
            if offset:
                block_files = block_files[offset:]
            if limit:
                block_files = block_files[:limit]
            
            blocks = []
            for block_file in block_files:
                try:
                    table = pq.read_table(block_file)
                    meta = table.schema.metadata
                    
                    if meta:
                        block_data = {
                            "index": int(meta.get(b'index', b'0')),
                            "events": table,
                            "timestamp": float(meta.get(b'timestamp', b'0.0')),
                            "previous_hash": meta.get(b'previous_hash', b'').decode('utf-8'),
                            "nonce": int(meta.get(b'nonce', b'0')),
                            "hash": meta.get(b'hash', b'').decode('utf-8')
                        }
                        blocks.append(block_data)
                except Exception as e:
                    logger.warning(f"Failed to read block file {block_file}: {e}")
                    continue
            
            return blocks
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to get blocks for chain {chain_name}: {e}")
            return []
    
    def get_entity_events(self, entity_id: str, chain_name: str = None) -> list[dict]:
        """
        Get all events for a specific entity using Arrow Dataset.
        """
        try:
            events = []
            
            # Determine which chains to search
            chains_to_search = []
            if chain_name:
                chains_to_search = [chain_name]
            else:
                # Search all chains (directories in events_path)
                chains_to_search = [p.name for p in self.events_path.iterdir() if p.is_dir()]
            
            # Search each chain's events dataset
            for search_chain in chains_to_search:
                events_dir = self._get_events_dir(search_chain)
                
                try:
                    # Load dataset
                    dataset = ds.dataset(events_dir, format="parquet")
                    filtered_table = dataset.to_table(filter=pc.field("entity_id") == entity_id)
                    sorted_table = filtered_table.sort_by([("timestamp", "ascending")])
                    index_records = sorted_table.to_pylist()
                    
                    for record in index_records:
                        # Fetch full block
                        block_data = self.get_block(search_chain, record["block_index"])
                        if block_data:

                            events_table = block_data["events"]
                            expr = (pc.field("entity_id") == entity_id) & \
                                   (pc.field("timestamp") == record["timestamp"])
                            subset = events_table.filter(expr)
                            subset_rows = Block._table_to_list_of_dicts(subset)
                            
                            for full_event in subset_rows:
                                events.append({
                                    "chain_name": search_chain,
                                    "block_index": record["block_index"],
                                    "event_type": full_event.get("event"),
                                    "timestamp": full_event.get("timestamp"),
                                    "details": full_event.get("details", {})
                                })
                                
                except Exception as e:
                    pass
            
            # Final sort by timestamp across chains
            events.sort(key=lambda x: x.get("timestamp", 0))
            return events
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to get events for entity {entity_id}: {e}")
            return []
    
    def get_chain_stats(self, chain_name: str) -> dict:
        """Get statistics for a specific chain using Arrow Datasets"""
        try:
            self._validate_filename(chain_name)
            chain_dir = self.blocks_path / chain_name
            events_dir = self._get_events_dir(chain_name)
            
            if not chain_dir.exists():
                return {
                    "chain_name": chain_name,
                    "total_blocks": 0,
                    "total_events": 0,
                    "unique_entities": 0
                }
            
            # Count blocks (files)
            total_blocks = len(list(chain_dir.glob("block_*.parquet")))
            
            # Count events and unique entities using dataset
            total_events = 0
            unique_entities_count = 0
            
            if events_dir.exists() and any(events_dir.iterdir()):
                try:
                    dataset = ds.dataset(events_dir, format="parquet")
                    
                    # Total events = count rows
                    total_events = dataset.count_rows()
                    
                    unique_entities_count = len(
                        dataset.to_table(columns=['entity_id'])
                        .column('entity_id')
                        .unique()
                    )
                except Exception:
                    pass
            
            return {
                "chain_name": chain_name,
                "total_blocks": total_blocks,
                "total_events": total_events,
                "unique_entities": unique_entities_count
            }
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to get stats for chain {chain_name}: {e}")
            return {
                "chain_name": chain_name,
                "total_blocks": 0,
                "total_events": 0,
                "unique_entities": 0
            }
    
    def list_chains(self) -> list[str]:
        """list all stored chains"""
        try:
            chain_files = self.chains_path.glob("*.json")
            return [f.stem for f in chain_files]
        except Exception as e:
            logger.error(f"Failed to list chains: {e}")
            return []
    
    def cleanup_old_data(self, days_to_keep: int = 30):
        """Clean up old data files"""
        try:
            cutoff_time = time.time() - (days_to_keep * 24 * 60 * 60)
            
            # Clean up old block files
            for chain_dir in self.blocks_path.iterdir():
                if chain_dir.is_dir():
                    for block_file in chain_dir.glob("block_*.parquet"):
                        if block_file.stat().st_mtime < cutoff_time:
                            block_file.unlink()
                            logger.debug(f"Cleaned up old block file: {block_file}")
            
            logger.info(f"Cleaned up data older than {days_to_keep} days")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
    
    def get_storage_info(self) -> dict:
        """Get storage information"""
        try:
            total_size = 0
            file_count = 0
            
            for root, dirs, files in os.walk(self.storage_path):
                for file in files:
                    file_path = Path(root) / file
                    total_size += file_path.stat().st_size
                    file_count += 1
            
            return {
                "storage_path": str(self.storage_path),
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "file_count": file_count,
                "chains_count": len(self.list_chains())
            }
            
        except Exception as e:
            logger.error(f"Failed to get storage info: {e}")
            return {}

    def get_entity_events_optimized(self, entity_id: str, chain_name: str = None, columns: list[str] = None) -> list[dict]:
        """
        Get events with column pruning for better performance.
        
        Args:
            entity_id: Entity to query
            chain_name: Optional chain filter
            columns: Columns to return (None = all). 
                     Common columns: ['entity_id', 'event_type', 'timestamp', 'block_index']
                     
        Returns:
            List of event records with only requested columns
        """
        try:
            events = []
            
            # Determine which chains to search
            chains_to_search = []
            if chain_name:
                chains_to_search = [chain_name]
            else:
                chains_to_search = [
                    p.name for p in self.events_path.iterdir() if p.is_dir()
                ]
            
            for search_chain in chains_to_search:
                events_dir = self._get_events_dir(search_chain)
                
                try:
                    dataset = ds.dataset(events_dir, format="parquet")
                    
                    # Apply column pruning - only read required columns
                    projection = columns if columns else None
                    
                    # Filter and project in one operation
                    filtered_table = dataset.to_table(
                        filter=pc.field("entity_id") == entity_id,
                        columns=projection
                    )
                    
                    # Sort by timestamp
                    sorted_table = filtered_table.sort_by([("timestamp", "ascending")])
                    
                    for record in sorted_table.to_pylist():
                        record["chain_name"] = search_chain
                        events.append(record)
                        
                except Exception:
                    continue
            
            # Final sort across chains
            events.sort(key=lambda x: x.get("timestamp", 0))
            return events
            
        except Exception as e:
            logger.error(f"Failed to get optimized events for entity {entity_id}: {e}")
            return []


class BatchBlockWriter:
    """
    Optimized batch writer for multiple blocks.
    
    Uses buffering for better I/O performance when writing
    multiple blocks in sequence.
    
    Usage:
        with BatchBlockWriter(storage, 'my_chain', batch_size=50) as writer:
            for block in blocks:
                writer.add(block)
    """
    
    def __init__(
        self,
        storage: FileStorageAdapter,
        chain_name: str,
        batch_size: int = 100
    ):
        """
        Initialize batch writer.
        
        Args:
            storage: FileStorageAdapter instance
            chain_name: Name of chain to write to
            batch_size: Number of blocks to buffer before flush
        """
        self.storage = storage
        self.chain_name = chain_name
        self.batch_size = batch_size
        self._buffer: list[Block] = []
        self._stats = {
            "blocks_written": 0,
            "events_written": 0,
            "flush_count": 0,
            "total_time_ms": 0.0
        }
    
    def add(self, block: Block) -> None:
        """
        Add block to buffer.
        
        Args:
            block: Block to add
        """
        self._buffer.append(block)
        if len(self._buffer) >= self.batch_size:
            self.flush()
    
    def flush(self) -> None:
        """Write all buffered blocks to storage."""
        if not self._buffer:
            return
        
        start_time = time.time()
        
        for block in self._buffer:
            self.storage.store_block(self.chain_name, block)
            self._stats["blocks_written"] += 1
            self._stats["events_written"] += len(block.events)
        
        elapsed_ms = (time.time() - start_time) * 1000
        self._stats["flush_count"] += 1
        self._stats["total_time_ms"] += elapsed_ms
        
        logger.debug(
            f"Flushed {len(self._buffer)} blocks in {elapsed_ms:.2f}ms"
        )
        
        self._buffer.clear()
    
    def get_stats(self) -> dict:
        """
        Get write statistics.
        
        Returns:
            Dictionary with blocks_written, events_written, 
            flush_count, total_time_ms, avg_time_per_block_ms
        """
        stats = self._stats.copy()
        if stats["blocks_written"] > 0:
            stats["avg_time_per_block_ms"] = (
                stats["total_time_ms"] / stats["blocks_written"]
            )
        else:
            stats["avg_time_per_block_ms"] = 0.0
        return stats
    
    def __enter__(self) -> 'BatchBlockWriter':
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.flush()
