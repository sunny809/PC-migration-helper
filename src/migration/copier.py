"""Copier — direct file copy engine with progress reporting."""

from __future__ import annotations

import os
import shutil
from typing import Callable, List, Optional

from src.constants import DEFAULT_CHUNK_SIZE
from src.models.file_entry import FileEntry
from src.utils.logger import setup_logging

logger = setup_logging()

# Progress callback type: (files_processed, total_files, bytes_processed, current_file_path)
ProgressCallback = Callable[[int, int, int, str], None]


class Copier:
    """Direct file copy engine that preserves directory structure.

    Copies files to a target directory while maintaining their
    relative directory structure. Reports progress via callbacks.
    """

    def __init__(self, chunk_size: int = DEFAULT_CHUNK_SIZE):
        """Initialize the copier.

        Args:
            chunk_size: Read/write buffer size in bytes for large files.
        """
        self.chunk_size = chunk_size
        self._cancelled = False

    def cancel(self) -> None:
        """Request cancellation of the current operation."""
        self._cancelled = True

    def copy_files(
        self,
        files: List[FileEntry],
        target_dir: str,
        on_progress: Optional[ProgressCallback] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
        verify: bool = False,
        verify_algorithm: str = "xxhash",
    ) -> dict:
        """Copy files to a target directory, preserving directory structure.

        Args:
            files: List of FileEntry objects to copy.
            target_dir: Target directory path.
            on_progress: Progress callback(files_done, total_files, bytes_done, current_path).
            cancel_check: Function that returns True if operation should be cancelled.
            verify: Whether to verify files after copying.
            verify_algorithm: Hash algorithm for verification ("xxhash" or "sha256").

        Returns:
            Dictionary with 'success', 'files_processed', 'bytes_processed',
            'errors', 'target_dir', and 'verify_failures' keys.
        """
        self._cancelled = False
        total_files = len(files)
        files_processed = 0
        bytes_processed = 0
        errors: List[str] = []
        verify_failures: List[str] = []

        # Ensure target directory exists
        os.makedirs(target_dir, exist_ok=True)

        for file_entry in files:
            # Check cancellation
            if cancel_check and cancel_check():
                logger.info("Copy operation cancelled by user")
                return {
                    "success": False,
                    "cancelled": True,
                    "files_processed": files_processed,
                    "bytes_processed": bytes_processed,
                    "errors": errors,
                    "target_dir": target_dir,
                    "verify_failures": verify_failures,
                }

            if not os.path.exists(file_entry.path):
                errors.append(f"File not found: {file_entry.path}")
                files_processed += 1
                continue

            try:
                # Compute relative path and target path
                # Strip drive letter and leading separator
                _, rel_path = os.path.splitdrive(file_entry.path)
                rel_path = rel_path.lstrip(os.sep)
                target_path = os.path.join(target_dir, rel_path)

                # Create target directory structure
                target_file_dir = os.path.dirname(target_path)
                os.makedirs(target_file_dir, exist_ok=True)

                # Copy the file
                self._copy_single_file(file_entry.path, target_path)

                # Verify after copy
                if verify:
                    from src.utils.checksum import verify_file
                    is_match, reason = verify_file(
                        file_entry.path, target_path,
                        algorithm=verify_algorithm,
                        chunk_size=self.chunk_size,
                    )
                    if not is_match:
                        verify_failures.append(
                            f"Verify failed: {file_entry.path} → {target_path} ({reason})"
                        )
                        logger.warning(f"Verify failed for {file_entry.path}: {reason}")

                file_size = file_entry.size
                bytes_processed += file_size
                files_processed += 1

                if on_progress:
                    on_progress(files_processed, total_files, bytes_processed, file_entry.path)

            except PermissionError:
                errors.append(f"Permission denied: {file_entry.path}")
                files_processed += 1
            except OSError as e:
                errors.append(f"OS error on {file_entry.path}: {e}")
                files_processed += 1

        success = len(errors) == 0 or files_processed > 0
        logger.info(
            f"Copy complete: {files_processed}/{total_files} files, "
            f"{bytes_processed} bytes, {len(errors)} errors, "
            f"{len(verify_failures)} verify failures"
        )

        return {
            "success": success,
            "files_processed": files_processed,
            "bytes_processed": bytes_processed,
            "errors": errors,
            "target_dir": target_dir,
            "verify_failures": verify_failures,
        }

    def _copy_single_file(self, src: str, dst: str) -> None:
        """Copy a single file with chunked I/O for progress support.

        Uses shutil.copy2 for small files and chunked copy for large files
        to enable progress reporting.

        Args:
            src: Source file path.
            dst: Destination file path.
        """
        file_size = os.path.getsize(src)

        # For small files (< 1MB), use shutil for simplicity
        if file_size < 1024 * 1024:
            shutil.copy2(src, dst)
            return

        # For large files, use chunked copy
        with open(src, "rb") as fsrc:
            with open(dst, "wb") as fdst:
                while True:
                    chunk = fsrc.read(self.chunk_size)
                    if not chunk:
                        break
                    fdst.write(chunk)

        # Copy metadata (timestamps)
        try:
            shutil.copystat(src, dst)
        except OSError:
            pass  # Some metadata may not be copyable
