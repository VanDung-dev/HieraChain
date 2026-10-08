"""Standard-library JSON with finite numbers and deterministic digest bytes."""

import json
import math
from collections.abc import Callable
from typing import Any, NoReturn


def dumps_json(
    value: Any,
    *,
    sort_keys: bool = False,
    indent: int | None = None,
    default: Callable[[Any], Any] | None = None,
) -> str:
    """Encode JSON values without silently converting non-finite numbers."""
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, sort_keys=sort_keys,
        separators=(",", ":") if indent is None else None, indent=indent, default=default,
    )


def _reject_constant(value: str) -> NoReturn:
    raise json.JSONDecodeError("Non-finite numbers are not valid JSON", value, 0)


def _parse_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        _reject_constant(value)
    return number


def loads_json(value: str | bytes | bytearray) -> Any:
    """Decode JSON, preserving Python integers and rejecting non-finite floats."""
    return json.loads(value, parse_constant=_reject_constant, parse_float=_parse_float)


def dumps_canonical_json(value: Any, *, default: Callable[[Any], Any] | None = None) -> bytes:
    """Encode sorted, compact JSON for hashes and signatures."""
    return dumps_json(value, sort_keys=True, default=default).encode("utf-8")
