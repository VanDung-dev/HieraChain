"""Path validation and file-descriptor helpers for the event journal."""

import os
import re
import struct
from pathlib import Path
from typing import BinaryIO, Literal

from hierachain.error_mitigation.journal_constants import (
    _JOURNAL_MAX_FRAME_SIZE,
)


def _validate_path_component(comp: str) -> None:
    """Validate a single path component for security."""
    if comp in ("", ".", ".."):
        raise ValueError("Security: storage_dir contains invalid path components")
    if not re.match(r"^[a-zA-Z0-9_\-~.]+$", comp):
        raise ValueError(f"Security: storage_dir invalid component: {comp}")


def _get_clean_path_input(storage_dir: str) -> str:
    """Strip Windows drive prefix and leading slashes."""
    _s = storage_dir
    m = re.match(r"^([a-zA-Z]:[\\/])(.*)$", _s)
    if m:
        _s = m.group(2)
    return _s.lstrip("/")


def _validate_storage_dir_input(storage_dir: str) -> None:
    """
    Validate the provided storage_dir string strictly.
    - Disallow traversal tokens ('..')
    - Allow only alphanumeric, underscore, hyphen in each path component
    - Allow directory separators ('/' or '\\') between components
    """
    if not isinstance(storage_dir, str) or not storage_dir.strip():
        raise ValueError("Security: storage_dir must be a non-empty string")

    # Preserve the original error message expected by tests for traversal detection
    if ".." in storage_dir:
        raise ValueError("Security: Path traversal sequence ('..') not allowed.")

    # Allow only safe characters overall (components and separators)
    overall_pattern = r"^(?:[a-zA-Z]:[\\/]|/)?[a-zA-Z0-9_\-~./\\]+$"
    if not re.match(overall_pattern, storage_dir):
        raise ValueError(
            "Security: storage_dir contains invalid characters. "
            "Allowed: [a-zA-Z0-9_-], dot, tilde, and path separators"
        )

    # Validate each component is safe
    _s = _get_clean_path_input(storage_dir)
    components = re.split(r"[\\/]+", _s)
    for comp in components:
        _validate_path_component(comp)


def _build_absolute_storage_path(data_root: Path, abs_path_str: str) -> Path:
    """Build a safe path from an absolute string within data_root."""
    # Must be within data_root
    if os.path.commonpath([str(data_root), abs_path_str]) != str(data_root):
        raise ValueError(
            "Security: Storage path %s must be within %s",
            abs_path_str, data_root
        )
    # Compute relative path string safely
    try:
        rel_str = os.path.relpath(abs_path_str, start=str(data_root))
    except (ValueError, OSError):
        rel_str = "."

    rel_parts = [] if rel_str in (".", "") else re.split(r"[\\/]+", rel_str)
    rel_parts = [p for p in rel_parts if p]

    # Validate each component
    safe_parts = []
    for comp in rel_parts:
        if comp in (".", "..") or not re.match(r"^[a-zA-Z0-9_\-~.]+$", comp):
            raise ValueError("Security: storage_dir invalid path components")
        safe_parts.append(comp)

    return data_root.joinpath(*safe_parts) if safe_parts else data_root


def _build_storage_path(data_root: Path, storage_dir: str) -> Path:
    """
    Build a safe storage path anchored strictly to data_root using sanitized
    components.
    """
    # Handle absolute paths explicitly
    if os.path.isabs(storage_dir):
        return _build_absolute_storage_path(data_root, os.path.normpath(storage_dir))

    # Relative path case
    _s = _get_clean_path_input(storage_dir)
    comps = [c for c in re.split(r"[\\/]+", _s) if c]
    if comps and comps[0].lower() == "data":
        comps = comps[1:]

    safe_parts = []
    for comp in comps:
        if comp in (".", "..") or not re.match(r"^[a-zA-Z0-9_\-~.]+$", comp):
            raise ValueError("Security: storage_dir invalid path components")
        safe_parts.append(comp)

    return data_root.joinpath(*safe_parts) if safe_parts else data_root


def _read_next_batch(f: BinaryIO) -> bytes | None:
    """Read the next length-prefixed batch from file."""
    len_bytes = f.read(4)
    if not len_bytes:
        return None

    if len(len_bytes) < 4:
        raise ValueError("Truncated journal file (incomplete length prefix)")

    msg_len = struct.unpack("<I", len_bytes)[0]
    if msg_len > _JOURNAL_MAX_FRAME_SIZE:
        raise ValueError(f"Journal frame length {msg_len} exceeds maximum")
    batch_data = f.read(msg_len)

    if len(batch_data) < msg_len:
        raise ValueError("Truncated journal file (incomplete batch data)")

    return batch_data


def _open_storage_directory(path: Path, create: bool = False) -> int:
    """Walk the directory using pinned descriptors and reject every symlink."""
    absolute = path.absolute()
    descriptor = os.open(absolute.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for component in absolute.parts[1:]:
            if create:
                try:
                    os.mkdir(component, mode=0o700, dir_fd=descriptor)
                    os.fsync(descriptor)
                except FileExistsError:
                    pass
            next_descriptor = os.open(
                component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor,
            )
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except OSError as exc:
        os.close(descriptor)
        raise ValueError("Security: journal directory contains an unsafe path component") from exc


def _open_safe_file(path: Path, mode: Literal["rb", "ab", "wb", "r+b"], buffering: int = -1) -> BinaryIO:
    descriptor = _open_storage_directory(path.parent)
    try:
        def opener(name: str, flags: int) -> int:
            return os.open(path.name, flags | os.O_NOFOLLOW, mode=0o600, dir_fd=descriptor)
        handle = open(path, mode, buffering=buffering, opener=opener)
        try:
            if any(flag in mode for flag in ("a", "w", "x")):
                os.fsync(descriptor)
            return handle
        except OSError:
            handle.close()
            raise
    finally:
        os.close(descriptor)


def _rename_safe_file(source: Path, target: Path) -> None:
    if source.parent != target.parent:
        raise ValueError("Security: journal rename must stay within its directory")
    descriptor = _open_storage_directory(source.parent)
    try:
        os.rename(source.name, target.name, src_dir_fd=descriptor, dst_dir_fd=descriptor)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _repair_truncated_active_file(path: Path) -> None:
    """Discard an incomplete final frame before the active file is opened for append."""
    file_size = path.stat().st_size
    valid_end = 0
    with _open_safe_file(path, "r+b", buffering=0) as handle:
        while valid_end < file_size:
            handle.seek(valid_end)
            length_bytes = handle.read(4)
            if len(length_bytes) < 4:
                break

            frame_length = struct.unpack("<I", length_bytes)[0]
            if frame_length > _JOURNAL_MAX_FRAME_SIZE:
                raise ValueError(f"Journal frame length {frame_length} exceeds maximum")

            payload_start = valid_end + 4
            if frame_length > file_size - payload_start:
                break
            valid_end = payload_start + frame_length

        if valid_end != file_size:
            handle.truncate(valid_end)
            handle.flush()
            os.fsync(handle.fileno())


def _file_write_state(descriptor: int) -> tuple[int, int, int, int, int]:
    """Identify the exact file state covered by a successful fsync."""
    state = os.fstat(descriptor)
    return state.st_dev, state.st_ino, state.st_size, state.st_mtime_ns, state.st_ctime_ns


def _is_parquet_file(path: Path) -> bool:
    """Identify legacy Parquet by its leading magic, even when its footer is damaged."""
    try:
        with _open_safe_file(path, "rb") as handle:
            return handle.read(4) == b"PAR1"
    except OSError:
        return False

