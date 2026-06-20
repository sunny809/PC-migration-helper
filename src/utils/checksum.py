"""File verification utility — checksum computation and comparison."""

from __future__ import annotations

import hashlib
from typing import Optional

from src.utils.logger import setup_logging

logger = setup_logging()

# Try to import xxhash for fast hashing; fall back to hashlib
try:
    import xxhash
    HAS_XXHASH = True
except ImportError:
    HAS_XXHASH = False
    logger.info("xxhash not installed, falling back to hashlib (SHA-256)")


def compute_file_hash(
    file_path: str,
    algorithm: str = "xxhash",
    chunk_size: int = 65536,
) -> Optional[str]:
    """Compute the hash of a file.

    Args:
        file_path: Path to the file.
        algorithm: Hash algorithm. "xxhash" (fast) or "sha256" (secure).
        chunk_size: Read buffer size in bytes.

    Returns:
        Hex digest string, or None if the file cannot be read.
    """
    try:
        if algorithm == "xxhash" and HAS_XXHASH:
            h = xxhash.xxh128()
        elif algorithm == "xxhash":
            # Fallback to SHA-256 if xxhash not available
            h = hashlib.sha256()
        elif algorithm == "sha256":
            h = hashlib.sha256()
        else:
            logger.warning(f"Unknown hash algorithm: {algorithm}, using sha256")
            h = hashlib.sha256()

        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)

        return h.hexdigest()

    except (OSError, PermissionError) as e:
        logger.debug(f"Cannot compute hash for {file_path}: {e}")
        return None


def verify_file(
    source_path: str,
    dest_path: str,
    algorithm: str = "xxhash",
    chunk_size: int = 65536,
) -> tuple[bool, Optional[str]]:
    """Verify that two files have identical content by comparing hashes.

    Also checks file size as a fast pre-check.

    Args:
        source_path: Original source file path.
        dest_path: Destination (copied) file path.
        algorithm: Hash algorithm to use.
        chunk_size: Read buffer size in bytes.

    Returns:
        Tuple of (is_match, failure_reason).
        is_match is True if files are identical.
        failure_reason is None on match, or a description string.
    """
    # Fast pre-check: file sizes
    try:
        source_size = os.path.getsize(source_path)
        dest_size = os.path.getsize(dest_path)
    except OSError as e:
        return False, f"Cannot read file size: {e}"

    if source_size != dest_size:
        return False, f"Size mismatch: source={source_size}, dest={dest_size}"

    # For empty files, size match is sufficient
    if source_size == 0:
        return True, None

    # Hash comparison
    source_hash = compute_file_hash(source_path, algorithm, chunk_size)
    dest_hash = compute_file_hash(dest_path, algorithm, chunk_size)

    if source_hash is None:
        return False, "Cannot compute source hash"
    if dest_hash is None:
        return False, "Cannot compute destination hash"

    if source_hash != dest_hash:
        return False, f"Hash mismatch: source={source_hash[:16]}..., dest={dest_hash[:16]}..."

    return True, None


# Import os for verify_file
import os
