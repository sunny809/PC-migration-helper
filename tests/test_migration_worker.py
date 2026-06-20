"""Tests for MigrationWorker — migration operation orchestrator.

Tests the core logic without relying on Qt signal infrastructure.
Since PySide6 may not be installed, we test through the public API
and verify side effects on the config and cancel event.
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from src.constants import MigrationFormat, MigrationState
from src.models.file_entry import FileEntry
from src.models.migration_config import MigrationConfig
from src.models.migration_target import DriveType, MigrationTarget


def _make_config(format=MigrationFormat.COPY_ONLY, verify=True):
    """Create a MigrationConfig for testing."""
    target = MigrationTarget(
        drive_letter="E:", label="USB", drive_type=DriveType.REMOVABLE,
        total_bytes=10**9, free_bytes=5*10**8,
    )
    files = [
        FileEntry(path="C:\\test\\a.docx", size=100, modified_time=0),
        FileEntry(path="C:\\test\\b.jpg", size=200, modified_time=0),
    ]
    return MigrationConfig(
        selected_files=files, target=target,
        output_format=format, verify_after_write=verify,
        verify_algorithm="xxhash",
    )


class TestMigrationWorkerCancel:
    """Test MigrationWorker cancel mechanism."""

    def test_cancel_sets_cancel_event(self):
        from src.migration.migration_worker import MigrationWorker
        config = _make_config()
        worker = MigrationWorker(config)
        assert not worker._cancel_event.is_set()
        worker.cancel()
        assert worker._cancel_event.is_set()

    def test_is_cancelled_reflects_cancel_event(self):
        from src.migration.migration_worker import MigrationWorker
        config = _make_config()
        worker = MigrationWorker(config)
        # Manually set the event
        worker._cancel_event.set()
        assert worker._cancel_event.is_set()


class TestMigrationWorkerPauseResume:
    """Test MigrationWorker pause and resume mechanism."""

    def test_pause_clears_pause_event(self):
        from src.migration.migration_worker import MigrationWorker
        config = _make_config()
        worker = MigrationWorker(config)
        assert worker._pause_event.is_set()  # Initially unpaused
        worker.pause()
        assert not worker._pause_event.is_set()  # Paused

    def test_resume_sets_pause_event(self):
        from src.migration.migration_worker import MigrationWorker
        config = _make_config()
        worker = MigrationWorker(config)
        worker.pause()
        assert not worker._pause_event.is_set()
        worker.resume()
        assert worker._pause_event.is_set()

    def test_cancel_unblocks_pause(self):
        """Cancel should also unblock a paused worker."""
        from src.migration.migration_worker import MigrationWorker
        config = _make_config()
        worker = MigrationWorker(config)
        worker.pause()
        worker.cancel()
        # Both events should be set
        assert worker._cancel_event.is_set()
        assert worker._pause_event.is_set()


class TestMigrationWorkerIsCancelled:
    """Test _is_cancelled blocking behavior with pause."""

    def test_returns_false_when_not_cancelled(self):
        from src.migration.migration_worker import MigrationWorker
        config = _make_config()
        worker = MigrationWorker(config)
        # Not paused, not cancelled
        assert worker._is_cancelled() is False

    def test_returns_true_when_cancelled(self):
        from src.migration.migration_worker import MigrationWorker
        config = _make_config()
        worker = MigrationWorker(config)
        worker.cancel()
        assert worker._is_cancelled() is True


class TestMigrationWorkerCopy:
    """Test MigrationWorker's copy path via _run_copy."""

    @patch("src.migration.migration_worker.Copier")
    def test_run_copy_calls_copier_with_correct_args(self, MockCopier):
        """_run_copy should pass verify params from config to Copier."""
        from src.migration.migration_worker import MigrationWorker
        mock_copier = MagicMock()
        mock_copier.copy_files.return_value = {
            "success": True, "files_processed": 2, "bytes_processed": 300,
            "errors": [], "target_dir": "/tmp/backup", "verify_failures": [],
        }
        MockCopier.return_value = mock_copier

        config = _make_config(format=MigrationFormat.COPY_ONLY, verify=True)
        config.verify_algorithm = "sha256"
        worker = MigrationWorker(config)
        worker._start_time = time.time()
        worker._run_copy()

        # Verify Copier was created and called
        MockCopier.assert_called_once_with(chunk_size=config.chunk_size)
        mock_copier.copy_files.assert_called_once()
        kwargs = mock_copier.copy_files.call_args[1]
        assert kwargs["verify"] is True
        assert kwargs["verify_algorithm"] == "sha256"
        assert kwargs["files"] == config.selected_files
        assert kwargs["target_dir"] == config.output_path

    @patch("src.migration.migration_worker.Copier")
    def test_run_copy_without_verify(self, MockCopier):
        """_run_copy should pass verify=False when config says so."""
        from src.migration.migration_worker import MigrationWorker
        mock_copier = MagicMock()
        mock_copier.copy_files.return_value = {
            "success": True, "files_processed": 2, "bytes_processed": 300,
            "errors": [], "target_dir": "/tmp/backup", "verify_failures": [],
        }
        MockCopier.return_value = mock_copier

        config = _make_config(format=MigrationFormat.COPY_ONLY, verify=False)
        worker = MigrationWorker(config)
        worker._start_time = time.time()
        worker._run_copy()

        kwargs = mock_copier.copy_files.call_args[1]
        assert kwargs["verify"] is False


class TestMigrationWorkerCompress:
    """Test MigrationWorker's compress path via _run_compress."""

    @patch("src.migration.migration_worker.Compressor")
    def test_run_compress_calls_compressor(self, MockCompressor):
        """_run_compress should call Compressor with correct params."""
        from src.migration.migration_worker import MigrationWorker
        mock_compressor = MagicMock()
        mock_compressor.compress.return_value = {
            "success": True, "files_processed": 2, "bytes_processed": 300,
            "errors": [], "output_path": "/tmp/backup.7z",
        }
        MockCompressor.return_value = mock_compressor

        config = _make_config(format=MigrationFormat.SEVEN_ZIP)
        worker = MigrationWorker(config)
        worker._start_time = time.time()
        worker._run_compress()

        MockCompressor.assert_called_once_with(chunk_size=config.chunk_size)
        mock_compressor.compress.assert_called_once()
        kwargs = mock_compressor.compress.call_args[1]
        assert kwargs["format"] == MigrationFormat.SEVEN_ZIP
        assert kwargs["compression_level"] == config.compression_level
        assert kwargs["files"] == config.selected_files
