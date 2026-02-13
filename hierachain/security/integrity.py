"""
Startup Integrity Guard for HieraChain Framework.

This module performs SHA-256 checksum verification of critical code directories
to detect unauthorized modifications before the system starts processing data.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

from hierachain.security.secure_logging import get_security_logger

logger = get_security_logger()


class IntegrityError(Exception):
    """Raised when code integrity check fails."""
    pass


def calculate_file_hash(file_path: Path) -> str:
    """Calculate SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


def _build_error_message(result: dict[str, list[str]]) -> str:
    """Construct detailed error message for integrity failure."""
    parts = ["Integrity check FAILED:"]
    if result["modified"]:
        parts.append(f"  Modified: {result['modified']}")
    if result["missing"]:
        parts.append(f"  Missing: {result['missing']}")
    return "\n".join(parts)


def _report_integrity_results(result: dict[str, list[str]]) -> dict[str, list[str]]:
    """Log findings and raise IntegrityError if critical issues found."""
    if result["modified"] or result["missing"]:
        error_msg = _build_error_message(result)
        logger.critical(error_msg)
        raise IntegrityError(error_msg)

    if result["new"]:
        logger.warning(f"New files detected (not in manifest): {result['new']}")

    logger.info("Integrity check PASSED")
    return result


class ChecksumValidator:
    """
    Validates file integrity using SHA-256 checksums.

    Compares current file hashes against a pre-generated manifest
    to detect code modifications since the last release.

    Usage:
        validator = ChecksumValidator(base_path="/path/to/project")
        validator.verify_integrity()  # Raises IntegrityError if mismatch
    """

    MANIFEST_FILE = "integrity_manifest.json"

    def __init__(self, base_path: str | None = None, manifest_path: str | None = None):
        """
        Initialize ChecksumValidator.

        Args:
            base_path: Root path of the project. Defaults to hierachain parent.
            manifest_path: Path to manifest file. Defaults to base_path/MANIFEST_FILE.
        """
        if base_path is None:
            # Default to hierachain package parent directory
            current_file = Path(__file__).resolve()
            base_path = str(current_file.parent.parent.parent)

        self.base_path = Path(base_path)
        self.manifest_path = Path(manifest_path or self.base_path / self.MANIFEST_FILE)

        # Directories to verify
        self.protected_dirs = ["hierachain/security", "hierachain/core"]

    def calculate_directory_hash(self, dir_path: str) -> dict[str, str]:
        """
        Calculate SHA-256 hashes for all .py files in a directory.

        Args:
            dir_path: Relative path from base_path.

        Returns:
            Dict mapping relative file paths to their SHA-256 hashes.
        """
        full_path = self.base_path / dir_path
        hashes: dict[str, str] = {}

        if not full_path.exists():
            logger.warning(f"Directory not found: {full_path}")
            return hashes

        for py_file in full_path.rglob("*.py"):
            relative_path = str(py_file.relative_to(self.base_path))
            hashes[relative_path] = calculate_file_hash(py_file)

        return hashes

    def generate_manifest(self) -> dict[str, Any]:
        """
        Generate integrity manifest for protected directories.

        Returns:
            Manifest dict with hashes for all protected files.
        """
        manifest: dict[str, Any] = {
            "version": "1.0",
            "protected_dirs": self.protected_dirs,
            "files": {}
        }

        for dir_path in self.protected_dirs:
            dir_hashes = self.calculate_directory_hash(dir_path)
            manifest["files"].update(dir_hashes)

        logger.info(f"Generated manifest with {len(manifest['files'])} files")
        return manifest

    def save_manifest(self, manifest: dict[str, Any] | None = None) -> None:
        """Save manifest to file (should be called during build/release)."""
        if manifest is None:
            manifest = self.generate_manifest()

        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        logger.info(f"Manifest saved to {self.manifest_path}")

    def load_manifest(self) -> dict[str, Any]:
        """Load manifest from file."""
        if not self.manifest_path.exists():
            raise IntegrityError(
                f"Manifest file not found: {self.manifest_path}. "
                "Run 'generate_manifest()' during build/release."
            )

        with open(self.manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def verify_integrity(self) -> dict[str, list[str]]:
        """
        Verify code integrity against manifest.
        
        Returns:
            Dict with 'modified', 'missing', and 'new' file lists.
        
        Raises:
            IntegrityError: If any files have been modified or removed.
        """
        manifest = self.load_manifest()
        expected_hashes = manifest.get("files", {})
        
        result: dict[str, list[str]] = {
            "modified": [],
            "missing": [],
            "new": []
        }
        
        # 1. Check existing files and detect modifications/missing
        self._check_manifest_files(expected_hashes, result)
        
        # 2. Check for new files not in manifest
        self._check_for_new_files(expected_hashes, result)
        
        # 3. Handle and report results
        return _report_integrity_results(result)

    def _check_manifest_files(self, expected_hashes: dict[str, str], result: dict[str, list[str]]) -> None:
        """Check each file in manifest for existence and hash match."""
        for file_path, expected_hash in expected_hashes.items():
            full_path = self.base_path / file_path
            
            if not full_path.exists():
                result["missing"].append(file_path)
                continue
                
            if calculate_file_hash(full_path) != expected_hash:
                result["modified"].append(file_path)

    def _check_for_new_files(self, expected_hashes: dict[str, str], result: dict[str, list[str]]) -> None:
        """Scan protected directories for files not present in manifest."""
        for dir_path in self.protected_dirs:
            current_hashes = self.calculate_directory_hash(dir_path)
            for file_path in current_hashes:
                if file_path not in expected_hashes:
                    result["new"].append(file_path)


def verify_startup_integrity(abort_on_failure: bool = True) -> bool:
    """
    Convenience function to verify integrity at startup.

    Args:
        abort_on_failure: If True, raises IntegrityError on failure.

    Returns:
        True if integrity check passed, False otherwise.
    """
    try:
        validator = ChecksumValidator()
        validator.verify_integrity()
        return True
    except IntegrityError as e:
        if abort_on_failure:
            raise
        logger.error(f"Integrity check failed: {e}")
        return False
    except FileNotFoundError:
        # Manifest doesn't exist - first run or dev mode
        logger.warning(
            "No integrity manifest found. "
            "Run ChecksumValidator.save_manifest() during build."
        )
        return True  # Allow startup in dev mode
