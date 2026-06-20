"""FileEntry data class — represents a single discovered file."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from src.constants import FileCategory


@dataclass
class FileEntry:
    """A single file discovered during scanning.

    Attributes:
        path: Absolute file path.
        size: File size in bytes.
        modified_time: Last modification timestamp (epoch seconds).
        category: Classified file category.
        is_selected: Whether this file is selected for migration.
        is_hidden: Whether the file has the hidden attribute.
    """
    path: str
    size: int
    modified_time: float
    category: FileCategory = FileCategory.OTHER
    is_selected: bool = True
    is_hidden: bool = False

    @property
    def name(self) -> str:
        """File name without directory path."""
        return os.path.basename(self.path)

    @property
    def dir_path(self) -> str:
        """Parent directory path."""
        return os.path.dirname(self.path)

    @property
    def extension(self) -> str:
        """File extension in lowercase (including the dot)."""
        _, ext = os.path.splitext(self.path)
        return ext.lower()

    @property
    def modified_datetime(self) -> datetime:
        """Modification time as a datetime object."""
        return datetime.fromtimestamp(self.modified_time)

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON export."""
        return {
            "path": self.path,
            "size": self.size,
            "modified_time": self.modified_time,
            "category": self.category.value,
            "is_selected": self.is_selected,
            "is_hidden": self.is_hidden,
        }

    @classmethod
    def from_dict(cls, data: dict) -> FileEntry:
        """Deserialize from dictionary."""
        data["category"] = FileCategory(data["category"])
        return cls(**data)
