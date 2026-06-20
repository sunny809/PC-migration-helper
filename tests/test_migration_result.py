"""Tests for MigrationResult and FileRecord data models."""

import json
import os
import tempfile
import platform
from datetime import datetime

import pytest

from src.constants import APP_VERSION, FileCategory
from src.models.file_entry import FileEntry
from src.models.migration_result import FileRecord, MigrationResult
from src.models.scan_result import ScanResult


class TestFileRecord:
    """Test FileRecord creation and serialization."""

    def test_from_file_entry_normalizes_windows_path(self):
        """Windows path C:\\Users\\file.txt → Users/file.txt"""
        entry = FileEntry(
            path="C:\\Users\\John\\Documents\\report.docx",
            size=1024, modified_time=1718765400,
        )
        record = FileRecord.from_file_entry(entry)
        assert record.path == "Users/John/Documents/report.docx"
        assert record.size == 1024
        assert record.category == "other"

    def test_from_file_entry_normalizes_unix_path(self):
        """Unix path /home/user/file.txt → home/user/file.txt"""
        entry = FileEntry(
            path="/home/user/docs/report.docx",
            size=512, modified_time=1718765400,
        )
        record = FileRecord.from_file_entry(entry)
        assert record.path == "home/user/docs/report.docx"

    def test_from_file_entry_with_category_and_hash(self):
        entry = FileEntry(
            path="D:\\Photos\\vacation.jpg",
            size=2048, modified_time=0,
            category=FileCategory.PHOTOS,
        )
        record = FileRecord.from_file_entry(entry, hash_value="xxh64:abc123", status="ok")
        assert record.category == "photos"
        assert record.hash == "xxh64:abc123"
        assert record.status == "ok"

    def test_to_dict_roundtrip(self):
        record = FileRecord(
            path="docs/file.txt", size=100, modified=0.0,
            hash="xxh64:deadbeef", category="documents", status="ok",
        )
        d = record.to_dict()
        assert d["path"] == "docs/file.txt"
        assert d["hash"] == "xxh64:deadbeef"
        restored = FileRecord(**d)
        assert restored.path == record.path
        assert restored.hash == record.hash


class TestMigrationResult:
    """Test MigrationResult creation and serialization."""

    def test_default_values(self):
        result = MigrationResult()
        assert result.format == "preview"
        assert result.total_files == 0
        assert result.app_version == APP_VERSION
        assert result.source_pc == platform.node()
        assert result.created != ""

    def test_from_scan_result_empty(self):
        scan = ScanResult()
        result = MigrationResult.from_scan_result(scan)
        assert result.is_preview
        assert result.total_files == 0
        assert result.files == []

    def test_from_scan_result_with_files(self):
        scan = ScanResult()
        scan.add_file(FileEntry(
            path="C:\\docs\\a.docx", size=100, modified_time=0,
            category=FileCategory.DOCUMENTS,
        ))
        scan.add_file(FileEntry(
            path="C:\\pics\\b.jpg", size=200, modified_time=0,
            category=FileCategory.PHOTOS,
        ))
        result = MigrationResult.from_scan_result(scan)
        assert result.total_files == 2
        assert result.total_size == 300
        assert "documents" in result.categories
        assert "photos" in result.categories
        assert len(result.files) == 2

    def test_to_json_roundtrip(self):
        scan = ScanResult()
        scan.add_file(FileEntry(path="C:\\f.txt", size=50, modified_time=0))
        result = MigrationResult.from_scan_result(scan)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "manifest.json")
            result.to_json(path)

            assert os.path.exists(path)
            with open(path, "r") as f:
                data = json.load(f)
            assert data["total_files"] == 1
            assert data["format"] == "preview"

            restored = MigrationResult.from_json(path)
            assert restored.total_files == 1
            assert len(restored.files) == 1
            assert restored.files[0].path == "f.txt"

    def test_verify_summary(self):
        r1 = MigrationResult(verify_passed=100, verify_failed=0)
        assert "passed" in r1.verify_summary
        assert "FAILED" not in r1.verify_summary

        r2 = MigrationResult(verify_passed=95, verify_failed=5)
        assert "FAILED" in r2.verify_summary

    def test_is_preview_vs_final(self):
        preview = MigrationResult(format="preview")
        assert preview.is_preview
        assert not preview.is_final

        final = MigrationResult(format="7z")
        assert not final.is_preview
        assert final.is_final

    def test_from_migration_dict_with_verify_failures(self):
        result_dict = {
            "success": True,
            "files_processed": 3,
            "bytes_processed": 600,
            "verify_failures": [
                {"path": "C:\\bad.txt", "expected": "hash1", "actual": "hash2"},
            ],
            "errors": [],
            "target_dir": "E:\\backup",
            "output_path": "E:\\backup\\backup.7z",
        }
        # Create with some FileEntry objects
        files = [
            FileEntry(path="C:\\a.txt", size=100, modified_time=0),
            FileEntry(path="C:\\b.txt", size=200, modified_time=0),
            FileEntry(path="C:\\bad.txt", size=300, modified_time=0),
        ]
        result_dict["files"] = files
        # Add verify_results map
        result_dict["verify_results"] = {
            "C:\\a.txt": "xxh64:aaa",
            "C:\\b.txt": "xxh64:bbb",
            "C:\\bad.txt": "xxh64:ccc",
        }

        result = MigrationResult.from_migration_dict(
            result_dict, config_format="7z", verify_algorithm="xxhash",
        )
        assert result.format == "7z"
        assert result.total_files == 3
        assert result.verify_failed == 1
        assert result.verify_passed == 2
        assert result.destination == "E:\\backup"
        assert result.output_path == "E:\\backup\\backup.7z"
