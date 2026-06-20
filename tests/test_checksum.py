"""Tests for checksum utility — file hash computation and verification."""

import os
import tempfile
from unittest.mock import patch

import pytest

from src.utils.checksum import compute_file_hash, verify_file


@pytest.fixture
def temp_file():
    """Create a temporary file with known content."""
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".dat", delete=False) as f:
        f.write(b"Hello, World! This is test content for hashing." * 100)
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def temp_file_copy(temp_file):
    """Create an identical copy of the temp file."""
    import shutil
    copy_path = temp_file + ".copy"
    shutil.copy2(temp_file, copy_path)
    yield copy_path
    if os.path.exists(copy_path):
        os.unlink(copy_path)


@pytest.fixture
def empty_file():
    """Create an empty temporary file."""
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".empty", delete=False) as f:
        path = f.name
    yield path
    os.unlink(path)


class TestComputeFileHash:
    """Test compute_file_hash function."""

    def test_xxhash_returns_hex_string(self, temp_file):
        """xxhash should return a hex digest string."""
        result = compute_file_hash(temp_file, "xxhash")
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0

    def test_sha256_returns_hex_string(self, temp_file):
        """sha256 should return a 64-char hex digest."""
        result = compute_file_hash(temp_file, "sha256")
        assert result is not None
        assert len(result) == 64  # SHA-256 hex digest length

    def test_xxhash_deterministic(self, temp_file):
        """Same file should always produce the same hash."""
        h1 = compute_file_hash(temp_file, "xxhash")
        h2 = compute_file_hash(temp_file, "xxhash")
        assert h1 == h2

    def test_sha256_deterministic(self, temp_file):
        """Same file should always produce the same SHA-256 hash."""
        h1 = compute_file_hash(temp_file, "sha256")
        h2 = compute_file_hash(temp_file, "sha256")
        assert h1 == h2

    def test_identical_files_same_hash(self, temp_file, temp_file_copy):
        """Identical files should produce the same hash."""
        h1 = compute_file_hash(temp_file, "xxhash")
        h2 = compute_file_hash(temp_file_copy, "xxhash")
        assert h1 == h2

    def test_different_content_different_hash(self, temp_file):
        """Different file content should produce different hashes."""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".dat", delete=False) as f:
            f.write(b"Different content entirely!" * 100)
            other_path = f.name

        h1 = compute_file_hash(temp_file, "xxhash")
        h2 = compute_file_hash(other_path, "xxhash")
        assert h1 != h2
        os.unlink(other_path)

    def test_empty_file(self, empty_file):
        """Empty file should still produce a valid hash."""
        result = compute_file_hash(empty_file, "xxhash")
        assert result is not None
        assert isinstance(result, str)

    def test_unreadable_file_returns_none(self):
        """Non-existent file should return None."""
        result = compute_file_hash("/nonexistent/path/file.dat", "xxhash")
        assert result is None

    @patch("src.utils.checksum.HAS_XXHASH", False)
    def test_fallback_to_sha256_when_no_xxhash(self, temp_file):
        """When xxhash is not installed, should fall back to SHA-256."""
        result = compute_file_hash(temp_file, "xxhash")
        assert result is not None
        assert len(result) == 64  # SHA-256 hex length

    def test_unknown_algorithm_defaults_to_sha256(self, temp_file):
        """Unknown algorithm should fall back to SHA-256."""
        result = compute_file_hash(temp_file, "md5")
        assert result is not None
        assert len(result) == 64  # SHA-256

    def test_custom_chunk_size(self, temp_file):
        """Custom chunk size should produce the same result."""
        h1 = compute_file_hash(temp_file, "xxhash", chunk_size=1024)
        h2 = compute_file_hash(temp_file, "xxhash", chunk_size=65536)
        assert h1 == h2


class TestVerifyFile:
    """Test verify_file function."""

    def test_matching_files_return_true(self, temp_file, temp_file_copy):
        """Identical files should verify successfully."""
        is_match, reason = verify_file(temp_file, temp_file_copy, "xxhash")
        assert is_match is True
        assert reason is None

    def test_matching_files_sha256(self, temp_file, temp_file_copy):
        """Identical files should verify with SHA-256."""
        is_match, reason = verify_file(temp_file, temp_file_copy, "sha256")
        assert is_match is True
        assert reason is None

    def test_size_mismatch_detected(self, temp_file, temp_file_copy):
        """Files with different sizes should fail verification."""
        # Append extra data to the copy
        with open(temp_file_copy, "ab") as f:
            f.write(b"extra data")

        is_match, reason = verify_file(temp_file, temp_file_copy, "xxhash")
        assert is_match is False
        assert "Size mismatch" in reason

    def test_content_mismatch_detected(self, temp_file, temp_file_copy):
        """Files with same size but different content should fail."""
        # Overwrite with same-length but different content
        file_size = os.path.getsize(temp_file)
        with open(temp_file_copy, "wb") as f:
            f.write(b"X" * file_size)

        is_match, reason = verify_file(temp_file, temp_file_copy, "xxhash")
        assert is_match is False
        assert "Hash mismatch" in reason

    def test_empty_files_match_without_hash(self, empty_file):
        """Two empty files should match (size check only)."""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".empty2", delete=False) as f:
            other_empty = f.name

        is_match, reason = verify_file(empty_file, other_empty, "xxhash")
        assert is_match is True
        assert reason is None
        os.unlink(other_empty)

    def test_source_unreadable(self, temp_file_copy):
        """If source file is unreadable, verification should fail."""
        is_match, reason = verify_file("/nonexistent/source", temp_file_copy, "xxhash")
        assert is_match is False
        assert reason is not None

    def test_dest_unreadable(self, temp_file):
        """If dest file is unreadable, verification should fail."""
        is_match, reason = verify_file(temp_file, "/nonexistent/dest", "xxhash")
        assert is_match is False
        assert reason is not None
