"""MigrationWorker — QThread-compatible worker for file migration (compress/copy)."""

from __future__ import annotations

import os
import threading
import time
from typing import Callable, List, Optional

from src.constants import MigrationFormat, MigrationState
from src.models.file_entry import FileEntry
from src.models.migration_config import MigrationConfig
from src.models.migration_result import MigrationResult
from src.migration.compressor import Compressor
from src.migration.copier import Copier
from src.utils.logger import setup_logging
from src.utils.report_generator import ReportGenerator

logger = setup_logging()

try:
    from PySide6.QtCore import QObject, Signal
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False
    class QObject:  # type: ignore[no-redef]
        pass
    class Signal:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs):
            pass
        def emit(self, *args, **kwargs):
            pass


class MigrationWorker(QObject if HAS_PYSIDE6 else object):
    """Worker object for file migration operations.

    Handles both compression (ZIP/7z) and direct copy operations.
    Reports detailed progress for UI integration.

    Usage:
        worker = MigrationWorker(config)
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_progress)
        worker.completed.connect(self._on_completed)
        worker.error.connect(self._on_error)
        thread.start()
    """

    # Qt signals
    progress = Signal(int, int, int, str)  # (files_done, total_files, bytes_done, current_path)
    speed_updated = Signal(float)  # (bytes_per_second)
    completed = Signal(dict)  # (result dictionary)
    error = Signal(str)  # (error_message)
    state_changed = Signal(str)  # (MigrationState value)

    def __init__(self, config: MigrationConfig, parent=None):
        """Initialize the migration worker.

        Args:
            config: MigrationConfig with all migration settings.
            parent: Parent QObject.
        """
        if HAS_PYSIDE6:
            super().__init__(parent)
        self._config = config
        self._cancel_event = threading.Event()
        self._pause_event = threading.Event()  # Set = not paused, clear = paused
        self._pause_event.set()  # Start unpaused
        self._start_time = 0.0
        self._bytes_at_last_speed_check = 0
        self._last_speed_check_time = 0.0

    def run(self) -> None:
        """Execute the migration operation. Call via thread.started signal."""
        logger.info(
            f"MigrationWorker starting: {self._config.file_count} files, "
            f"format={self._config.output_format.value}"
        )
        self._start_time = time.time()

        try:
            if self._config.output_format == MigrationFormat.COPY_ONLY:
                self._run_copy()
            else:
                self._run_compress()

        except Exception as e:
            logger.error(f"MigrationWorker error: {e}", exc_info=True)
            self.error.emit(str(e))
            self.state_changed.emit(MigrationState.ERROR.value)

    def _run_compress(self) -> None:
        """Run compression migration."""
        self.state_changed.emit(MigrationState.COMPRESSING.value)

        compressor = Compressor(chunk_size=self._config.chunk_size)

        result = compressor.compress(
            files=self._config.selected_files,
            output_path=self._config.output_path,
            format=self._config.output_format,
            compression_level=self._config.compression_level,
            on_progress=self._on_progress,
            cancel_check=self._is_cancelled,
        )

        if result.get("cancelled"):
            self.state_changed.emit(MigrationState.CANCELLED.value)
        elif result.get("success"):
            result["duration"] = time.time() - self._start_time
            result["files"] = self._config.selected_files
            self._generate_final_report(result, self._config.output_format.value)
            self.state_changed.emit(MigrationState.COMPLETED.value)
            self.completed.emit(result)
        else:
            self.error.emit(result.get("error", "Unknown compression error"))
            self.state_changed.emit(MigrationState.ERROR.value)

    def _run_copy(self) -> None:
        """Run direct copy migration."""
        self.state_changed.emit(MigrationState.COPYING.value)

        copier = Copier(chunk_size=self._config.chunk_size)

        result = copier.copy_files(
            files=self._config.selected_files,
            target_dir=self._config.output_path,
            on_progress=self._on_progress,
            cancel_check=self._is_cancelled,
            verify=self._config.verify_after_write,
            verify_algorithm=self._config.verify_algorithm,
        )

        if result.get("cancelled"):
            self.state_changed.emit(MigrationState.CANCELLED.value)
        elif result.get("success"):
            result["duration"] = time.time() - self._start_time
            result["files"] = self._config.selected_files
            self._generate_final_report(result, self._config.output_format.value)
            self.state_changed.emit(MigrationState.COMPLETED.value)
            self.completed.emit(result)
        else:
            self.error.emit(result.get("error", "Unknown copy error"))
            self.state_changed.emit(MigrationState.ERROR.value)

    def _on_progress(self, files_done: int, total_files: int,
                     bytes_done: int, current_path: str) -> None:
        """Internal progress handler that also computes speed."""
        self.progress.emit(files_done, total_files, bytes_done, current_path)

        # Compute speed every 0.5 seconds
        now = time.time()
        if now - self._last_speed_check_time >= 0.5:
            elapsed = now - self._last_speed_check_time
            bytes_delta = bytes_done - self._bytes_at_last_speed_check
            if elapsed > 0:
                speed = bytes_delta / elapsed
                self.speed_updated.emit(speed)
            self._bytes_at_last_speed_check = bytes_done
            self._last_speed_check_time = now

    def _is_cancelled(self) -> bool:
        """Check if cancellation has been requested, with pause support."""
        while not self._pause_event.is_set():
            # Paused — wait until resumed
            if self._cancel_event.is_set():
                return True
            self._pause_event.wait(0.1)
        return self._cancel_event.is_set()

    def cancel(self) -> None:
        """Request migration cancellation."""
        logger.info("MigrationWorker cancellation requested")
        self._cancel_event.set()
        self._pause_event.set()  # Unblock if paused

    def pause(self) -> None:
        """Pause the migration operation."""
        logger.info("MigrationWorker paused")
        self._pause_event.clear()

    def resume(self) -> None:
        """Resume the migration operation."""
        logger.info("MigrationWorker resumed")
        self._pause_event.set()

    def _generate_final_report(self, result: dict, config_format: str) -> None:
        """Generate the final migration report (manifest.json + report.html).

        Args:
            result: The result dict from the migration operation.
            config_format: The migration format string.
        """
        try:
            output_dir = self._config.output_path
            if not output_dir:
                return

            # For archive formats, put report next to the archive
            if config_format != "copy_only":
                output_dir = os.path.dirname(output_dir) if os.path.isfile(output_dir) else output_dir

            migration_result = MigrationResult.from_migration_dict(
                result,
                config_format=config_format,
                verify_algorithm=self._config.verify_algorithm,
            )
            generator = ReportGenerator()
            generator.generate(migration_result, output_dir)
        except Exception as e:
            logger.warning(f"Failed to generate final migration report: {e}")
