"""MigrationResult — complete record of a migration operation.

Serializable to JSON for migration reports and manifests.
Supports both preview (after scan) and final (after migration) modes.
"""

from __future__ import annotations

import json
import os
import platform
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional

from src.constants import APP_VERSION, FileCategory, MigrationFormat
from src.models.file_entry import FileEntry
from src.models.scan_result import ScanResult


@dataclass
class FileRecord:
    """Record of a single file in a migration manifest.

    Attributes:
        path: Relative path (e.g. "Documents/report.docx").
        size: File size in bytes.
        modified: Last modification timestamp (epoch seconds).
        hash: File hash string ("algorithm:hexdigest"), or "" if not computed.
        category: File category string value.
        status: "ok", "failed", or "skipped".
    """
    path: str
    size: int
    modified: float
    hash: str
    category: str
    status: str = "ok"

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "size": self.size,
            "modified": self.modified,
            "hash": self.hash,
            "category": self.category,
            "status": self.status,
        }

    @classmethod
    def from_file_entry(cls, entry: FileEntry, hash_value: str = "",
                        status: str = "ok") -> "FileRecord":
        """Create a FileRecord from a FileEntry, normalizing the path.

        Strips drive letter or leading slash to produce a portable relative path.
        """
        raw = entry.path.replace("\\", "/")
        if len(raw) >= 2 and raw[1] == ":":
            raw = raw[2:].lstrip("/")
        raw = raw.lstrip("/")

        return cls(
            path=raw,
            size=entry.size,
            modified=entry.modified_time,
            hash=hash_value,
            category=entry.category.value,
            status=status,
        )


@dataclass
class MigrationResult:
    """Complete record of a scan or migration operation.

    Can represent either:
    - A scan preview (before migration): files listed, no verify results yet
    - A final migration result: files + verify results + destination info

    Attributes:
        created: ISO-8601 timestamp of creation.
        source_pc: Source computer name.
        app_version: Application version that created this report.
        format: Migration format ("zip", "7z", "copy_only"), or "preview".
        verify_algorithm: Hash algorithm used, or "".
        total_files: Total number of files.
        total_size: Total size in bytes.
        categories: Per-category stats.
        files: List of FileRecord entries.
        verify_passed: Files that passed verification.
        verify_failed: Files that failed verification.
        verify_skipped: Files skipped during verification.
        errors: List of error messages.
        destination: Target path (final reports).
        output_path: Path to output archive/directory (final reports).
    """
    created: str = ""
    source_pc: str = ""
    app_version: str = APP_VERSION
    format: str = "preview"
    verify_algorithm: str = ""
    total_files: int = 0
    total_size: int = 0
    categories: Dict[str, dict] = field(default_factory=dict)
    files: List[FileRecord] = field(default_factory=list)
    verify_passed: int = 0
    verify_failed: int = 0
    verify_skipped: int = 0
    errors: List[str] = field(default_factory=list)
    destination: str = ""
    output_path: str = ""

    def __post_init__(self):
        if not self.created:
            self.created = datetime.now().isoformat()
        if not self.source_pc:
            self.source_pc = platform.node()

    @classmethod
    def from_scan_result(cls, result: ScanResult,
                         verify_algorithm: str = "") -> "MigrationResult":
        """Create a MigrationResult from a ScanResult (preview mode)."""
        categories = {}
        for cat in FileCategory:
            count = result.category_counts.get(cat, 0)
            size = result.category_sizes.get(cat, 0)
            if count > 0:
                categories[cat.value] = {"count": count, "size": size}

        files = []
        for entry in result.files:
            files.append(FileRecord.from_file_entry(entry))

        return cls(
            format="preview",
            verify_algorithm=verify_algorithm,
            total_files=result.file_count,
            total_size=result.total_size,
            categories=categories,
            files=files,
            errors=result.errors.copy(),
        )

    @classmethod
    def from_migration_dict(cls, result_dict: dict,
                            config_format: str = "copy_only",
                            verify_algorithm: str = "") -> "MigrationResult":
        """Create from a migration worker's result dict."""
        files = []
        for f in result_dict.get("files", []):
            if isinstance(f, FileEntry):
                hash_value = result_dict.get("verify_results", {}).get(f.path, "")
                files.append(FileRecord.from_file_entry(f, hash_value))
            elif isinstance(f, dict):
                files.append(FileRecord(**f))

        cat_counts: Dict[str, int] = {}
        cat_sizes: Dict[str, int] = {}
        for f in files:
            cat = f.category
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
            cat_sizes[cat] = cat_sizes.get(cat, 0) + f.size

        categories = {}
        for cat, count in cat_counts.items():
            categories[cat] = {"count": count, "size": cat_sizes.get(cat, 0)}

        verify_failures = result_dict.get("verify_failures", [])
        total = len(files)
        failed = len(verify_failures)

        return cls(
            format=config_format,
            verify_algorithm=verify_algorithm,
            total_files=total,
            total_size=result_dict.get("bytes_processed", 0),
            categories=categories,
            files=files,
            verify_passed=total - failed,
            verify_failed=failed,
            errors=result_dict.get("errors", []),
            destination=result_dict.get("target_dir", ""),
            output_path=result_dict.get("output_path", ""),
        )

    def to_json(self, path: str, indent: int = 2) -> str:
        """Serialize to JSON and write to a file.

        Args:
            path: Output file path.
            indent: JSON indentation level.

        Returns:
            The JSON string written to the file.
        """
        data = {
            "created": self.created,
            "source_pc": self.source_pc,
            "app_version": self.app_version,
            "format": self.format,
            "verify_algorithm": self.verify_algorithm,
            "total_files": self.total_files,
            "total_size": self.total_size,
            "categories": self.categories,
            "files": [f.to_dict() for f in self.files],
            "verify_passed": self.verify_passed,
            "verify_failed": self.verify_failed,
            "verify_skipped": self.verify_skipped,
            "errors": self.errors,
            "destination": self.destination,
            "output_path": self.output_path,
        }
        json_str = json.dumps(data, indent=indent, ensure_ascii=False)
        with open(path, "w", encoding="utf-8") as f:
            f.write(json_str)
        return json_str

    @classmethod
    def from_json(cls, path: str) -> "MigrationResult":
        """Deserialize from a JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        files = [FileRecord(**f) for f in data.pop("files", [])]
        result = cls(**data)
        result.files = files
        return result

    @property
    def is_preview(self) -> bool:
        return self.format == "preview"

    @property
    def is_final(self) -> bool:
        return self.format != "preview"

    @property
    def verify_summary(self) -> str:
        if self.verify_failed > 0:
            return f"{self.verify_passed} passed, {self.verify_failed} FAILED"
        return f"{self.verify_passed} passed"
