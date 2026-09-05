import time
import threading
import logging
from pathlib import Path
import orjson
import pyarrow as pa
import pyarrow.parquet as pq

_lock = threading.Lock()
_SCHEMA = pa.schema([("timestamp", pa.float64()), ("data", pa.string())])

def write_parquet_log(path: str | Path, record: dict) -> None:
    p = Path(path)
    if p.suffix != ".parquet":
        p = p.with_suffix(".parquet")
    p.parent.mkdir(parents=True, exist_ok=True)
    row = {"timestamp": float(record.get("timestamp", time.time())), "data": orjson.dumps(record, default=str).decode()}
    table = pa.table({"timestamp": [row["timestamp"]], "data": [row["data"]]}, schema=_SCHEMA)
    with _lock:
        if p.exists() and p.stat().st_size > 0:
            try:
                existing = pq.read_table(p, schema=_SCHEMA)
                table = pa.concat_tables([existing, table])
            except (OSError, pa.ArrowException, ValueError) as e:
                logging.getLogger(__name__).debug("Failed to read existing parquet log: %s", e)
        pq.write_table(table, p)

class ParquetLogHandler(logging.Handler):
    def __init__(self, parquet_path: str | Path):
        super().__init__()
        self.parquet_path = Path(parquet_path)
        if self.parquet_path.suffix != ".parquet":
            self.parquet_path = self.parquet_path.with_suffix(".parquet")

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            write_parquet_log(self.parquet_path, {"level": record.levelname, "logger": record.name, "message": msg, "created": record.created})
        except (OSError, pa.ArrowException, ValueError, TypeError):
            self.handleError(record)
