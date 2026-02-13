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


def _transactions_to_arrow(transactions: list[Transaction]) -> pa.Table:
    """
    Chuyển đổi danh sách các đối tượng Transaction thành Apache Arrow Table.

    Hàm này chuẩn hóa dữ liệu giao dịch để phù hợp với schema yêu cầu bởi HieraChain Engine,
    bao gồm cả các trường metadata (details) và các trường ZK Proof mới được thêm vào.

    Args:
        transactions: Danh sách các giao dịch cần chuyển đổi.

    Returns:
        pa.Table: Bảng dữ liệu định dạng Arrow.
    """
    schema = get_transaction_schema()

    if not transactions:
        # Trả về bảng trống với schema đúng nếu không có dữ liệu
        return pa.Table.from_batches([], schema=schema)

    # Xây dựng từ điển dữ liệu để sử dụng với from_pydict
    # Điều này đảm bảo tất cả các trường trong TRANSACTION_SCHEMA đều được cung cấp
    data = {
        "tx_id": [tx.tx_id for tx in transactions],
        "entity_id": [tx.entity_id for tx in transactions],
        "event_type": [tx.event_type for tx in transactions],
        "arrow_payload": [tx.arrow_payload for tx in transactions],
        "signature": [tx.signature for tx in transactions],
        "timestamp": [tx.timestamp for tx in transactions],
        "details": [tx.details if tx.details else None for tx in transactions],
        "zk_proof": [None] * len(transactions),
        "zk_public_inputs": [None] * len(transactions),
    }

    return pa.Table.from_pydict(data, schema=schema)


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
        table = _transactions_to_arrow(transactions)
        
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

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
