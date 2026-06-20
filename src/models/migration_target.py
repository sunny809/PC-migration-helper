"""MigrationTarget — represents a migration destination (USB drive, etc.)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class DriveType(Enum):
    """Type of storage drive."""
    LOCAL = "local"
    REMOVABLE = "removable"
    NETWORK = "network"
    CDROM = "cdrom"
    UNKNOWN = "unknown"


@dataclass
class MigrationTarget:
    """A migration destination drive or path.

    Attributes:
        drive_letter: Windows drive letter (e.g., "E:").
        label: Volume label or display name.
        drive_type: Type of drive.
        total_bytes: Total capacity in bytes.
        free_bytes: Available free space in bytes.
        is_network: Whether this is a network share.
        path: Full root path (e.g., "E:\\" or "\\\\server\\share").
    """
    drive_letter: str
    label: str
    drive_type: DriveType
    total_bytes: int
    free_bytes: int
    is_network: bool = False
    path: str = ""

    def __post_init__(self):
        if not self.path:
            if self.is_network:
                self.path = self.drive_letter
            else:
                self.path = f"{self.drive_letter}\\" if len(self.drive_letter) == 2 else self.drive_letter

    @property
    def used_bytes(self) -> int:
        """Used space in bytes."""
        return self.total_bytes - self.free_bytes

    @property
    def usage_ratio(self) -> float:
        """Space usage ratio (0.0 to 1.0)."""
        if self.total_bytes == 0:
            return 0.0
        return self.used_bytes / self.total_bytes

    @property
    def display_name(self) -> str:
        """Human-readable display name."""
        if self.label:
            return f"{self.drive_letter} - {self.label}"
        return self.drive_letter

    @property
    def type_display(self) -> str:
        """Bilingual drive type display string."""
        type_map = {
            DriveType.LOCAL: ("本地磁盘 / Local Disk", "💾"),
            DriveType.REMOVABLE: ("可移动磁盘 / Removable Disk", "🔌"),
            DriveType.NETWORK: ("网络驱动器 / Network Drive", "🌐"),
            DriveType.CDROM: ("光驱 / CD-ROM", "💿"),
            DriveType.UNKNOWN: ("未知 / Unknown", "❓"),
        }
        return type_map.get(self.drive_type, ("未知 / Unknown", "❓"))

    def has_sufficient_space(self, required_bytes: int) -> bool:
        """Check if the target has enough free space.

        Args:
            required_bytes: Required space in bytes.

        Returns:
            True if free space >= required_bytes.
        """
        return self.free_bytes >= required_bytes

    def space_deficit(self, required_bytes: int) -> int:
        """Calculate how much additional space is needed.

        Args:
            required_bytes: Required space in bytes.

        Returns:
            Additional bytes needed (0 if sufficient).
        """
        return max(0, required_bytes - self.free_bytes)
