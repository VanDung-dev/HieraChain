"""
Client for communicating with the HieraChain Engine using Arrow IPC over TCP.

Provides helpers to serialize batches of `Transaction` objects into an
Apache Arrow IPC stream, send length-prefixed messages over a TCP socket,
and receive responses. Supports context-manager semantics for automatic
connect/close.
"""


import socket
import struct
import pyarrow as pa
import logging

# Import Transaction from types to decouple integration modules
from hierachain.integration.types import Transaction
from hierachain.core.schemas import get_transaction_schema

logger = logging.getLogger(__name__)

class ArrowClient:
    """
    Client for communicating with HieraChain Engine via Arrow IPC over TCP.
    """

    def __init__(self, host: str = "localhost", port: int = 50051):
        self.host = host
        self.port = port
        self.sock: socket.socket | None = None

    def connect(self):
        """Establish TCP connection to the server."""
        if self.sock:
            return
        
        try:
            self.sock = socket.create_connection((self.host, self.port))
            logger.info(f"Connected to Arrow Server at {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect to {self.host}:{self.port}: {e}")
            raise

    def close(self):
        """Close the TCP connection."""
        if self.sock:
            self.sock.close()
            self.sock = None
            logger.info("Disconnected from Arrow Server")

    def submit_batch(self, transactions: list[Transaction]) -> bytes:
        """
        Submit a batch of transactions to the engine.
        
        Args:
            transactions: List of Transaction objects.
            
        Returns:
            Response bytes from server (currently "OK").
        """
        if not self.sock:
            self.connect()

        # 1. Convert Transactions to Arrow Table/RecordBatch
        table = self._transactions_to_arrow(transactions)
        
        # 2. Serialize to IPC Stream
        sink = pa.BufferOutputStream()
        # Use new_stream for IPC Stream format (Schema + Batches)
        with pa.ipc.new_stream(sink, table.schema) as writer:
            writer.write_table(table)
        
        ipc_bytes = sink.getvalue().to_pybytes()
        
        # 3. Send Message (Length + Data)
        length = len(ipc_bytes)
        try:
            # Send 4-byte length (Big Endian)
            self.sock.sendall(struct.pack('>I', length))
            # Send payload
            self.sock.sendall(ipc_bytes)
            
            # 4. Receive Response
            # Read 4-byte length
            len_bytes = self._recv_all(4)
            if not len_bytes:
                raise ConnectionError("Server closed connection")
                
            resp_len = struct.unpack('>I', len_bytes)[0]
            
            # Read payload
            resp_data = self._recv_all(resp_len)
            return resp_data
            
        except BrokenPipeError:
            self.close()
            raise

    def _recv_all(self, n: int) -> bytearray:
        """Helper to receive exactly n bytes."""
        data = bytearray()
        while len(data) < n:
            packet = self.sock.recv(n - len(data))
            if not packet:
                return None
            data.extend(packet)
        return data

    def _transactions_to_arrow(self, transactions: list[Transaction]) -> pa.Table:
        """Convert list of Transactions to Arrow Table."""
        
        # Define schema matches core expectations
        # For now, let's map the Transaction fields
        # Note: 'details' is a map/dict, which can be handled as MapType or Struct
        
        tx_ids = []
        entity_ids = []
        event_types = []
        arrow_payloads = []
        signatures = []
        timestamps = []
        # Complex types like Map might be tricky, let's start with basic fields + strict schema if needed
        # Or let pyarrow infer for now, but explicit is better for cross-lang
        
        for tx in transactions:
            tx_ids.append(tx.tx_id)
            entity_ids.append(tx.entity_id)
            event_types.append(tx.event_type)
            arrow_payloads.append(tx.arrow_payload)
            signatures.append(tx.signature)
            timestamps.append(tx.timestamp) # Standardize on float64 seconds matching Schema
            
            # Details: map[string]string -> List of structs or Map type
            # For simplicity in this phase, ignoring details or handling simply?
            # Let's Skip details for complex map handling for a moment or add as binary json?
            # Let's try to stick to primitives for the first pass or implementation plan doesn't specify schema details.
        
        
        # Use standardized schema
        schema = get_transaction_schema()
        
        # Construct arrays matching the schema fields
        arrays = [
            pa.array(tx_ids, pa.string()),
            pa.array(entity_ids, pa.string()),
            pa.array(event_types, pa.string()),
            pa.array(arrow_payloads, pa.binary()),
            pa.array(signatures, pa.string()),
            pa.array(timestamps, pa.float64()),
            pa.array([None] * len(transactions), pa.map_(pa.string(), pa.string())),
        ]
        
        return pa.Table.from_arrays(arrays, schema=schema)

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
