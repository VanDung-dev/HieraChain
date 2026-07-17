"""
IPFS Client for HieraChain Private Swarm.

This module provides a client for interacting with a Private IPFS Swarm,
including upload, download, pinning, and encryption integration.

The client is designed to work with local IPFS daemons running in a private network,
ensuring that all data stored remains within the enterprise boundary.
"""

import orjson
import os
from typing import Any

import httpx

from hierachain.api.storage.encryption import AESEncryption, EncryptionError
from hierachain.security.secure_logging import SecureLogger

logger = SecureLogger("hierachain.storage.ipfs_client")


class IPFSError(Exception):
    """Base exception for IPFS-related errors."""

    pass


def _parse_multiaddr(addr: str) -> tuple[str, int]:
    """Parse multiaddr format /ip4/<host>/tcp/<port> to (host, port)."""
    parts = addr.strip("/").split("/")
    return parts[1], int(parts[3])


class IPFSClient:
    """
    Client for interacting with Private IPFS Swarm with encryption support.

    Key Features:
    - Upload/download files to/from IPFS
    - Automatic pinning to prevent garbage collection
    - Built-in AES-256-GCM encryption for data-at-rest security
    - Support for both raw bytes and JSON data
    - Connection pooling and error handling

    Security Model:
    - All data is encrypted before upload (encryption-at-rest)
    - IPFS stores ciphertext only
    - Only nodes with the correct key can decrypt
    - CIDs can be public, but underlying data remains secure
    """

    def __init__(
        self,
        ipfs_host: str = "/ip4/127.0.0.1/tcp/5001",
        encryption_key: bytes | None = None,
        auto_pin: bool = True,
        timeout: int = 120,
    ):
        """
        Initialize IPFS client.

        Args:
            ipfs_host: IPFS daemon API address (multiaddr format)
            encryption_key: 32-byte AES-256 key. If None, creates a new key.
            auto_pin: Automatically pin uploaded files to prevent GC
            timeout: Request timeout in seconds

        Raises:
            IPFSError: If IPFS client library is not available or connection fails
        """
        self._host, self._port = _parse_multiaddr(ipfs_host)
        self._timeout = timeout
        self._auto_pin = auto_pin

        # Initialize encryption
        self._encryption = AESEncryption(encryption_key)

        # Lazy connection - only connect when needed
        self._client: httpx.Client | None = None

        logger.info(
            "IPFS client initialized",
            host=ipfs_host,
            auto_pin=auto_pin,
            encryption_enabled=True,
        )

    @property
    def encryption_key(self) -> bytes:
        """Get the encryption key (return a copy to prevent modification)."""
        return bytes(self._encryption.key)  # Return copy for safety

    # ---- Connection Management ----

    @property
    def client(self) -> httpx.Client:
        """Get the connected HTTP client, ensuring connection."""
        if self._client is None:
            try:
                client_instance = httpx.Client(
                    base_url=f"http://{self._host}:{self._port}",
                    timeout=self._timeout,
                )
                # Test connection
                resp = client_instance.post("/api/v0/version")
                resp.raise_for_status()
                self._client = client_instance
                logger.info("Connected to IPFS daemon", host=self._host)
            except httpx.HTTPError as e:
                logger.error("Failed to connect to IPFS daemon", error=str(e))
                raise IPFSError(f"Failed to connect to IPFS daemon: {str(e)}")
        
        # Explicit type check for linters
        if self._client is None:
            raise IPFSError("IPFS client is not initialized")
        return self._client

    def _ensure_connected(self) -> None:
        """Ensure IPFS client is connected, connect if needed."""
        _ = self.client

    def upload_bytes(
        self, data: bytes, encrypt: bool = True, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Upload raw bytes to IPFS with optional encryption.

        Args:
            data: Raw bytes to upload
            encrypt: Whether to encrypt data before upload (recommended: True)
            metadata: Optional metadata dict (will be used as AAD if encrypting)

        Returns:
            Dict containing:
            - cid: IPFS Content Identifier
            - size: Size in bytes (of ciphertext if encrypted)
            - encrypted: Whether data was encrypted
            - nonce: Encryption nonce (hex) if encrypted
            - metadata: Original metadata if provided

        Raises:
            IPFSError: If upload fails
            EncryptionError: If encryption fails
        """
        try:
            # Prepare data for upload
            if encrypt:
                # Serialize metadata for AAD
                aad = (
                    orjson.dumps(metadata, option=orjson.OPT_SORT_KEYS)
                    if metadata
                    else None
                )

                # Encrypt data
                ciphertext, nonce = self._encryption.encrypt(data, aad)
                upload_data = ciphertext
                nonce_hex = nonce.hex()

                logger.debug(
                    "Data encrypted for IPFS upload",
                    original_size=len(data),
                    encrypted_size=len(ciphertext),
                )
            else:
                upload_data = data
                nonce_hex = None

            # Upload to IPFS via Kubo RPC
            self._ensure_connected()
            resp = self.client.post(
                "/api/v0/add",
                files={"file": ("data", upload_data)},
            )
            resp.raise_for_status()
            # Kubo returns NDJSON; first line has the Hash
            result = resp.json()
            cid = result["Hash"]

            # Auto-pin if enabled
            if self._auto_pin:
                self.pin(cid)

            response = {
                "cid": cid,
                "size": len(upload_data),
                "encrypted": encrypt,
            }

            if encrypt:
                response["nonce"] = nonce_hex

            if metadata:
                response["metadata"] = metadata

            logger.info(
                "Data uploaded to IPFS successfully",
                cid=cid,
                size=len(upload_data),
                encrypted=encrypt,
            )

            return response

        except EncryptionError:
            raise
        except (httpx.HTTPError, KeyError) as e:
            logger.error("Failed to upload data to IPFS", error=str(e))
            raise IPFSError(f"Failed to upload data: {str(e)}")

    def download_bytes(
        self,
        cid: str,
        encrypted: bool = True,
        nonce: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bytes:
        """
        Download and optionally decrypt data from IPFS.

        Args:
            cid: IPFS Content Identifier
            encrypted: Whether the data is encrypted
            nonce: Encryption nonce (hex string) required if encrypted=True
            metadata: Optional metadata used as AAD during encryption

        Returns:
            Decrypted bytes (or raw bytes if encrypted=False)

        Raises:
            IPFSError: If download fails or CID not found
            EncryptionError: If decryption fails
        """
        try:
            # Validate CID format (alphanumeric check)
            if not cid or not all(c.isalnum() for c in cid):
                raise IPFSError("Invalid CID format")

            # Download from IPFS via Kubo RPC
            self._ensure_connected()
            resp = self.client.post(f"/api/v0/cat?arg={cid}")
            resp.raise_for_status()
            download_data = resp.content

            logger.debug("Data downloaded from IPFS", cid=cid, size=len(download_data))

            # Decrypt if needed
            if encrypted:
                if nonce is None:
                    raise IPFSError("Nonce is required for decrypting data")

                # Validate nonce format and length
                if len(nonce) != 24:
                    raise IPFSError("Invalid nonce length: must be 24 hex characters")
                try:
                    nonce_bytes = bytes.fromhex(nonce)
                except ValueError:
                    raise IPFSError("Invalid nonce format: must be hex characters")

                # Deserialize metadata for AAD
                aad = (
                    orjson.dumps(metadata, option=orjson.OPT_SORT_KEYS)
                    if metadata
                    else None
                )

                plaintext = self._encryption.decrypt(download_data, nonce_bytes, aad)

                logger.debug(
                    "Data decrypted successfully", decrypted_size=len(plaintext)
                )

                return plaintext
            else:
                return download_data

        except EncryptionError:
            raise
        except (httpx.HTTPError, ValueError) as e:
            logger.error("Failed to download data from IPFS", cid=cid, error=str(e))
            raise IPFSError(f"Failed to download data from CID {cid}: {str(e)}")

    def upload_json(
        self, data: dict, encrypt: bool = True, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Upload JSON data to IPFS with optional encryption.

        Args:
            data: Dictionary to upload
            encrypt: Whether to encrypt data
            metadata: Optional metadata

        Returns:
            Upload result dict with CID, nonce, etc.
        """
        try:
            json_bytes = orjson.dumps(data, option=orjson.OPT_SORT_KEYS)
            return self.upload_bytes(json_bytes, encrypt=encrypt, metadata=metadata)
        except (TypeError, ValueError) as e:
            raise IPFSError(f"JSON serialization failed: {str(e)}")

    def download_json(
        self,
        cid: str,
        encrypted: bool = True,
        nonce: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict:
        """
        Download and optionally decrypt JSON data from IPFS.

        Args:
            cid: IPFS Content Identifier
            encrypted: Whether the data is encrypted
            nonce: Encryption nonce (hex string)
            metadata: Optional metadata used as AAD

        Returns:
            Decrypted dictionary
        """
        try:
            json_bytes = self.download_bytes(
                cid, encrypted=encrypted, nonce=nonce, metadata=metadata
            )
            return orjson.loads(json_bytes)
        except (orjson.JSONDecodeError, UnicodeDecodeError) as e:
            raise IPFSError(f"JSON deserialization failed: {str(e)}")

    # ---- Pin Management ----

    def pin(self, cid: str) -> bool:
        """
        Pin content to prevent garbage collection.

        Args:
            cid: IPFS Content Identifier to pin

        Returns:
            True if pinned successfully

        Raises:
            IPFSError: If pinning fails
        """
        try:
            self._ensure_connected()
            resp = self.client.post(f"/api/v0/pin/add?arg={cid}")
            resp.raise_for_status()

            logger.info("Content pinned successfully", cid=cid)
            return True

        except httpx.HTTPError as e:
            logger.error("Failed to pin content", cid=cid, error=str(e))
            raise IPFSError(f"Failed to pin CID {cid}: {str(e)}")

    def unpin(self, cid: str) -> bool:
        """
        Unpin content (allow garbage collection).

        Args:
            cid: IPFS Content Identifier to unpin

        Returns:
            True if unpinned successfully

        Raises:
            IPFSError: If unpinning fails
        """
        try:
            self._ensure_connected()
            resp = self.client.post(f"/api/v0/pin/rm?arg={cid}")
            resp.raise_for_status()

            logger.info("Content unpinned successfully", cid=cid)
            return True

        except httpx.HTTPError as e:
            logger.error("Failed to unpin content", cid=cid, error=str(e))
            raise IPFSError(f"Failed to unpin CID {cid}: {str(e)}")

    def list_pins(self) -> list[str]:
        """
        List all pinned CIDs.

        Returns:
            List of pinned CIDs

        Raises:
            IPFSError: If listing fails
        """
        try:
            self._ensure_connected()
            resp = self.client.post("/api/v0/pin/ls")
            resp.raise_for_status()
            pins = resp.json()

            # Extract CIDs from pins dict
            cids = list(pins["Keys"].keys()) if "Keys" in pins else []

            logger.debug("Listed pinned content", count=len(cids))
            return cids

        except (httpx.HTTPError, KeyError) as e:
            logger.error("Failed to list pins", error=str(e))
            raise IPFSError(f"Failed to list pins: {str(e)}")

    # ---- Misc ----

    def get_stats(self, cid: str) -> dict[str, Any]:
        """
        Get statistics for a CID.

        Args:
            cid: IPFS Content Identifier

        Returns:
            Dict with size, type, and other stats

        Raises:
            IPFSError: If stat fails
        """
        try:
            self._ensure_connected()
            resp = self.client.post(f"/api/v0/files/stat?arg=/ipfs/{cid}")
            resp.raise_for_status()

            logger.debug("Retrieved IPFS stats", cid=cid)
            return resp.json()

        except httpx.HTTPError as e:
            logger.error("Failed to get stats", cid=cid, error=str(e))
            raise IPFSError(f"Failed to get stats for CID {cid}: {str(e)}")

    def is_available(self, cid: str) -> bool:
        """
        Check if content is available on IPFS network.

        Args:
            cid: IPFS Content Identifier

        Returns:
            True if content is available, False otherwise
        """
        try:
            self._ensure_connected()
            resp = self.client.post(f"/api/v0/object/stat?arg={cid}")
            return resp.is_success
        except (IPFSError, httpx.HTTPError):
            logger.debug("Content not available", cid=cid)
            return False

    def get_daemon_version(self) -> dict[str, Any]:
        """
        Get IPFS daemon version information.

        Returns:
            Dict with version info

        Raises:
            IPFSError: If version check fails
        """
        try:
            self._ensure_connected()
            resp = self.client.post("/api/v0/version")
            resp.raise_for_status()
            version = resp.json()

            # Safe access to Version key with default value
            logger.debug(
                "Retrieved IPFS daemon version",
                version=version.get("Version", "unknown"),
            )
            return {"version": version.get("Version", "unknown")}

        except (httpx.HTTPError, KeyError) as e:
            logger.error("Failed to get daemon version", error=str(e))
            raise IPFSError(f"Failed to get daemon version: {str(e)}")

    def close(self):
        """Close the IPFS client connection."""
        if self._client is not None:
            try:
                self._client.close()
                logger.info("IPFS client connection closed")
            except Exception as e:
                logger.warning("Error closing IPFS client", error=str(e))
            finally:
                self._client = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, *exc):
        """Context manager exit."""
        self.close()

    def __repr__(self) -> str:
        return f"<IPFSClient host={self._host}:{self._port} auto_pin={self._auto_pin}>"


def create_ipfs_client_from_env() -> IPFSClient:
    """
    Create IPFS client from environment variables.

    Environment Variables:
        HRC_IPFS_HOST: IPFS daemon API address (default: /ip4/127.0.0.1/tcp/5001)
        HRC_IPFS_ENCRYPTION_KEY: Hex-encoded 256-bit encryption key
        HRC_IPFS_AUTO_PIN: Auto-pin uploads (default: true)
        HRC_IPFS_TIMEOUT: Request timeout in seconds (default: 120)

    Returns:
        Configured IPFSClient instance
    """
    ipfs_host = os.getenv("HRC_IPFS_HOST", "/ip4/127.0.0.1/tcp/5001")
    auto_pin = os.getenv("HRC_IPFS_AUTO_PIN", "true").lower() == "true"
    timeout = int(os.getenv("HRC_IPFS_TIMEOUT", "120"))

    # Get or generate encryption key
    key_hex = os.getenv("HRC_IPFS_ENCRYPTION_KEY")
    if key_hex:
        try:
            encryption_key = bytes.fromhex(key_hex)
            logger.info("Using encryption key from environment variable")
        except ValueError:
            logger.warning("Invalid encryption key in environment, generating new key")
            encryption_key = None
    else:
        logger.warning(
            "No encryption key in environment (HRC_IPFS_ENCRYPTION_KEY), "
            "generating new key. This key should be securely stored and shared "
            "across nodes in the same channel/organization."
        )
        encryption_key = None

    return IPFSClient(
        ipfs_host=ipfs_host,
        encryption_key=encryption_key,
        auto_pin=auto_pin,
        timeout=timeout,
    )
