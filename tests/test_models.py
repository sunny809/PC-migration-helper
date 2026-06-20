"""Tests for data models — FileEntry, ScanResult, MigrationTarget, MigrationConfig."""

import os
from datetime import datetime

import pytest

from src.constants import FileCategory, MigrationFormat


class TestFileEntry:
    """Test FileEntry dataclass."""

    def test_name_property(self):
        from src.models.file_entry import FileEntry
        entry = FileEntry(path="C:\\Users\\test\\report.docx", size=1024, modified_time=0.0)
        # Use PureWindowsPath for consistent results across platforms
        from pathlib import PureWindowsPath
        assert PureWindowsPath(entry.path).name == "report.docx"

    def test_dir_path_property(self):
        from src.models.file_entry import FileEntry
        entry = FileEntry(path="C:\\Users\\test\\report.docx", size=1024, modified_time=0.0)
        from pathlib import PureWindowsPath
        assert PureWindowsPath(entry.path).parent == PureWindowsPath("C:\\Users\\test")

    def test_extension_property_lowercase(self):
        from src.models.file_entry import FileEntry
        entry = FileEntry(path="C:\\Photos\\IMG.JPG", size=2048, modified_time=0.0)
        assert entry.extension == ".jpg"

    def test_extension_no_extension(self):
        from src.models.file_entry import FileEntry
        entry = FileEntry(path="C:\\file_no_ext", size=100, modified_time=0.0)
        assert entry.extension == ""

    def test_modified_datetime_property(self):
        from src.models.file_entry import FileEntry
        ts = 1700000000.0
        entry = FileEntry(path="test.txt", size=50, modified_time=ts)
        dt = entry.modified_datetime
        assert isinstance(dt, datetime)
        assert dt.year > 2020

    def test_default_values(self):
        from src.models.file_entry import FileEntry
        entry = FileEntry(path="test.txt", size=100, modified_time=0.0)
        assert entry.category == FileCategory.OTHER
        assert entry.is_selected is True
        assert entry.is_hidden is False

    def test_to_dict_roundtrip(self):
        from src.models.file_entry import FileEntry
        entry = FileEntry(
            path="C:\\test.docx", size=500, modified_time=12345.0,
            category=FileCategory.DOCUMENTS, is_selected=False, is_hidden=True,
        )
        d = entry.to_dict()
        assert d["path"] == "C:\\test.docx"
        assert d["category"] == "documents"
        assert d["is_selected"] is False

    def test_from_dict(self):
        from src.models.file_entry import FileEntry
        data = {
            "path": "test.pdf", "size": 200, "modified_time": 99.0,
            "category": "documents", "is_selected": True, "is_hidden": False,
        }
        entry = FileEntry.from_dict(data)
        assert entry.path == "test.pdf"
        assert entry.category == FileCategory.DOCUMENTS


class TestScanResult:
    """Test ScanResult dataclass."""

    def test_add_file_updates_aggregates(self):
        from src.models.file_entry import FileEntry
        from src.models.scan_result import ScanResult
        result = ScanResult()
        entry = FileEntry(path="a.docx", size=100, modified_time=0, category=FileCategory.DOCUMENTS)
        result.add_file(entry)
        assert result.file_count == 1
        assert result.total_size == 100
        assert result.category_counts[FileCategory.DOCUMENTS] == 1
        assert result.category_sizes[FileCategory.DOCUMENTS] == 100

    def test_add_multiple_files_different_categories(self):
        from src.models.file_entry import FileEntry
        from src.models.scan_result import ScanResult
        result = ScanResult()
        result.add_file(FileEntry(path="a.docx", size=100, modified_time=0, category=FileCategory.DOCUMENTS))
        result.add_file(FileEntry(path="b.jpg", size=200, modified_time=0, category=FileCategory.PHOTOS))
        result.add_file(FileEntry(path="c.mp3", size=300, modified_time=0, category=FileCategory.MUSIC))

        assert result.file_count == 3
        assert result.total_size == 600
        assert result.category_counts[FileCategory.DOCUMENTS] == 1
        assert result.category_counts[FileCategory.PHOTOS] == 1
        assert result.category_counts[FileCategory.MUSIC] == 1

    def test_error_count(self):
        from src.models.scan_result import ScanResult
        result = ScanResult(errors=["/dir1", "/dir2"])
        assert result.error_count == 2

    def test_get_files_by_category(self):
        from src.models.file_entry import FileEntry
        from src.models.scan_result import ScanResult
        result = ScanResult()
        result.add_file(FileEntry(path="a.docx", size=100, modified_time=0, category=FileCategory.DOCUMENTS))
        result.add_file(FileEntry(path="b.docx", size=200, modified_time=0, category=FileCategory.DOCUMENTS))
        result.add_file(FileEntry(path="c.jpg", size=300, modified_time=0, category=FileCategory.PHOTOS))

        docs = result.get_files_by_category(FileCategory.DOCUMENTS)
        assert len(docs) == 2
        photos = result.get_files_by_category(FileCategory.PHOTOS)
        assert len(photos) == 1

    def test_get_selected_files(self):
        from src.models.file_entry import FileEntry
        from src.models.scan_result import ScanResult
        result = ScanResult()
        result.add_file(FileEntry(path="a.docx", size=100, modified_time=0, is_selected=True))
        result.add_file(FileEntry(path="b.jpg", size=200, modified_time=0, is_selected=False))

        selected = result.get_selected_files()
        assert len(selected) == 1
        assert selected[0].path == "a.docx"

    def test_selected_size(self):
        from src.models.file_entry import FileEntry
        from src.models.scan_result import ScanResult
        result = ScanResult()
        result.add_file(FileEntry(path="a.docx", size=100, modified_time=0, is_selected=True))
        result.add_file(FileEntry(path="b.jpg", size=200, modified_time=0, is_selected=False))

        assert result.selected_size == 100

    def test_selected_count(self):
        from src.models.file_entry import FileEntry
        from src.models.scan_result import ScanResult
        result = ScanResult()
        result.add_file(FileEntry(path="a.docx", size=100, modified_time=0, is_selected=True))
        result.add_file(FileEntry(path="b.jpg", size=200, modified_time=0, is_selected=False))

        assert result.selected_count == 1

    def test_empty_result(self):
        from src.models.scan_result import ScanResult
        result = ScanResult()
        assert result.file_count == 0
        assert result.total_size == 0
        assert result.error_count == 0
        assert result.selected_size == 0


