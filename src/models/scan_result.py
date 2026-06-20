"""ScanResult — aggregate result of a disk scan operation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from src.constants import FileCategory, ScanState
from src.models.file_entry import FileEntry


@dataclass
class ScanResult:
    """Aggregate result of a disk scan.

    Attributes:
        state: Current scan state.
        files: List of discovered file entries.
        total_size: Total size of all discovered files in bytes.
        category_counts: Number of files per category.
        category_sizes: Total size per category in bytes.
        scan_duration: Scan duration in seconds.
        errors: List of paths that caused permission/access errors.
    """
    state: ScanState = ScanState.IDLE
    files: List[FileEntry] = field(default_factory=list)
    total_size: int = 0
    category_counts: dict = field(default_factory=lambda: {c: 0 for c in FileCategory})
    category_sizes: dict = field(default_factory=lambda: {c: 0 for c in FileCategory})
    scan_duration: float = 0.0
    errors: List[str] = field(default_factory=list)

    def add_file(self, entry: FileEntry) -> None:
        """Add a file entry and update aggregates."""
        self.files.append(entry)
        self.total_size += entry.size
        self.category_counts[entry.category] = self.category_counts.get(entry.category, 0) + 1
        self.category_sizes[entry.category] = self.category_sizes.get(entry.category, 0) + entry.size

    @property
    def file_count(self) -> int:
        """Total number of discovered files."""
        return len(self.files)

    @property
    def error_count(self) -> int:
        """Number of directories/files skipped due to errors."""
        return len(self.errors)

    def get_files_by_category(self, category: FileCategory) -> List[FileEntry]:
        """Get all files belonging to a specific category."""
        return [f for f in self.files if f.category == category]

    def get_selected_files(self) -> List[FileEntry]:
        """Get all files currently selected for migration."""
        return [f for f in self.files if f.is_selected]

    @property
    def selected_size(self) -> int:
        """Total size of selected files."""
        return sum(f.size for f in self.files if f.is_selected)

    @property
    def selected_count(self) -> int:
        """Number of selected files."""
        return sum(1 for f in self.files if f.is_selected)
