"""Windows-specific utility functions using ctypes."""

from __future__ import annotations

import ctypes
import os
from typing import List, Optional, Tuple

from src.utils.logger import setup_logging

logger = setup_logging()


# Windows API constants
DRIVE_UNKNOWN = 0
DRIVE_NO_ROOT_DIR = 1
DRIVE_REMOVABLE = 2
DRIVE_FIXED = 3
DRIVE_REMOTE = 4
DRIVE_CDROM = 5
DRIVE_RAMDISK = 6

# Known Folder IDs (Windows Vista+)
FOLDERID_Documents = "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}"
FOLDERID_Downloads = "{374DE290-123F-4565-9164-39C4925E467B}"
FOLDERID_Desktop = "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}"
FOLDERID_Pictures = "{33E28130-4E1E-4676-835A-98395C3BC3BB}"
FOLDERID_Videos = "{18989B1D-99B5-455B-841C-AB7C74E4DDFC}"
FOLDERID_Music = "{4BD8D571-6D19-48D3-BE97-422220080E43}"
FOLDERID_Contacts = "{567A5F39-6433-4433-B046-6E6D20BA3C2C}"
FOLDERID_Favorites = "{1777F761-68AD-4D8A-87BD-30B759FA33DD}"
FOLDERID_SavedGames = "{4C5C32FF-BB9D-43B0-B5B4-2D72E54EAAA4}"
FOLDERID_Links = "{BFB9D5E0-C6A9-404C-B2B2-AE6DB6AF506A}"

# Mapping of friendly names to Known Folder IDs
KNOWN_FOLDERS = {
    "Documents": FOLDERID_Documents,
    "Downloads": FOLDERID_Downloads,
    "Desktop": FOLDERID_Desktop,
    "Pictures": FOLDERID_Pictures,
    "Videos": FOLDERID_Videos,
    "Music": FOLDERID_Music,
    "Contacts": FOLDERID_Contacts,
    "Favorites": FOLDERID_Favorites,
    "SavedGames": FOLDERID_SavedGames,
    "Links": FOLDERID_Links,
}


def get_known_folder_path(folder_id: str) -> Optional[str]:
    """Get the actual path of a Windows Known Folder.

    Uses SHGetKnownFolderPath via ctypes to resolve folder paths,
    which works even if the user has relocated their folders.

    Args:
        folder_id: A Known Folder GUID string.

    Returns:
        The folder path, or None if it cannot be resolved.
    """
    if os.name != "nt":
        # Fallback for non-Windows (development/testing)
        env_map = {
            FOLDERID_Documents: "HOME",
            FOLDERID_Desktop: "HOME",
            FOLDERID_Downloads: "HOME",
            FOLDERID_Pictures: "HOME",
            FOLDERID_Videos: "HOME",
            FOLDERID_Music: "HOME",
        }
        home = os.environ.get(env_map.get(folder_id, "HOME"), os.path.expanduser("~"))
        return home

    try:
        # SHGetKnownFolderPath
        # HRESULT SHGetKnownFolderPath(
        #   REFKNOWNFOLDERID rfid,
        #   DWORD dwFlags,
        #   HANDLE hToken,
        #   PWSTR *ppszPath
        # );
        shell32 = ctypes.windll.shell32  # type: ignore[attr-defined]
        ole32 = ctypes.windll.ole32  # type: ignore[attr-defined]

        # Convert GUID string to IID structure
        iid = ctypes.c_wchar_p(folder_id)

        ppath = ctypes.c_wchar_p()
        hr = shell32.SHGetKnownFolderPath(
            ctypes.byref(ctypes.cast(iid, ctypes.POINTER(ctypes.c_byte))),
            0,
            None,
            ctypes.byref(ppath),
        )

        if hr == 0:  # S_OK
            path = ppath.value
            ole32.CoTaskMemFree(ppath)
            return path
        else:
            logger.debug(f"SHGetKnownFolderPath failed for {folder_id}: hr={hr}")
            return None

    except (AttributeError, OSError) as e:
        logger.debug(f"Cannot call SHGetKnownFolderPath: {e}")
        return None


def get_user_known_folders() -> dict[str, str]:
    """Get all known user folders with their resolved paths.

    Returns:
        Dictionary mapping folder name to absolute path.
        Only includes folders that exist on the system.
    """
    folders = {}
    for name, folder_id in KNOWN_FOLDERS.items():
        path = get_known_folder_path(folder_id)
        if path and os.path.isdir(path):
            folders[name] = path
    return folders


def get_drive_type(drive_letter: str) -> int:
    """Get the type of a Windows drive.

    Args:
        drive_letter: Drive letter like "C:" or "C:\\".

    Returns:
        Drive type constant (DRIVE_FIXED, DRIVE_REMOVABLE, etc.).
    """
    if os.name != "nt":
        return DRIVE_FIXED  # Default for non-Windows

    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        root_path = f"{drive_letter.rstrip(chr(92))}{chr(92)}"  # "C:\"
        return kernel32.GetDriveTypeW(root_path)
    except (AttributeError, OSError):
        return DRIVE_UNKNOWN


