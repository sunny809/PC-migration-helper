"""Compressor — ZIP and 7z compression engine with progress reporting."""

from __future__ import annotations

import os
import time
import zipfile
from typing import Callable, List, Optional

from src.constants import DEFAULT_CHUNK_SIZE, MigrationFormat
from src.models.file_entry import FileEntry
from src.utils.logger import setup_logging

logger = setup_logging()

# Progress callback type: (files_processed, total_files, bytes_processed, current_file_path)
ProgressCallback = Callable[[int, int, int, str], None]


class Compressor:
    """Compression engine supporting ZIP and 7z formats.

    Reports progress via callbacks for UI integration.
    Handles errors gracefully (missing files, permission errors).
    """

    def __init__(self, chunk_size: int = DEFAULT_CHUNK_SIZE):
        """Initialize the compressor.

        Args:
            chunk_size: Read/write buffer size in bytes.
        """
        self.chunk_size = chunk_size
        self._cancelled = False

    def cancel(self) -> None:
        """Request cancellation of the current operation."""
        self._cancelled = True

    def compress(
        self,
        files: List[FileEntry],
        output_path: str,
        format: MigrationFormat = MigrationFormat.ZIP,
        compression_level: int = 5,
        on_progress: Optional[ProgressCallback] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> dict:
        """Compress files into an archive.

        Args:
            files: List of FileEntry objects to compress.
            output_path: Full path for the output archive.
            format: Compression format (ZIP or SEVEN_ZIP).
            compression_level: Compression level (0-9).
            on_progress: Progress callback(files_done, total_files, bytes_done, current_path).
            cancel_check: Function that returns True if operation should be cancelled.

        Returns:
            Dictionary with 'success', 'files_processed', 'bytes_processed',
            'errors', and 'output_path' keys.
        """
        self._cancelled = False
        total_files = len(files)
        files_processed = 0
        bytes_processed = 0
        errors: List[str] = []

        if format == MigrationFormat.ZIP:
            result = self._compress_zip(
                files, output_path, compression_level,
                on_progress, cancel_check
            )
        elif format == MigrationFormat.SEVEN_ZIP:
            result = self._compress_7z(
                files, output_path, compression_level,
                on_progress, cancel_check
            )
        else:
            return {
                "success": False,
                "error": f"Unsupported format: {format}",
                "files_processed": 0,
                "bytes_processed": 0,
                "errors": [],
            }

        return result

    def _compress_zip(
        self,
        files: List[FileEntry],
        output_path: str,
        compression_level: int,
        on_progress: Optional[ProgressCallback],
        cancel_check: Optional[Callable[[], bool]],
    ) -> dict:
        """Compress files into a ZIP archive."""
        total_files = len(files)
        files_processed = 0
        bytes_processed = 0
        errors: List[str] = []

        # Map compression level (0-9) to zipfile constants
        # 0 = stored, 1-9 = compressed (higher = more compression)
        zip_compression = zipfile.ZIP_DEFLATED if compression_level > 0 else zipfile.ZIP_STORED
        compresslevel = min(9, max(0, compression_level))

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        try:
            with zipfile.ZipFile(
                output_path, "w",
                compression=zip_compression,
                compresslevel=compresslevel,
            ) as zf:
                for i, file_entry in enumerate(files):
                    # Check cancellation
                    if cancel_check and cancel_check():
                        logger.info("ZIP compression cancelled by user")
                        return {
                            "success": False,
                            "cancelled": True,
                            "files_processed": files_processed,
                            "bytes_processed": bytes_processed,
                            "errors": errors,
                            "output_path": output_path,
                        }

                    if not os.path.exists(file_entry.path):
                        errors.append(f"File not found: {file_entry.path}")
                        files_processed += 1
                        continue

                    try:
                        # Store with relative path to preserve directory structure
                        arcname = file_entry.path.lstrip(os.sep)

                        # Add file to archive
                        zf.write(file_entry.path, arcname=arcname)

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

        except Exception as e:
            logger.error(f"ZIP compression failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "files_processed": files_processed,
                "bytes_processed": bytes_processed,
                "errors": errors,
                "output_path": output_path,
            }

        logger.info(
            f"ZIP compression complete: {files_processed}/{total_files} files, "
            f"{bytes_processed} bytes, {len(errors)} errors"
        )

        return {
            "success": True,
            "files_processed": files_processed,
            "bytes_processed": bytes_processed,
            "errors": errors,
            "output_path": output_path,
        }

    def _compress_7z(
        self,
        files: List[FileEntry],
        output_path: str,
        compression_level: int,
        on_progress: Optional[ProgressCallback],
        cancel_check: Optional[Callable[[], bool]],
    ) -> dict:
        """Compress files into a 7z archive using py7zr."""
        try:
            import py7zr
        except ImportError:
            logger.error("py7zr is not installed. Falling back to ZIP format.")
            zip_path = output_path.replace(".7z", ".zip")
            return self._compress_zip(
                files, zip_path, compression_level,
                on_progress, cancel_check
            )

        total_files = len(files)
        files_processed = 0
        bytes_processed = 0
        errors: List[str] = []

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Build list of (path, arcname) pairs
        file_pairs = []
        for file_entry in files:
            if not os.path.exists(file_entry.path):
                errors.append(f"File not found: {file_entry.path}")
                files_processed += 1
                continue
            arcname = file_entry.path.lstrip(os.sep)
            file_pairs.append((file_entry.path, arcname))

        try:
            filters = [{"id": py7zr.FILTER_LZMA, "level": min(9, max(0, compression_level))}]

            with py7zr.SevenZipFile(
                output_path, "w", filters=filters
            ) as zf:
                for file_path, arcname in file_pairs:
                    # Check cancellation
                    if cancel_check and cancel_check():
                        logger.info("7z compression cancelled by user")
                        return {
                            "success": False,
                            "cancelled": True,
                            "files_processed": files_processed,
                            "bytes_processed": bytes_processed,
                            "errors": errors,
                            "output_path": output_path,
                        }

                    try:
                        zf.write(file_path, arcname)

                        # Get file size for progress
                        file_size = os.path.getsize(file_path)
                        bytes_processed += file_size
                        files_processed += 1

                        if on_progress:
                            on_progress(files_processed, total_files, bytes_processed, file_path)

                    except PermissionError:
                        errors.append(f"Permission denied: {file_path}")
                        files_processed += 1
                    except OSError as e:
                        errors.append(f"OS error on {file_path}: {e}")
                        files_processed += 1

        except Exception as e:
            logger.error(f"7z compression failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "files_processed": files_processed,
                "bytes_processed": bytes_processed,
                "errors": errors,
                "output_path": output_path,
            }

        logger.info(
            f"7z compression complete: {files_processed}/{total_files} files, "
            f"{bytes_processed} bytes, {len(errors)} errors"
        )

        return {
            "success": True,
            "files_processed": files_processed,
            "bytes_processed": bytes_processed,
            "errors": errors,
            "output_path": output_path,
        }
