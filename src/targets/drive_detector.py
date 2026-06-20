"""DriveDetector — detect removable, network, and local drives for migration targets."""

from __future__ import annotations

import os
from typing import List, Optional

from src.models.migration_target import DriveType, MigrationTarget
from src.utils.logger import setup_logging
from src.utils.win_utils import (
    DRIVE_CDROM,
    DRIVE_FIXED,
    DRIVE_NO_ROOT_DIR,
    DRIVE_RAMDISK,
    DRIVE_REMOTE,
    DRIVE_REMOVABLE,
    DRIVE_UNKNOWN,
    get_disk_free_space,
    get_drive_type,
    get_local_drives,
    get_volume_label,
)

logger = setup_logging()

# Windows drive type to our DriveType mapping
_DRIVE_TYPE_MAP = {
    DRIVE_UNKNOWN: DriveType.UNKNOWN,  # type: ignore[name-defined]
    DRIVE_NO_ROOT_DIR: DriveType.UNKNOWN,  # type: ignore[name-defined]
    DRIVE_REMOVABLE: DriveType.REMOVABLE,
    DRIVE_FIXED: DriveType.LOCAL,
    DRIVE_REMOTE: DriveType.NETWORK,
    DRIVE_CDROM: DriveType.CDROM,
    DRIVE_RAMDISK: DriveType.LOCAL,  # type: ignore[name-defined]
}


class DriveDetector:
    """Detects available drives and classifies them for migration targeting.

    Identifies removable drives (USB, external HDD), network shares,
    and local drives. Reports free space and volume labels.
    """

    def detect_all(self) -> List[MigrationTarget]:
        """Detect all available drives on the system.

        Returns:
            List of MigrationTarget objects for all detected drives.
        """
        targets = []
        drive_letters = get_local_drives()

        for drive_letter in drive_letters:
            target = self._create_target(drive_letter)
            if target is not None:
                targets.append(target)

        logger.info(f"Detected {len(targets)} drives: {[t.display_name for t in targets]}")
        return targets

    def detect_removable(self) -> List[MigrationTarget]:
        """Detect only removable and network drives (migration targets).

        Returns:
            List of MigrationTarget objects for removable/network drives.
        """
        all_drives = self.detect_all()
        return [d for d in all_drives if d.drive_type in (DriveType.REMOVABLE, DriveType.NETWORK)]

    def detect_migration_targets(self) -> List[MigrationTarget]:
        """Detect drives suitable as migration targets.

        Includes removable drives, network drives, and non-system local drives.
        Excludes the system drive (C:) and CD-ROM drives.

        Returns:
            List of MigrationTarget objects suitable for migration.
        """
        all_drives = self.detect_all()
        targets = []

        for drive in all_drives:
            # Skip CD-ROM
            if drive.drive_type == DriveType.CDROM:
                continue
            # Skip system drive (C:)
            if drive.drive_letter.upper() == "C:":
                continue
            # Include removable, network, and non-system local drives
            targets.append(drive)

        return targets

    def _create_target(self, drive_letter: str) -> Optional[MigrationTarget]:
        """Create a MigrationTarget from a drive letter.

        Args:
            drive_letter: Drive letter like "C:" or "D:".

        Returns:
            MigrationTarget or None if the drive is not accessible.
        """
        # Get drive type
        win_type = get_drive_type(drive_letter)
        drive_type = _DRIVE_TYPE_MAP.get(win_type, DriveType.UNKNOWN)

        # Get volume label
        label = get_volume_label(drive_letter)

        # Get disk space
        root_path = f"{drive_letter}\\"
        space_info = get_disk_free_space(root_path)

        if space_info is None:
            # Drive might not be ready (e.g., empty CD-ROM)
            logger.debug(f"Cannot get space info for {drive_letter}, skipping")
            return None

        free_bytes, total_bytes, available_bytes = space_info

        is_network = drive_type == DriveType.NETWORK

        return MigrationTarget(
            drive_letter=drive_letter,
            label=label,
            drive_type=drive_type,
            total_bytes=total_bytes,
            free_bytes=available_bytes,  # Use available (user-accessible) space
            is_network=is_network,
            path=root_path,
        )
