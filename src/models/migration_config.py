"""MigrationConfig — user's migration choices and settings."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from src.constants import MigrationFormat
from src.models.file_entry import FileEntry
from src.models.migration_target import MigrationTarget


@dataclass
class MigrationConfig:
    """Configuration for a migration operation.

    Attributes:
        selected_files: Files selected for migration.
        target: Migration destination.
        output_format: Compression format or copy-only.
        compression_level: Compression level (1-9 for 7z, 0-9 for zip).
        output_filename: Name of the output archive (without extension).
        verify_after_write: Whether to verify files after writing.
        chunk_size: Read/write buffer size in bytes.
    """
    selected_files: List[FileEntry] = field(default_factory=list)
    target: Optional[MigrationTarget] = None
    output_format: MigrationFormat = MigrationFormat.SEVEN_ZIP
    compression_level: int = 5
    output_filename: str = "migration_backup"
    verify_after_write: bool = True
    verify_algorithm: str = "xxhash"  # "xxhash" (fast) or "sha256" (secure)
    chunk_size: int = 65536  # 64 KB

    @property
    def total_size(self) -> int:
        """Total size of selected files in bytes."""
        return sum(f.size for f in self.selected_files)

    @property
    def file_count(self) -> int:
        """Number of selected files."""
        return len(self.selected_files)

    @property
    def output_path(self) -> str:
        """Full output path including filename and extension."""
        if self.target is None:
            return ""

        import os
        ext_map = {
            MigrationFormat.ZIP: ".zip",
            MigrationFormat.SEVEN_ZIP: ".7z",
            MigrationFormat.COPY_ONLY: "",
        }
        ext = ext_map.get(self.output_format, "")

        if self.output_format == MigrationFormat.COPY_ONLY:
            # For copy-only, create a folder
            return os.path.join(self.target.path, self.output_filename)

        return os.path.join(self.target.path, f"{self.output_filename}{ext}")

    @property
    def estimated_output_size(self) -> int:
        """Rough estimate of output size.

        Compression ratios are conservative estimates:
        - ZIP: ~60% of original
        - 7z: ~50% of original
        - Copy: 100% of original
        """
        ratio_map = {
            MigrationFormat.ZIP: 0.6,
            MigrationFormat.SEVEN_ZIP: 0.5,
            MigrationFormat.COPY_ONLY: 1.0,
        }
        ratio = ratio_map.get(self.output_format, 1.0)
        return int(self.total_size * ratio)

    def is_ready(self) -> bool:
        """Check if all required configuration is set for migration."""
        return (
            len(self.selected_files) > 0
            and self.target is not None
            and self.target.has_sufficient_space(self.estimated_output_size)
        )
