"""Tests for ReportGenerator — HTML and JSON report generation."""

import os
import tempfile

import pytest

from src.constants import FileCategory
from src.models.file_entry import FileEntry
from src.models.migration_result import MigrationResult
from src.models.scan_result import ScanResult
from src.utils.report_generator import ReportGenerator


class TestReportGenerator:
    """Test ReportGenerator output."""

    def test_generate_preview_report(self):
        """Preview report creates both JSON and HTML from a ScanResult."""
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
        generator = ReportGenerator()

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path, html_path = generator.generate(result, tmpdir)

            assert os.path.exists(json_path)
            assert os.path.exists(html_path)
            assert json_path.endswith(".json")
            assert html_path.endswith(".html")

            # Check HTML content
            with open(html_path, "r", encoding="utf-8") as f:
                html = f.read()
            assert "Scan Preview" in html or "扫描预览" in html
            assert "a.docx" in html
            assert "b.jpg" in html
            assert "statistics" in html.lower() or "分类统计" in html

    def test_generate_final_report(self):
        """Final report includes verification results."""
        result = MigrationResult(
            format="7z",
            verify_algorithm="xxhash",
            total_files=2,
            total_size=300,
            categories={
                "documents": {"count": 1, "size": 100},
                "photos": {"count": 1, "size": 200},
            },
            files=[
                type("FakeRecord", (), {
                    "path": "docs/a.docx", "size": 100, "modified": 0.0,
                    "hash": "xxh64:aaa", "category": "documents", "status": "ok",
                    "to_dict": lambda self: {"path": self.path, "size": self.size, "modified": self.modified, "hash": self.hash, "category": self.category, "status": self.status},
                })(),
                type("FakeRecord", (), {
                    "path": "pics/b.jpg", "size": 200, "modified": 0.0,
                    "hash": "xxh64:bbb", "category": "photos", "status": "ok",
                    "to_dict": lambda self: {"path": self.path, "size": self.size, "modified": self.modified, "hash": self.hash, "category": self.category, "status": self.status},
                })(),
            ],
            verify_passed=2,
            verify_failed=0,
        )

        generator = ReportGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path, html_path = generator.generate(result, tmpdir)

            with open(html_path, "r", encoding="utf-8") as f:
                html = f.read()
            assert "Migration Report" in html or "迁移报告" in html
            assert "xxhash" in html
            assert "2 passed" in html or "✓" in html

    def test_generate_empty_result(self):
        """Empty scan result still produces valid reports."""
        scan = ScanResult()
        result = MigrationResult.from_scan_result(scan)
        generator = ReportGenerator()

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path, html_path = generator.generate(result, tmpdir)
            assert os.path.exists(json_path)
            assert os.path.exists(html_path)

            with open(html_path, "r", encoding="utf-8") as f:
                html = f.read()
            assert "No data" in html or "无数据" in html or "No files" in html or "无文件" in html

    def test_generate_with_errors(self):
        """Errors are included in the report."""
        scan = ScanResult()
        scan.add_file(FileEntry(path="C:\\f.txt", size=10, modified_time=0))
        scan.errors = ["C:\\Windows\\System32: Permission denied"]
        result = MigrationResult.from_scan_result(scan)
        generator = ReportGenerator()

        with tempfile.TemporaryDirectory() as tmpdir:
            _, html_path = generator.generate(result, tmpdir)
            with open(html_path, "r", encoding="utf-8") as f:
                html = f.read()
            assert "Permission denied" in html

    def test_html_is_self_contained(self):
        """Report HTML has no external dependencies (no CDN/hosted resources)."""
        scan = ScanResult()
        scan.add_file(FileEntry(path="C:\\f.txt", size=10, modified_time=0))
        result = MigrationResult.from_scan_result(scan)
        generator = ReportGenerator()

        with tempfile.TemporaryDirectory() as tmpdir:
            _, html_path = generator.generate(result, tmpdir)
            with open(html_path, "r", encoding="utf-8") as f:
                html = f.read()
            # No external URLs
            assert "http://" not in html
            assert "https://" not in html
            # No external fonts or scripts
            assert "@import" not in html
            assert "<script" not in html
            # All styles inline
            assert "<style>" in html
