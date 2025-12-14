"""
Transaction Journal System for HieraChain.

This module provides a durability layer to ensure that transactions are
safely persisted to physical storage before being processed.
This protects against data loss during power failures, system crashes, or
rapid shutdowns.
"""

import os
import re
import logging
import struct
import json
from typing import Dict, Any, Generator
from pathlib import Path

import pyarrow as pa
from hierachain.core import schemas

logger = logging.getLogger(__name__)

class TransactionJournal:
    """
    Append-only journal for durable transaction logging using Apache Arrow.
    
    This class handles writing critical events to disk as serialized Arrow RecordBatches
    with synchronous flushing to guarantee persistence. Using Arrow provides faster
    IO and ensures schema consistency early in the pipeline.
    """
    
    @staticmethod
    def _validate_filename(name: str) -> None:
        """
        Validate filename against strict security rules (CWE-22).
        Allowed: alphanumeric, underscore, hyphen, single dot.
        """
        # Strict allowlist approach.
        pattern = r'^[a-zA-Z0-9_\-]+(\.[a-zA-Z0-9]+)?$'
        if not re.match(pattern, name):
            raise ValueError(f"Security: Invalid filename '{name}'. Allowed: [a-zA-Z0-9_-] and single optional extension.")
    
    def __init__(self, storage_dir: str = "data/journal", active_log_name: str = "current.log"):
        """
        Initialize the Transaction Journal.
        
        Args:
            storage_dir: Directory to store journal files.
            active_log_name: Name of the active journal file.
        """
        # Strictly validate storage_dir string BEFORE any filesystem resolution (CodeQL: py/path-injection)
        self._validate_storage_dir_input(storage_dir)

        self.storage_path = Path(storage_dir).resolve()

        data_root = Path("data").resolve()
        if not str(self.storage_path).startswith(str(data_root)):
            raise ValueError(f"Security: Storage path {self.storage_path} must be within {data_root}")

        safe_log_name = os.path.basename(active_log_name)
        self._validate_filename(safe_log_name)
        
        self.active_log_file = (self.storage_path / safe_log_name).resolve()

        try:
            self.active_log_file.relative_to(self.storage_path)
        except ValueError:
            raise ValueError(f"Security: Log file path {self.active_log_file} escapes storage directory {self.storage_path}")
        
        self._file_handle = None
        self._schema = schemas.get_event_schema()
        
        # Ensure directory exists
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Open the active log file
        self._open_journal()

    @staticmethod
    def _validate_storage_dir_input(storage_dir: str) -> None:
        """
        Validate the provided storage_dir string strictly before using it in any Path operations.
        - Disallow traversal tokens ('..')
        - Allow only alphanumeric, underscore, hyphen in each path component
        - Allow directory separators ('/' or '\\') between components
        """
        if not isinstance(storage_dir, str) or not storage_dir.strip():
            raise ValueError("Security: storage_dir must be a non-empty string")

        # Preserve the original error message expected by tests for traversal detection
        if ".." in storage_dir:
            raise ValueError("Security: Path traversal sequence ('..') not allowed in storage_dir.")

        # Allow only safe characters overall (components and separators)
        # Allow optional Windows drive prefix like "C:\\" or "D:/" at the beginning
        overall_pattern = r'^(?:[a-zA-Z]:[\\/])?[a-zA-Z0-9_\-/\\]+$'
        if not re.match(overall_pattern, storage_dir):
            raise ValueError("Security: storage_dir contains invalid characters. Allowed: [a-zA-Z0-9_-] and path separators")

        # Validate each component is safe and not empty / dot components
        # Strip Windows drive prefix from component validation if present
        _s = storage_dir
        m = re.match(r'^([a-zA-Z]:[\\/])(.*)$', _s)
        if m:
            _s = m.group(2)
        components = re.split(r'[\\/]+', _s)
        for comp in components:
            if comp in ('', '.', '..'):
                raise ValueError("Security: storage_dir contains invalid path components")
            if not re.match(r'^[a-zA-Z0-9_\-]+$', comp):
                raise ValueError("Security: storage_dir contains invalid path components")
        
    def _open_journal(self):
        """Open the journal file for appending (binary mode)."""
        try:
            # 'ab' mode for append binary
            self._file_handle = open(self.active_log_file, "ab")
        except Exception as e:
            logger.critical(f"Failed to open transaction journal: {e}")
            raise
            
    def _dict_to_arrow_batch(self, event_data: Dict[str, Any]) -> pa.RecordBatch:
        """
        Convert a raw event dictionary to an Arrow RecordBatch.
        Handles packing of extra fields into 'data' binary column.
        """
        # Create a copy to avoid modifying original
        ev = event_data.copy()
        
        # Prepare 'details' map
        details = ev.get('details')
        if isinstance(details, dict):
            ev['details'] = [(k, str(v)) for k, v in details.items()]
        elif details is None:
            ev['details'] = []
            
        # Pack extra fields into 'data' if they aren't part of the main schema
        if 'data' not in ev or not ev['data']:
            clean_event = {}
            for k, v in event_data.items():
                if k in ['entity_id', 'event', 'timestamp', 'data', 'details']:
                    continue
                if isinstance(v, bytes):
                    continue
                clean_event[k] = v
            
            if clean_event:
                ev['data'] = json.dumps(clean_event).encode('utf-8')
        
        # Ensure 'data' is bytes if None
        if 'data' not in ev:
            ev['data'] = b''

        # Create RecordBatch (size 1)
        try:
            batch = pa.RecordBatch.from_pylist([ev], schema=self._schema)
            return batch
        except Exception as e:
            logger.error(f"Schema conversion error for event {ev.get('event_id', 'unknown')}: {e}")
            raise

    def log_event(self, event_data: Dict[str, Any]) -> bool:
        """
        Durably log an event to the journal using Arrow format.
        
        Writes length-prefixed serialized batch: [Length (4 bytes)][Batch Bytes...]
        
        Args:
            event_data: The event dictionary to log.
            
        Returns:
            bool: True if logged and synced successfully.
        """
        if self._file_handle is None:
            self._open_journal()

        try:
            # 1. Convert to Arrow Batch
            batch = self._dict_to_arrow_batch(event_data)
            
            # 2. Serialize Batch to IPC message (buffer)
            serialized_batch = batch.serialize()
            
            # 3. Write Length Prefix (4 bytes, little endian)
            length_prefix = struct.pack('<I', len(serialized_batch))
            self._file_handle.write(length_prefix)
            
            # 4. Write Data
            self._file_handle.write(serialized_batch)
            
            # 5. Flush and Sync
            self._file_handle.flush()
            os.fsync(self._file_handle.fileno())
            
            return True
            
        except Exception as e:
            logger.critical(f"CRITICAL: Failed to write to transaction journal: {e}")
            return False

    def replay(self) -> Generator[Dict[str, Any], None, None]:
        """
        Replay all events from the journal.
        Reads binary Arrow batches and yields them as Dictionaries.
        """
        if not self.active_log_file.exists():
            return
            
        try:
            with open(self.active_log_file, "rb") as f:
                while True:
                    # Read Length Prefix
                    len_bytes = f.read(4)
                    if not len_bytes:
                        break # EOF
                    
                    if len(len_bytes) < 4:
                        logger.warning("Truncated journal file (incomplete length prefix). Stopping replay.")
                        break
                        
                    msg_len = struct.unpack('<I', len_bytes)[0]
                    
                    # Read Batch Data
                    batch_data = f.read(msg_len)
                    if len(batch_data) < msg_len:
                        logger.warning("Truncated journal file (incomplete batch data). Stopping replay.")
                        break
                        
                    try:
                        # Deserialize using IPC reader
                        batch = pa.ipc.read_record_batch(batch_data, self._schema)
                        
                        # Convert back to Python Dict
                        row = batch.to_pylist()[0]
                        
                        
                        # Unpack 'details' map back to dict
                        if row.get('details'):
                            row['details'] = dict(row['details'])
                            
                        # Unpack 'data' if it contains extra fields
                        if row.get('data'):
                            try:
                                extra_data = json.loads(row['data'])
                                if isinstance(extra_data, dict):
                                    for k, v in extra_data.items():
                                        if k not in row:
                                            row[k] = v
                            except (json.JSONDecodeError, TypeError):
                                pass
                        
                        yield row
                        
                    except Exception as arrow_err:
                        logger.error(f"Corrupted Arrow batch in journal: {arrow_err}")
                        continue
                        
        except Exception as e:
            logger.error(f"Error replaying journal: {e}")
            
    def close(self):
        """Close the journal file handle."""
        if self._file_handle:
            try:
                self._file_handle.flush()
                self._file_handle.close()
            except Exception as e:
                logger.error(f"Error closing journal: {e}")
            finally:
                self._file_handle = None

    def clear(self):
        """Clear the current journal."""
        self.close()
        try:
            # Truncate file (binary mode)
            with open(self.active_log_file, "wb") as f:
                pass
            # Reopen
            self._open_journal()
            logger.info("Transaction journal cleared (Arrow format).")
        except Exception as e:
            logger.error(f"Failed to clear journal: {e}")
