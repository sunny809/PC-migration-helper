"""Tests for win_utils — Windows API helper functions."""

import os
import pytest

from src.utils.win_utils import (
    FAT32_MAX_FILE_SIZE,
    LIMITED_FILE_SYSTEMS,
    get_disk_free_space,
    get_file_system,
    get_known_folder_path,
    get_local_drives,
    has_file_size_limit,
)


class TestFileSystemDetection:
    """Test file system detection functions."""

    def test_get_file_system_returns_string(self):
        """get_file_system should return a string."""
        if os.name == "nt":
            result = get_file_system("C:\\")
            assert isinstance(result, str)
        else:
            # On non-Windows, it returns "unknown" or ""
            result = get_file_system("/")
            assert isinstance(result, str)

    def test_has_file_size_limit_returns_tuple(self):
        """has_file_size_limit should return (bool, str)."""
        if os.name == "nt":
            result = has_file_size_limit("C:\\")
            assert isinstance(result, tuple)
            assert len(result) == 2
            assert isinstance(result[0], bool)
            assert isinstance(result[1], str)
        else:
            # On non-Windows with statvfs
            result = has_file_size_limit("/")
            assert isinstance(result, tuple)
            assert len(result) == 2


class TestConstants:
    """Test Windows utility constants."""

    def test_fat32_max_file_size(self):
        """FAT32 max file size should be 4GB - 1 byte."""
        assert FAT32_MAX_FILE_SIZE == 4 * 1024 * 1024 * 1024 - 1
        assert FAT32_MAX_FILE_SIZE == 4294967295

    def test_limited_file_systems_contains_fat32(self):
        """LIMITED_FILE_SYSTEMS should include FAT32."""
        assert "FAT32" in LIMITED_FILE_SYSTEMS
        assert "FAT" in LIMITED_FILE_SYSTEMS
        assert "FAT16" in LIMITED_FILE_SYSTEMS

    def test_limited_file_systems_does_not_contain_ntfs(self):
        """LIMITED_FILE_SYSTEMS should NOT include NTFS."""
        assert "NTFS" not in LIMITED_FILE_SYSTEMS
        assert "exFAT" not in LIMITED_FILE_SYSTEMS


class TestKnownFolderPaths:
    """Test known folder path resolution."""

    def test_get_known_folder_path_returns_string_or_none(self):
        """Should return a string path or None."""
        result = get_known_folder_path("{FDD39AD0-238F-46AF-ADB4-6C85480369C7}")
        assert result is None or isinstance(result, str)

    def test_get_known_folder_path_invalid_guid(self):
        """Invalid GUID should return None or a fallback path."""
        result = get_known_folder_path("{00000000-0000-0000-0000-000000000000}")
        # On non-Windows, the fallback may return HOME for any GUID
        # So we just check it returns a string or None
        assert result is None or isinstance(result, str)


class TestDriveDetection:
    """Test drive detection functions."""

    def test_get_local_drives_returns_list(self):
        """Should return a list of drive strings."""
        drives = get_local_drives()
        assert isinstance(drives, list)
        assert len(drives) > 0

    def test_get_disk_free_space_returns_tuple_or_none(self):
        """Should return (free, total, available) tuple or None."""
        if os.name == "nt":
            result = get_disk_free_space("C:\\")
        else:
            result = get_disk_free_space("/")

        if result is not None:
            assert isinstance(result, tuple)
            assert len(result) == 3
            free, total, available = result
            assert total >= 0
            assert free >= 0
            assert available >= 0
