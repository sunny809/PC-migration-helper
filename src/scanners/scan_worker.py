"""ScanWorker — QThread-compatible worker for disk scanning."""

from __future__ import annotations

import threading
from typing import List, Optional

from src.constants import ScanState
from src.models.file_entry import FileEntry
from src.models.scan_result import ScanResult
from src.scanners.disk_scanner import DiskScanner
from src.scanners.file_classifier import FileClassifier
from src.utils.logger import setup_logging

logger = setup_logging()

try:
    from PySide6.QtCore import QObject, Signal
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False
    # Provide stub classes for non-Qt environments (testing)
    class QObject:  # type: ignore[no-redef]
        pass
    class Signal:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs):
            pass


class ScanWorker(QObject if HAS_PYSIDE6 else object):
    """Worker object for disk scanning operations.

    Designed to be moved to a QThread via moveToThread().
    All long-running scan work happens in the run() method,
    which communicates with the UI via Qt signals.

    The scan process has two phases:
    1. Estimation: Quick pre-scan to count directories for progress %
    2. Full scan: Real scan that discovers and classifies files

    Usage:
        worker = ScanWorker(classifier, roots)
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.progress.connect(self._on_scan_progress)
        worker.found_file.connect(self._on_file_found)
        worker.completed.connect(self._on_scan_completed)
        thread.start()
    """

    # Qt signals
    # progress: (scanned_dirs, files_found, progress_percent, estimated_total_dirs)
    progress = Signal(int, int, int, int)  # extended with % and estimated total
    found_file = Signal(object)  # (FileEntry)
    completed = Signal(object)  # (ScanResult)
    error = Signal(str)  # (error_message)
    state_changed = Signal(str)  # (ScanState value)
    estimation_done = Signal(int)  # estimated total dirs

    def __init__(
        self,
        classifier: FileClassifier,
        roots: List[str],
        parent=None,
    ):
        """Initialize the scan worker.

        Args:
            classifier: FileClassifier instance for categorizing files.
            roots: List of directory paths to scan.
            parent: Parent QObject.
        """
        if HAS_PYSIDE6:
            super().__init__(parent)
        self._classifier = classifier
        self._roots = roots
        self._cancel_event = threading.Event()
        self._scanner = DiskScanner(classifier)

    def run(self) -> None:
        """Execute the scan operation. Call via thread.started signal."""
        logger.info(f"ScanWorker starting scan of {len(self._roots)} roots")

        try:
            # Phase 1: Quick estimation for progress %
            self.state_changed.emit(ScanState.SCANNING.value)

            estimated_total = self._scanner.estimate_dir_count(
                roots=self._roots,
                cancel_event=self._cancel_event,
            )
            self.estimation_done.emit(estimated_total)

            if self._cancel_event.is_set():
                result = ScanResult(state=ScanState.CANCELLED)
                self.state_changed.emit(ScanState.CANCELLED.value)
                self.completed.emit(result)
                return

            # Phase 2: Full scan with percentage progress
            result = ScanResult(state=ScanState.SCANNING)

            def on_progress(scanned_dirs: int, files_found: int):
                # Calculate percentage based on estimation
                pct = 0
                if estimated_total > 0:
                    pct = min(100, int(scanned_dirs / estimated_total * 100))
                self.progress.emit(scanned_dirs, files_found, pct, estimated_total)

            def on_file(entry: FileEntry):
                result.add_file(entry)
                self.found_file.emit(entry)

            scan_result = self._scanner.scan(
                roots=self._roots,
                cancel_event=self._cancel_event,
                on_progress=on_progress,
                on_file=on_file,
            )

            # Merge scan metadata (errors, duration) into our result
            result.state = scan_result.state
            result.scan_duration = scan_result.scan_duration
            result.errors = scan_result.errors

            self.state_changed.emit(result.state.value)
            self.completed.emit(result)

        except Exception as e:
            logger.error(f"ScanWorker error: {e}", exc_info=True)
            self.error.emit(str(e))
            self.state_changed.emit(ScanState.ERROR.value)

    def cancel(self) -> None:
        """Request scan cancellation."""
        logger.info("ScanWorker cancellation requested")
        self._cancel_event.set()

    @property
    def is_cancelled(self) -> bool:
        """Whether cancellation has been requested."""
        return self._cancel_event.is_set()