class TestMigrationTarget:
    """Test MigrationTarget dataclass."""

    def test_used_bytes(self):
        from src.models.migration_target import DriveType, MigrationTarget
        t = MigrationTarget(drive_letter="E:", label="USB", drive_type=DriveType.REMOVABLE,
                           total_bytes=1000, free_bytes=300)
        assert t.used_bytes == 700

    def test_usage_ratio(self):
        from src.models.migration_target import DriveType, MigrationTarget
        t = MigrationTarget(drive_letter="E:", label="", drive_type=DriveType.REMOVABLE,
                           total_bytes=1000, free_bytes=200)
        assert t.usage_ratio == 0.8

    def test_usage_ratio_zero_total(self):
        from src.models.migration_target import DriveType, MigrationTarget
        t = MigrationTarget(drive_letter="E:", label="", drive_type=DriveType.REMOVABLE,
                           total_bytes=0, free_bytes=0)
        assert t.usage_ratio == 0.0

    def test_display_name_with_label(self):
        from src.models.migration_target import DriveType, MigrationTarget
        t = MigrationTarget(drive_letter="E:", label="MyUSB", drive_type=DriveType.REMOVABLE,
                           total_bytes=1000, free_bytes=500)
        assert t.display_name == "E: - MyUSB"

    def test_display_name_without_label(self):
        from src.models.migration_target import DriveType, MigrationTarget
        t = MigrationTarget(drive_letter="E:", label="", drive_type=DriveType.REMOVABLE,
                           total_bytes=1000, free_bytes=500)
        assert t.display_name == "E:"

    def test_has_sufficient_space_true(self):
        from src.models.migration_target import DriveType, MigrationTarget
        t = MigrationTarget(drive_letter="E:", label="", drive_type=DriveType.REMOVABLE,
                           total_bytes=1000, free_bytes=500)
        assert t.has_sufficient_space(400) is True

    def test_has_sufficient_space_false(self):
        from src.models.migration_target import DriveType, MigrationTarget
        t = MigrationTarget(drive_letter="E:", label="", drive_type=DriveType.REMOVABLE,
                           total_bytes=1000, free_bytes=500)
        assert t.has_sufficient_space(600) is False

    def test_has_sufficient_space_exact(self):
        from src.models.migration_target import DriveType, MigrationTarget
        t = MigrationTarget(drive_letter="E:", label="", drive_type=DriveType.REMOVABLE,
                           total_bytes=1000, free_bytes=500)
        assert t.has_sufficient_space(500) is True

    def test_space_deficit_positive(self):
        from src.models.migration_target import DriveType, MigrationTarget
        t = MigrationTarget(drive_letter="E:", label="", drive_type=DriveType.REMOVABLE,
                           total_bytes=1000, free_bytes=300)
        assert t.space_deficit(500) == 200

    def test_space_deficit_zero(self):
        from src.models.migration_target import DriveType, MigrationTarget
        t = MigrationTarget(drive_letter="E:", label="", drive_type=DriveType.REMOVABLE,
                           total_bytes=1000, free_bytes=500)
        assert t.space_deficit(300) == 0

    def test_post_init_path_local(self):
        from src.models.migration_target import DriveType, MigrationTarget
        t = MigrationTarget(drive_letter="E:", label="", drive_type=DriveType.REMOVABLE,
                           total_bytes=1000, free_bytes=500)
        assert t.path == "E:\\"

    def test_post_init_path_network(self):
        from src.models.migration_target import DriveType, MigrationTarget
        t = MigrationTarget(drive_letter="\\\\server\\share", label="NAS", drive_type=DriveType.NETWORK,
                           total_bytes=1000, free_bytes=500, is_network=True)
        assert t.path == "\\\\server\\share"

    def test_type_display_removable(self):
        from src.models.migration_target import DriveType, MigrationTarget
        t = MigrationTarget(drive_letter="E:", label="", drive_type=DriveType.REMOVABLE,
                           total_bytes=1000, free_bytes=500)
        display, icon = t.type_display
        assert "可移动" in display or "Removable" in display


