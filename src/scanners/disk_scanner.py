"""DiskScanner — full disk traversal engine for discovering personal files."""

from __future__ import annotations

import os
import stat
import time
from typing import Callable, List, Optional, Set

from src.constants import FileCategory, ScanState
from src.models.file_entry import FileEntry
from src.models.scan_result import ScanResult
from src.scanners.file_classifier import FileClassifier
from src.utils.browser_detector import BrowserDetector
from src.utils.logger import setup_logging

logger = setup_logging()


def _get_file_attributes(path: str) -> tuple[bool, bool]:
    """Get hidden and system attributes for a file/directory on Windows.

    Args:
        path: File or directory path.

    Returns:
        Tuple of (is_hidden, is_system).
    """
    is_hidden = False
    is_system = False
    try:
        attrs = os.stat(path).st_file_attributes  # type: ignore[attr-defined]
        is_hidden = bool(attrs & stat.FILE_ATTRIBUTE_HIDDEN)  # type: ignore[attr-defined]
        is_system = bool(attrs & stat.FILE_ATTRIBUTE_SYSTEM)  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        # On non-Windows or if stat fails, use name-based heuristic
        name = os.path.basename(path)
        is_hidden = name.startswith(".") or name.startswith("~")
    return is_hidden, is_system


class DiskScanner:
    """Full disk traversal engine that discovers personal files.

    Uses an iterative (stack-based) approach with os.scandir() for
    efficient traversal. Handles permission errors gracefully and
    supports cancellation via threading.Event.

    Usage:
        scanner = DiskScanner(classifier)
        result = scanner.scan(
            roots=["C:\\Users\\john", "D:\\"],
            cancel_event=threading.Event(),
            on_progress=lambda scanned, total: ...,
            on_file=lambda entry: ...,
        )
    """

    def __init__(self, classifier: FileClassifier):
        """Initialize the scanner.

        Args:
            classifier: FileClassifier instance for categorizing files.
        """
        self.classifier = classifier
        self._errors: List[str] = []
        self._scanned_dirs = 0
        self._estimated_total_dirs = 0

    def estimate_dir_count(
        self,
        roots: List[str],
        cancel_event: Optional[object] = None,
    ) -> int:
        """Quick pre-scan to estimate total directory count.

        Does a lightweight traversal counting directories without
        reading file details or classifying files. Used to provide
        a meaningful progress percentage during the real scan.

        Args:
            roots: List of directory paths to scan.
            cancel_event: threading.Event for cancellation support.

        Returns:
            Estimated total number of directories to scan.
        """
        def is_cancelled():
            return cancel_event is not None and hasattr(cancel_event, 'is_set') and cancel_event.is_set()

        total_dirs = 0
        for root in roots:
            if is_cancelled():
                break
            root = os.path.normpath(root)
            if not os.path.isdir(root):
                continue
            total_dirs += self._count_dirs_fast(root, is_cancelled)

        self._estimated_total_dirs = total_dirs
        logger.info(f"Estimated {total_dirs:,} directories to scan")
        return total_dirs

    def _count_dirs_fast(
        self,
        root: str,
        cancel_check: Callable[[], bool],
    ) -> int:
        """Fast directory-only traversal for estimation.

        Only counts directories, skips file processing entirely.
        Uses the same exclusion logic as the real scan.
        """
        count = 0
        stack = [root]

        while stack:
            if cancel_check():
                return count

            dir_path = stack.pop()
            count += 1

            # Apply same exclusion as real scan
            if self.classifier.is_excluded_path(dir_path):
                continue

            try:
                with os.scandir(dir_path) as it:
                    for entry in it:
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                is_hidden, is_system = _get_file_attributes(entry.path)
                                if is_hidden and is_system:
                                    continue
                                if self.classifier.skip_hidden and is_hidden:
                                    continue
                                if self.classifier.skip_system and is_system:
                                    continue
                                if self.classifier.is_excluded_path(entry.path):
                                    continue
                                stack.append(entry.path)
                        except (PermissionError, OSError):
                            continue
            except (PermissionError, OSError):
                continue

        return count

    def scan(
        self,
        roots: List[str],
        cancel_event: Optional[object] = None,
        on_progress: Optional[Callable[[int, int], None]] = None,
        on_file: Optional[Callable[[FileEntry], None]] = None,
        include_browser_data: bool = True,
        browser_detector: Optional[BrowserDetector] = None,
    ) -> ScanResult:
        """Scan the given root directories for personal files.

        Args:
            roots: List of directory paths to scan.
            cancel_event: threading.Event for cancellation support.
                         If set(), scanning stops at the next directory.
            on_progress: Callback(scanned_dirs, total_files_found) for
                        progress reporting.
            on_file: Callback(FileEntry) called for each discovered file.
                    If provided, files are NOT added to ScanResult.files
                    (caller manages them). If None, files are added to
                    ScanResult.files automatically.
            include_browser_data: If True, also scan for browser bookmark
                                 files and add them to the result.
            browser_detector: Optional BrowserDetector instance. If None
                             and include_browser_data is True, a default
                             detector is created.

        Returns:
            ScanResult with discovered files and metadata.
        """
        result = ScanResult(state=ScanState.SCANNING)
        self._errors = []
        self._scanned_dirs = 0
        start_time = time.time()

        # Check if cancel_event has is_set method (threading.Event interface)
        def is_cancelled():
            return cancel_event is not None and hasattr(cancel_event, 'is_set') and cancel_event.is_set()

        try:
            for root in roots:
                if is_cancelled():
                    result.state = ScanState.CANCELLED
                    break

                root = os.path.normpath(root)
                if not os.path.isdir(root):
                    logger.warning(f"Scan root does not exist: {root}")
                    continue

                logger.info(f"Starting scan of: {root}")
                self._scan_tree(
                    root=root,
                    result=result,
                    cancel_check=is_cancelled,
                    on_progress=on_progress,
                    on_file=on_file,
                )

            # Scan for browser bookmark data (in AppData, normally excluded)
            if include_browser_data and not is_cancelled():
                try:
                    detector = browser_detector or BrowserDetector()
                    bookmark_entries = detector.get_bookmark_entries()
                    for entry in bookmark_entries:
                        result.add_file(entry)
                        self._scanned_dirs += 1
                        if on_file is not None:
                            on_file(entry)
                    if bookmark_entries:
                        logger.info(f"Added {len(bookmark_entries)} browser bookmark file(s)")
                except Exception as e:
                    logger.warning(f"Browser data scan failed (non-fatal): {e}")

            if result.state == ScanState.SCANNING:
                result.state = ScanState.COMPLETED

        except Exception as e:
            logger.error(f"Scan failed with error: {e}")
            result.state = ScanState.ERROR

        result.scan_duration = time.time() - start_time
        result.errors = self._errors.copy()

        logger.info(
            f"Scan completed: {result.file_count} files, "
            f"{result.total_size} bytes, "
            f"{result.scan_duration:.1f}s, "
            f"{len(self._errors)} errors"
        )

        return result

    def _scan_tree(
        self,
        root: str,
        result: ScanResult,
        cancel_check: Callable[[], bool],
        on_progress: Optional[Callable[[int, int], None]],
        on_file: Optional[Callable[[FileEntry], None]],
    ) -> None:
        """Iteratively scan a directory tree.

        Uses os.scandir() with a stack for efficient traversal.
        """
        stack = [root]

        while stack:
            if cancel_check():
                return

            dir_path = stack.pop()
            self._scanned_dirs += 1

            # Report progress periodically (every 50 directories)
            if on_progress and self._scanned_dirs % 50 == 0:
                on_progress(self._scanned_dirs, result.file_count)

            # Check if this directory should be excluded
            if self.classifier.is_excluded_path(dir_path):
                logger.debug(f"Excluded path: {dir_path}")
                continue

            try:
                with os.scandir(dir_path) as it:
                    for entry in it:
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                self._process_directory(
                                    entry, stack, cancel_check
                                )
                            elif entry.is_file(follow_symlinks=False):
                                self._process_file(
                                    entry, result, on_file
                                )
                        except PermissionError:
                            self._errors.append(entry.path)
                        except OSError as e:
                            # Handle broken symlinks, stale handles, etc.
                            logger.debug(f"OS error on {entry.path}: {e}")
                            continue
            except PermissionError:
                self._errors.append(dir_path)
                logger.debug(f"Permission denied: {dir_path}")
            except OSError as e:
                self._errors.append(dir_path)
                logger.debug(f"Cannot scan directory {dir_path}: {e}")

    def _process_directory(
        self,
        entry: os.DirEntry,  # type: ignore[type-arg]
        stack: List[str],
        cancel_check: Callable[[], bool],
    ) -> None:
        """Process a directory entry during scanning.

        Checks if the directory should be skipped (hidden, system,
        excluded path) and adds it to the traversal stack if not.
        """
        if cancel_check():
            return

        dir_path = entry.path

        # Check attributes
        is_hidden, is_system = _get_file_attributes(dir_path)

        # Skip hidden+system directories (junction points, etc.)
        if is_hidden and is_system:
            return

        # Skip if classified as system/hidden and classifier says so
        if self.classifier.skip_hidden and is_hidden:
            return
        if self.classifier.skip_system and is_system:
            return

        # Skip if path is excluded
        if self.classifier.is_excluded_path(dir_path):
            return

        stack.append(dir_path)

    def _process_file(
        self,
        entry: os.DirEntry,  # type: ignore[type-arg]
        result: ScanResult,
        on_file: Optional[Callable[[FileEntry], None]],
    ) -> None:
        """Process a file entry during scanning.

        Classifies the file and creates a FileEntry if it passes
        all exclusion checks.
        """
        try:
            stat_result = entry.stat(follow_symlinks=False)
        except OSError:
            return

        file_path = entry.path
        file_size = stat_result.st_size

        # Check attributes
        is_hidden, is_system = _get_file_attributes(file_path)

        # Apply exclusion rules
        _, ext = os.path.splitext(file_path)
        if self.classifier.should_skip_file(
            file_path, file_size, is_hidden, is_system
        ):
            return

        # Classify the file
        category = self.classifier.classify(file_path, ext.lower())

        # Create FileEntry
        file_entry = FileEntry(
            path=file_path,
            size=file_size,
            modified_time=stat_result.st_mtime,
            category=category,
            is_selected=True,
            is_hidden=is_hidden,
        )

        # Add to result or call callback
        if on_file is not None:
            on_file(file_entry)
        else:
            result.add_file(file_entry)