def get_disk_free_space(drive_path: str) -> Optional[Tuple[int, int, int]]:
    """Get disk free space information.

    Args:
        drive_path: Root path like "C:\\" or "\\\\server\\share".

    Returns:
        Tuple of (free_bytes, total_bytes, available_bytes) or None on error.
        - free_bytes: Total free space on the disk
        - total_bytes: Total disk capacity
        - available_bytes: Free space available to the current user
    """
    if os.name != "nt":
        # Use os.statvfs for non-Windows
        try:
            st = os.statvfs(drive_path)
            free = st.f_bavail * st.f_frsize
            total = st.f_blocks * st.f_frsize
            available = st.f_bavail * st.f_frsize
            return (free, total, available)
        except OSError:
            return None

    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        free_bytes = ctypes.c_ulonglong(0)
        total_bytes = ctypes.c_ulonglong(0)
        available_bytes = ctypes.c_ulonglong(0)

        root_path = drive_path
        if not root_path.endswith("\\"):
            root_path += "\\"

        success = kernel32.GetDiskFreeSpaceExW(
            root_path,
            ctypes.byref(available_bytes),
            ctypes.byref(total_bytes),
            ctypes.byref(free_bytes),
        )

        if success:
            return (free_bytes.value, total_bytes.value, available_bytes.value)
        return None
    except (AttributeError, OSError):
        return None


def get_volume_label(drive_letter: str) -> str:
    """Get the volume label of a drive.

    Args:
        drive_letter: Drive letter like "C:".

    Returns:
        Volume label string, or empty string if unavailable.
    """
    if os.name != "nt":
        return ""

    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        root_path = f"{drive_letter.rstrip(chr(92))}{chr(92)}"

        volume_name = ctypes.create_unicode_buffer(256)
        file_system_name = ctypes.create_unicode_buffer(256)
        serial_number = ctypes.c_ulong(0)
        max_component_length = ctypes.c_ulong(0)
        fs_flags = ctypes.c_ulong(0)

        success = kernel32.GetVolumeInformationW(
            root_path,
            volume_name,
            ctypes.sizeof(volume_name),
            ctypes.byref(serial_number),
            ctypes.byref(max_component_length),
            ctypes.byref(fs_flags),
            file_system_name,
            ctypes.sizeof(file_system_name),
        )

        if success:
            return volume_name.value
        return ""
    except (AttributeError, OSError):
        return ""


def get_local_drives() -> List[str]:
    """Get list of local drive letters on the system.

    Returns:
        List of drive letter strings like ["C:", "D:", "E:"].
    """
    if os.name != "nt":
        # Non-Windows: return root
        return ["/"]

    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        bitmask = kernel32.GetLogicalDrives()

        drives = []
        for i in range(26):
            if bitmask & (1 << i):
                drive = f"{chr(65 + i)}:"
                drives.append(drive)
        return drives
    except (AttributeError, OSError):
        # Fallback: check common drive letters
        drives = []
        for c in "CDEFGHIJKLMNOPQRSTUVWXYZ":
            if os.path.isdir(f"{c}:\\"):
                drives.append(f"{c}:")
        return drives


def get_file_system(drive_path: str) -> str:
    """Get the file system type of a drive.

    Args:
        drive_path: Root path like "C:\\" or "E:\\".

    Returns:
        File system name string (e.g., "NTFS", "FAT32", "exFAT"),
        or empty string if unknown.
    """
    if os.name != "nt":
        # Non-Windows: try statvfs
        try:
            st = os.statvfs(drive_path)
            # Most Linux/macOS filesystems don't report type via statvfs
            # Just return a generic name
            return "unknown"
        except OSError:
            return ""

    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

        root_path = drive_path
        if not root_path.endswith("\\"):
            root_path += "\\"

        volume_name = ctypes.create_unicode_buffer(256)
        file_system_name = ctypes.create_unicode_buffer(256)
        serial_number = ctypes.c_ulong(0)
        max_component_length = ctypes.c_ulong(0)
        fs_flags = ctypes.c_ulong(0)

        success = kernel32.GetVolumeInformationW(
            root_path,
            volume_name,
            ctypes.sizeof(volume_name),
            ctypes.byref(serial_number),
            ctypes.byref(max_component_length),
            ctypes.byref(fs_flags),
            file_system_name,
            ctypes.sizeof(file_system_name),
        )

        if success:
            return file_system_name.value
        return ""
    except (AttributeError, OSError):
        return ""


# FAT32 maximum single file size (4 GB - 1 byte)
FAT32_MAX_FILE_SIZE = 4 * 1024 * 1024 * 1024 - 1  # 4,294,967,295 bytes

# File systems that have the 4GB file size limit
LIMITED_FILE_SYSTEMS = {"FAT32", "FAT", "FAT16"}


def has_file_size_limit(drive_path: str) -> tuple[bool, str]:
    """Check if a drive's file system has file size limitations.

    Args:
        drive_path: Root path like "E:\\".

    Returns:
        Tuple of (has_limit, file_system_name).
        has_limit is True if the file system has a 4GB single-file limit.
    """
    fs = get_file_system(drive_path)
    has_limit = fs.upper() in LIMITED_FILE_SYSTEMS
    return has_limit, fs