class TestMigrationConfig:
    """Test MigrationConfig dataclass."""

    def _make_target(self):
        from src.models.migration_target import DriveType, MigrationTarget
        return MigrationTarget(drive_letter="E:", label="USB", drive_type=DriveType.REMOVABLE,
                              total_bytes=10**9, free_bytes=5*10**8)

    def test_total_size_sums_selected(self):
        from src.models.file_entry import FileEntry
        from src.models.migration_config import MigrationConfig
        files = [
            FileEntry(path="a.docx", size=100, modified_time=0),
            FileEntry(path="b.jpg", size=200, modified_time=0),
        ]
        config = MigrationConfig(selected_files=files)
        assert config.total_size == 300

    def test_file_count(self):
        from src.models.file_entry import FileEntry
        from src.models.migration_config import MigrationConfig
        files = [FileEntry(path=f"file{i}.txt", size=10, modified_time=0) for i in range(5)]
        config = MigrationConfig(selected_files=files)
        assert config.file_count == 5

    def test_output_path_zip(self):
        from src.models.file_entry import FileEntry
        from src.models.migration_config import MigrationConfig
        config = MigrationConfig(
            selected_files=[FileEntry(path="a.txt", size=10, modified_time=0)],
            target=self._make_target(),
            output_format=MigrationFormat.ZIP,
        )
        assert config.output_path.endswith(".zip")

    def test_output_path_7z(self):
        from src.models.file_entry import FileEntry
        from src.models.migration_config import MigrationConfig
        config = MigrationConfig(
            selected_files=[FileEntry(path="a.txt", size=10, modified_time=0)],
            target=self._make_target(),
            output_format=MigrationFormat.SEVEN_ZIP,
        )
        assert config.output_path.endswith(".7z")

    def test_output_path_copy_only(self):
        from src.models.file_entry import FileEntry
        from src.models.migration_config import MigrationConfig
        config = MigrationConfig(
            selected_files=[FileEntry(path="a.txt", size=10, modified_time=0)],
            target=self._make_target(),
            output_format=MigrationFormat.COPY_ONLY,
        )
        assert "migration_backup" in config.output_path
        assert not config.output_path.endswith(".zip")
        assert not config.output_path.endswith(".7z")

    def test_output_path_no_target(self):
        from src.models.migration_config import MigrationConfig
        config = MigrationConfig()
        assert config.output_path == ""

    def test_estimated_output_size_zip(self):
        from src.models.file_entry import FileEntry
        from src.models.migration_config import MigrationConfig
        config = MigrationConfig(
            selected_files=[FileEntry(path="a.txt", size=1000, modified_time=0)],
            output_format=MigrationFormat.ZIP,
        )
        assert config.estimated_output_size == 600  # 60%

    def test_estimated_output_size_7z(self):
        from src.models.file_entry import FileEntry
        from src.models.migration_config import MigrationConfig
        config = MigrationConfig(
            selected_files=[FileEntry(path="a.txt", size=1000, modified_time=0)],
            output_format=MigrationFormat.SEVEN_ZIP,
        )
        assert config.estimated_output_size == 500  # 50%

    def test_estimated_output_size_copy(self):
        from src.models.file_entry import FileEntry
        from src.models.migration_config import MigrationConfig
        config = MigrationConfig(
            selected_files=[FileEntry(path="a.txt", size=1000, modified_time=0)],
            output_format=MigrationFormat.COPY_ONLY,
        )
        assert config.estimated_output_size == 1000  # 100%

    def test_is_ready_with_files_and_space(self):
        from src.models.file_entry import FileEntry
        from src.models.migration_config import MigrationConfig
        config = MigrationConfig(
            selected_files=[FileEntry(path="a.txt", size=10, modified_time=0)],
            target=self._make_target(),
        )
        assert config.is_ready() is True

    def test_is_ready_no_files(self):
        from src.models.migration_config import MigrationConfig
        config = MigrationConfig(target=self._make_target())
        assert config.is_ready() is False

    def test_is_ready_insufficient_space(self):
        from src.models.file_entry import FileEntry
        from src.models.migration_config import MigrationConfig
        from src.models.migration_target import DriveType, MigrationTarget
        small_target = MigrationTarget(drive_letter="E:", label="", drive_type=DriveType.REMOVABLE,
                                       total_bytes=100, free_bytes=10)
        config = MigrationConfig(
            selected_files=[FileEntry(path="a.txt", size=1000, modified_time=0)],
            target=small_target,
        )
        assert config.is_ready() is False

    def test_verify_defaults(self):
        from src.models.migration_config import MigrationConfig
        config = MigrationConfig()
        assert config.verify_after_write is True
        assert config.verify_algorithm == "xxhash"
