"""
Logging configuration for HieraChain.

Supports two output formats, selected via the ``HRC_LOG_FORMAT`` environment variable:

* ``text`` (default) — human-readable, coloured uvicorn-style output.
* ``json``           — machine-readable structured output suitable for Elastic /
                       Cloud Logging aggregators.
"""

import json
import logging
import os


class _JsonFormatter(logging.Formatter):
    """
    Emit each log record as a single JSON line with a standard set of fields.

    Fields: timestamp (ISO-8601), level, logger, message, request_id (if set).
    Any *extra* key/value pairs passed via ``logging.info("msg", extra={...})`` are
    merged into the top-level JSON object.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include request_id injected by server middleware when present
        if hasattr(record, "request_id"):
            payload["request_id"] = getattr(record, "request_id")

        # Merge any user-supplied extra fields (excluding internal logging attrs)
        _SKIP = frozenset(logging.LogRecord.__dict__) | {
            "message", "asctime", "request_id"
        }
        for key, value in record.__dict__.items():
            if key not in _SKIP and not key.startswith("_"):
                try:
                    json.dumps(value)  # guard: only include JSON-serialisable values
                    payload[key] = value
                except (TypeError, ValueError):
                    payload[key] = str(value)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


_TEXT_LOGGING_CONFIG: dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": "%(levelprefix)s %(name)-30s %(message)s",
            "use_colors": None,
        },
        "access": {
            "()": "uvicorn.logging.AccessFormatter",
            "fmt": (
                '%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s'
            ),
        },
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)-30s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
        "access": {
            "formatter": "access",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
        "console": {
            "formatter": "standard",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
    },
    "loggers": {
        "hierachain": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "uvicorn.error": {"level": "INFO"},
        "uvicorn.access": {"handlers": ["access"], "level": "INFO", "propagate": False},
    },
}

_JSON_LOGGING_CONFIG: dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": f"{__name__}._JsonFormatter",
        },
    },
    "handlers": {
        "json_stdout": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "hierachain": {"handlers": ["json_stdout"], "level": "INFO", "propagate": False},
        "uvicorn": {"handlers": ["json_stdout"], "level": "INFO", "propagate": False},
        "uvicorn.error": {"level": "INFO"},
        "uvicorn.access": {
            "handlers": ["json_stdout"], "level": "INFO", "propagate": False
        },
    },
}


def _pick_config() -> dict:
    fmt = os.getenv("HRC_LOG_FORMAT", "text").strip().lower()
    return _JSON_LOGGING_CONFIG if fmt == "json" else _TEXT_LOGGING_CONFIG


LOGGING_CONFIG: dict = _pick_config()
