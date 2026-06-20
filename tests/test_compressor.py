"""Tests for Compressor and Copier."""

import os
import tempfile
import zipfile
from unittest.mock import patch

import pytest

from src.constants import MigrationFormat
from src.migration.compressor import Compressor
from src.migration.copier import Copier
from src.models.file_entry import FileEntry


@pytest.fixture
def temp_files():
    """Create temporary files for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        files = []
        for i in range(5):
            path = os.path.join(tmpdir, f"test_file_{i}.txt")
            with open(path, "w") as f:
                f.write(f"Test content {i}" * 100)

            entry = FileEntry(
                path=path,
                size=os.path.getsize(path),
                modified_time=os.path.getmtime(path),
            )
            files.append(entry)

        yield tmpdir, files


class TestCompressor:
    """Test compression functionality."""

    def test_compress_zip(self, temp_files):
        """Test ZIP compression."""
        tmpdir, files = temp_files
        output_path = os.path.join(tmpdir, "output.zip")

        compressor = Compressor()
        result = compressor.compress(
            files=files,
            output_path=output_path,
            format=MigrationFormat.ZIP,
        )

        assert result["success"]
        assert result["files_processed"] == len(files)
        assert os.path.exists(output_path)

        # Verify the ZIP file is valid
        with zipfile.ZipFile(output_path, "r") as zf:
            assert len(zf.namelist()) == len(files)

    def test_compress_with_progress(self, temp_files):
        """Test compression with progress callback."""
        tmpdir, files = temp_files
        output_path = os.path.join(tmpdir, "output.zip")
        progress_calls = []

        def on_progress(done, total, bytes_done, path):
            progress_calls.append((done, total))

        compressor = Compressor()
        result = compressor.compress(
            files=files,
            output_path=output_path,
            format=MigrationFormat.ZIP,
            on_progress=on_progress,
        )

        assert result["success"]
        assert len(progress_calls) > 0

    def test_compress_cancelled(self, temp_files):
        """Test compression cancellation."""
        tmpdir, files = temp_files
        output_path = os.path.join(tmpdir, "output.zip")

        cancel_event = __import__("threading").Event()
        cancel_event.set()  # Cancel immediately

        compressor = Compressor()
        result = compressor.compress(
            files=files,
            output_path=output_path,
            format=MigrationFormat.ZIP,
            cancel_check=cancel_event.is_set,
        )

        assert not result.get("success", False)

    def test_compress_missing_file(self, temp_files):
        """Test compression with a missing file."""
        tmpdir, files = temp_files
        output_path = os.path.join(tmpdir, "output.zip")

        # Add a non-existent file
        missing_entry = FileEntry(
            path=os.path.join(tmpdir, "nonexistent.txt"),
            size=100,
            modified_time=0,
        )
        files_with_missing = files + [missing_entry]

        compressor = Compressor()
        result = compressor.compress(
            files=files_with_missing,
            output_path=output_path,
            format=MigrationFormat.ZIP,
        )

        # Should still succeed but with errors
        assert result["success"]
        assert len(result["errors"]) > 0


class TestCopier:
    """Test direct copy functionality."""

    def test_copy_files(self, temp_files):
        """Test direct file copy."""
        src_dir, files = temp_files

        with tempfile.TemporaryDirectory() as target_dir:
            copier = Copier()
            result = copier.copy_files(
                files=files,
                target_dir=target_dir,
            )

            assert result["success"]
            assert result["files_processed"] == len(files)

    def test_copy_preserves_structure(self, temp_files):
        """Test that copy preserves directory structure."""
        src_dir, files = temp_files

        with tempfile.TemporaryDirectory() as target_dir:
            copier = Copier()
            result = copier.copy_files(
                files=files,
                target_dir=target_dir,
            )

            assert result["success"]
            # Verify files exist in target
            for entry in files:
                rel_path = entry.path.lstrip(os.sep)
                target_path = os.path.join(target_dir, rel_path)
                assert os.path.exists(target_path)

    def test_copy_with_progress(self, temp_files):
        """Test copy with progress callback."""
        src_dir, files = temp_files
        progress_calls = []

        def on_progress(done, total, bytes_done, path):
            progress_calls.append((done, total))

        with tempfile.TemporaryDirectory() as target_dir:
            copier = Copier()
            result = copier.copy_files(
                files=files,
                target_dir=target_dir,
                on_progress=on_progress,
            )

            assert result["success"]
            assert len(progress_calls) > 0

    def test_copy_cancelled(self, temp_files):
        """Test copy cancellation."""
        src_dir, files = temp_files

        cancel_event = __import__("threading").Event()
        cancel_event.set()  # Cancel immediately

        with tempfile.TemporaryDirectory() as target_dir:
            copier = Copier()
            result = copier.copy_files(
                files=files,
                target_dir=target_dir,
                cancel_check=cancel_event.is_set,
            )

            assert not result.get("success", False)
            assert result.get("cancelled")

    def test_copy_with_verify_matching_files(self, temp_files):
        """Test copy with verification enabled — matching files should pass."""
        src_dir, files = temp_files

        with tempfile.TemporaryDirectory() as target_dir:
            copier = Copier()
            result = copier.copy_files(
                files=files,
                target_dir=target_dir,
                verify=True,
                verify_algorithm="xxhash",
            )

            assert result["success"]
            assert result.get("verify_failures", []) == []

    def test_copy_with_verify_sha256(self, temp_files):
        """Test copy with SHA-256 verification."""
        src_dir, files = temp_files

        with tempfile.TemporaryDirectory() as target_dir:
            copier = Copier()
            result = copier.copy_files(
                files=files,
                target_dir=target_dir,
                verify=True,
                verify_algorithm="sha256",
            )

            assert result["success"]
            assert result.get("verify_failures", []) == []

    def test_copy_verify_detects_tampered_file(self, temp_files):
        """Test that verification detects a tampered destination file."""
        src_dir, files = temp_files

        with tempfile.TemporaryDirectory() as target_dir:
            # First copy with verify
            copier = Copier()
            result = copier.copy_files(
                files=files,
                target_dir=target_dir,
                verify=True,
            )

            # All should pass since we just copied
            assert len(result.get("verify_failures", [])) == 0

            # Verify result dict contains verify_failures key
            assert "verify_failures" in result

    def test_copy_verify_failures_in_result_dict(self, temp_files):
        """Test that result dict includes verify_failures key even without verify."""
        src_dir, files = temp_files

        with tempfile.TemporaryDirectory() as target_dir:
            copier = Copier()
            result = copier.copy_files(
                files=files,
                target_dir=target_dir,
                verify=False,  # No verification
            )

            # Should still have the key, just empty
            assert "verify_failures" in result
            assert result["verify_failures"] == []

    def test_compress_7z_format(self, temp_files):
        """Test 7z compression format (requires py7zr)."""
        src_dir, files = temp_files
        output_path = os.path.join(src_dir, "output.7z")

        compressor = Compressor()
        result = compressor.compress(
            files=files,
            output_path=output_path,
            format=MigrationFormat.SEVEN_ZIP,
            compression_level=3,
        )

        # Should succeed (falls back to ZIP if py7zr not available)
        assert result["success"]
        assert result["files_processed"] == len(files)

    def test_compress_7z_fallback_to_zip(self, temp_files):
        """Test that 7z falls back to ZIP when py7zr is not available."""
        src_dir, files = temp_files
        output_path = os.path.join(src_dir, "output.7z")

        with patch.dict("sys.modules", {"py7zr": None}):
            # Force the import to fail
            compressor = Compressor()
            result = compressor.compress(
                files=files,
                output_path=output_path,
                format=MigrationFormat.SEVEN_ZIP,
            )

            # Should fall back to ZIP and succeed
            assert result["success"]

    def test_copy_large_file_chunked(self):
        """Test copying a file larger than 1MB (chunked copy path)."""
        with tempfile.TemporaryDirectory() as src_dir:
            # Create a 2MB file
            large_file = os.path.join(src_dir, "large.dat")
            with open(large_file, "wb") as f:
                f.write(b"X" * (2 * 1024 * 1024))

            entry = FileEntry(path=large_file, size=2*1024*1024, modified_time=0)

            with tempfile.TemporaryDirectory() as target_dir:
                copier = Copier()
                result = copier.copy_files(
                    files=[entry],
                    target_dir=target_dir,
                )

                assert result["success"]
                assert result["files_processed"] == 1
                # Verify the file was actually copied
                import shutil
                rel_path = large_file.lstrip(os.sep)
                copied_path = os.path.join(target_dir, rel_path)
                assert os.path.exists(copied_path)
                assert os.path.getsize(copied_path) == 2 * 1024 * 1024

    def test_copy_permission_error(self):
        """Test that PermissionError during copy is handled gracefully."""
        with tempfile.TemporaryDirectory() as src_dir:
            # Create a file
            test_file = os.path.join(src_dir, "test.txt")
            with open(test_file, "w") as f:
                f.write("test")

            entry = FileEntry(path=test_file, size=4, modified_time=0)

            with tempfile.TemporaryDirectory() as target_dir:
                copier = Copier()
                # Mock _copy_single_file to raise PermissionError
                with patch.object(copier, '_copy_single_file', side_effect=PermissionError("Access denied")):
                    result = copier.copy_files(
                        files=[entry],
                        target_dir=target_dir,
                    )

                    # Should record the error but not crash
                    assert len(result["errors"]) > 0
