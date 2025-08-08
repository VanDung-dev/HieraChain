"""
File storage adapter for Hierarchical Blockchain Framework

This module provides a file-based storage implementation for the hierarchical blockchain system.
It stores blockchain data in a structured directory layout with separate folders for different
types of data
"""
import json
import os
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
import time
from datetime import datetime

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
        return self.chains_path / f"{chain_name}.json"
    
    def _get_block_file(self, chain_name: str, block_index: int) -> Path:
        """Get file path for a specific block"""
        chain_dir = self.blocks_path / chain_name
        chain_dir.mkdir(exist_ok=True)
        return chain_dir / f"block_{block_index:06d}.json"
    
    def _get_events_file(self, chain_name: str) -> Path:
        """Get file path for chain events index"""
        return self.events_path / f"{chain_name}_events.json"
    
    def store_chain_metadata(self, chain_name: str, chain_type: str, parent_chain: str = None, metadata: Dict = None):
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
    
    def store_block(self, chain_name: str, block_data: Dict):
        """Store block data"""
        try:
            # Add storage timestamp
            block_data_with_meta = block_data.copy()
            block_data_with_meta["stored_at"] = time.time()
            
            # Store block file
            block_file = self._get_block_file(chain_name, block_data["index"])
            with open(block_file, 'w') as f:
                json.dump(block_data_with_meta, f, indent=2)
            
            # Update events index
            self._update_events_index(chain_name, block_data)
            
            logger.debug(f"Stored block {block_data['index']} for chain {chain_name}")
            
        except Exception as e:
            logger.error(f"Failed to store block: {e}")
            raise
    
    def _update_events_index(self, chain_name: str, block_data: Dict):
        """Update events index for faster entity queries"""
        try:
            events_file = self._get_events_file(chain_name)
            
            # Load existing events index
            events_index = {}
            if events_file.exists():
                with open(events_file, 'r') as f:
                    events_index = json.load(f)
            
            # Add new events to index
            for event in block_data.get("events", []):
                entity_id = event.get("entity_id")
                if entity_id:
                    if entity_id not in events_index:
                        events_index[entity_id] = []
                    
                    events_index[entity_id].append({
                        "block_index": block_data["index"],
                        "event_type": event.get("event", event.get("event_type")),
                        "timestamp": event.get("timestamp", block_data["timestamp"]),
                        "block_hash": block_data["hash"]
                    })
            
            # Save updated index
            with open(events_file, 'w') as f:
                json.dump(events_index, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to update events index: {e}")
            # Don't raise - this is not critical for block storage
    
    def get_chain_metadata(self, chain_name: str) -> Optional[Dict]:
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
    
    def get_block(self, chain_name: str, block_index: int) -> Optional[Dict]:
        """Get a specific block"""
        try:
            block_file = self._get_block_file(chain_name, block_index)
            if not block_file.exists():
                return None
            
            with open(block_file, 'r') as f:
                return json.load(f)
                
        except Exception as e:
            logger.error(f"Failed to get block {block_index} for chain {chain_name}: {e}")
            return None
    
    def get_chain_blocks(self, chain_name: str, limit: int = None, offset: int = 0) -> List[Dict]:
        """Get blocks for a specific chain"""
        try:
            chain_dir = self.blocks_path / chain_name
            if not chain_dir.exists():
                return []
            
            # Get all block files and sort by index
            block_files = sorted(
                [f for f in chain_dir.glob("block_*.json")],
                key=lambda x: int(x.stem.split('_')[1])
            )
            
            # Apply offset and limit
            if offset:
                block_files = block_files[offset:]
            if limit:
                block_files = block_files[:limit]
            
            blocks = []
            for block_file in block_files:
                with open(block_file, 'r') as f:
                    block_data = json.load(f)
                    # Remove storage metadata
                    block_data.pop("stored_at", None)
                    blocks.append(block_data)
            
            return blocks
            
        except Exception as e:
            logger.error(f"Failed to get blocks for chain {chain_name}: {e}")
            return []
    
    def get_entity_events(self, entity_id: str, chain_name: str = None) -> List[Dict]:
        """Get all events for a specific entity"""
        try:
            events = []
            
            # Determine which chains to search
            chains_to_search = []
            if chain_name:
                chains_to_search = [chain_name]
            else:
                # Search all chains
                for events_file in self.events_path.glob("*_events.json"):
                    chain_name_from_file = events_file.stem.replace("_events", "")
                    chains_to_search.append(chain_name_from_file)
            
            # Search each chain's events index
            for search_chain in chains_to_search:
                events_file = self._get_events_file(search_chain)
                if not events_file.exists():
                    continue
                
                with open(events_file, 'r') as f:
                    events_index = json.load(f)
                
                if entity_id in events_index:
                    for event_ref in events_index[entity_id]:
                        # Get full event data from block
                        block_data = self.get_block(search_chain, event_ref["block_index"])
                        if block_data:
                            for event in block_data["events"]:
                                if event.get("entity_id") == entity_id:
                                    events.append({
                                        "chain_name": search_chain,
                                        "block_index": event_ref["block_index"],
                                        "event_type": event.get("event", event.get("event_type")),
                                        "timestamp": event.get("timestamp"),
                                        "details": event.get("details", {})
                                    })
            
            # Sort by timestamp
            events.sort(key=lambda x: x.get("timestamp", 0))
            return events
            
        except Exception as e:
            logger.error(f"Failed to get events for entity {entity_id}: {e}")
            return []
    
    def get_chain_stats(self, chain_name: str) -> Dict:
        """Get statistics for a specific chain"""
        try:
            chain_dir = self.blocks_path / chain_name
            if not chain_dir.exists():
                return {
                    "chain_name": chain_name,
                    "total_blocks": 0,
                    "total_events": 0,
                    "unique_entities": 0
                }
            
            block_files = list(chain_dir.glob("block_*.json"))
            total_blocks = len(block_files)
            total_events = 0
            unique_entities = set()
            
            for block_file in block_files:
                with open(block_file, 'r') as f:
                    block_data = json.load(f)
                    events = block_data.get("events", [])
                    total_events += len(events)
                    
                    for event in events:
                        entity_id = event.get("entity_id")
                        if entity_id:
                            unique_entities.add(entity_id)
            
            return {
                "chain_name": chain_name,
                "total_blocks": total_blocks,
                "total_events": total_events,
                "unique_entities": len(unique_entities)
            }
            
        except Exception as e:
            logger.error(f"Failed to get stats for chain {chain_name}: {e}")
            return {
                "chain_name": chain_name,
                "total_blocks": 0,
                "total_events": 0,
                "unique_entities": 0
            }
    
    def list_chains(self) -> List[str]:
        """List all stored chains"""
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
                    for block_file in chain_dir.glob("block_*.json"):
                        if block_file.stat().st_mtime < cutoff_time:
                            block_file.unlink()
                            logger.debug(f"Cleaned up old block file: {block_file}")
            
            logger.info(f"Cleaned up data older than {days_to_keep} days")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
    
    def get_storage_info(self) -> Dict:
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