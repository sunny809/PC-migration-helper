"""TargetWorker — QThread-compatible worker for drive detection."""

from __future__ import annotations

from typing import List

from src.models.migration_target import MigrationTarget
from src.targets.drive_detector import DriveDetector
from src.utils.logger import setup_logging

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


class TargetWorker(QObject if HAS_PYSIDE6 else object):
    """Worker object for detecting migration target drives.

    Can be run in a QThread for non-blocking drive detection.
    Also supports periodic refresh to detect USB insertion/removal.

    Usage:
        worker = TargetWorker()
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.drives_found.connect(self._on_drives_updated)
        worker.error.connect(self._on_error)
        thread.start()
    """

    # Qt signals
    drives_found = Signal(list)  # (List[MigrationTarget])
    error = Signal(str)  # (error_message)

    def __init__(self, detect_migration_targets: bool = True, parent=None):
        """Initialize the target worker.

        Args:
            detect_migration_targets: If True, only return drives suitable
                                      for migration (excludes C:, CD-ROM).
            parent: Parent QObject.
        """
        if HAS_PYSIDE6:
            super().__init__(parent)
        self._detect_migration_targets = detect_migration_targets
        self._detector = DriveDetector()

    def run(self) -> None:
        """Execute drive detection. Call via thread.started signal."""
        logger.info("TargetWorker starting drive detection")

        try:
            if self._detect_migration_targets:
                drives = self._detector.detect_migration_targets()
            else:
                drives = self._detector.detect_all()

            self.drives_found.emit(drives)

        except Exception as e:
            logger.error(f"TargetWorker error: {e}", exc_info=True)
            self.error.emit(str(e))

    def refresh(self) -> None:
        """Re-run drive detection (same as run, for clarity)."""
        self.run()
