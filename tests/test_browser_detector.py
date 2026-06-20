"""Tests for BrowserDetector — browser bookmark detection."""

import os
import tempfile
from unittest.mock import patch

import pytest

from src.constants import FileCategory
from src.models.file_entry import FileEntry


class TestBrowserDetectorDetectAll:
    """Test BrowserDetector.detect_all() under various conditions."""

    def test_detect_all_no_browsers(self):
        """When no browser data exists, detect_all returns empty list."""
        from src.utils.browser_detector import BrowserDetector

        with patch.dict(os.environ, {"LOCALAPPDATA": "/nonexistent", "APPDATA": "/nonexistent"}):
            detector = BrowserDetector()
            browsers = detector.detect_all()
            assert browsers == []

    def test_detect_chrome_bookmark(self):
        """Chrome bookmark is detected when file exists."""
        from src.utils.browser_detector import BrowserDetector

        with tempfile.TemporaryDirectory() as tmpdir:
            chrome_dir = os.path.join(
                tmpdir, "Google", "Chrome", "User Data", "Default"
            )
            os.makedirs(chrome_dir)
            bookmark_path = os.path.join(chrome_dir, "Bookmarks")
            with open(bookmark_path, "w") as f:
                f.write('{"roots": {"bookmark_bar": {"children": []}}}')

            with patch.dict(os.environ, {"LOCALAPPDATA": tmpdir}):
                detector = BrowserDetector()
                browsers = detector.detect_all()
                names = [b.name for b in browsers]
                assert "Google Chrome" in names
                chrome = [b for b in browsers if b.name == "Google Chrome"][0]
                assert chrome.bookmark_path == bookmark_path

    def test_detect_multiple_chromium_browsers(self):
        """Multiple Chromium browsers are detected independently."""
        from src.utils.browser_detector import BrowserDetector

        with tempfile.TemporaryDirectory() as tmpdir:
            chrome_dir = os.path.join(tmpdir, "Google", "Chrome", "User Data", "Default")
            os.makedirs(chrome_dir)
            with open(os.path.join(chrome_dir, "Bookmarks"), "w") as f:
                f.write("{}")

            edge_dir = os.path.join(tmpdir, "Microsoft", "Edge", "User Data", "Default")
            os.makedirs(edge_dir)
            with open(os.path.join(edge_dir, "Bookmarks"), "w") as f:
                f.write("{}")

            with patch.dict(os.environ, {"LOCALAPPDATA": tmpdir}):
                detector = BrowserDetector()
                browsers = detector.detect_all()
                names = [b.name for b in browsers]
                assert "Google Chrome" in names
                assert "Microsoft Edge" in names

    def test_detect_firefox_bookmarks(self):
        """Firefox places.sqlite is detected in profiles."""
        from src.utils.browser_detector import BrowserDetector

        with tempfile.TemporaryDirectory() as tmpdir:
            profile_dir = os.path.join(
                tmpdir, "Mozilla", "Firefox", "Profiles", "abc123.default"
            )
            os.makedirs(profile_dir)
            places_path = os.path.join(profile_dir, "places.sqlite")
            with open(places_path, "w") as f:
                f.write("SQLite format 3\0")

            with patch.dict(os.environ, {"APPDATA": tmpdir}):
                detector = BrowserDetector()
                browsers = detector.detect_all()
                names = [b.name for b in browsers]
                assert "Firefox" in names
                ff = [b for b in browsers if b.name == "Firefox"][0]
                assert ff.bookmark_path == places_path

    def test_detect_no_localappdata_env(self):
        """When LOCALAPPDATA is not set, no Chromium browsers are found."""
        from src.utils.browser_detector import BrowserDetector

        with patch.dict(os.environ, {}, clear=True):
            detector = BrowserDetector()
            browsers = detector.detect_all()
            chrome_browsers = [b for b in browsers if b.name != "Firefox"]
            assert len(chrome_browsers) == 0


class TestBrowserDetectorGetBookmarkEntries:
    """Test BrowserDetector.get_bookmark_entries()."""

    def test_get_bookmark_entries_returns_file_entries(self):
        """Bookmark entries are FileEntry objects with BROWSER_DATA category."""
        from src.utils.browser_detector import BrowserDetector

        with tempfile.TemporaryDirectory() as tmpdir:
            chrome_dir = os.path.join(tmpdir, "Google", "Chrome", "User Data", "Default")
            os.makedirs(chrome_dir)
            bookmark_path = os.path.join(chrome_dir, "Bookmarks")
            with open(bookmark_path, "w") as f:
                f.write("test content")

            with patch.dict(os.environ, {"LOCALAPPDATA": tmpdir}):
                detector = BrowserDetector()
                entries = detector.get_bookmark_entries()

                assert len(entries) == 1
                entry = entries[0]
                assert isinstance(entry, FileEntry)
                assert entry.category == FileCategory.BROWSER_DATA
                assert entry.is_selected is True
                assert entry.path == bookmark_path
                assert entry.size > 0

    def test_get_bookmark_entries_empty_when_none_found(self):
        """No browser data means empty list."""
        from src.utils.browser_detector import BrowserDetector

        with patch.dict(os.environ, {"LOCALAPPDATA": "/nonexistent", "APPDATA": "/nonexistent"}):
            detector = BrowserDetector()
            entries = detector.get_bookmark_entries()
            assert entries == []

    def test_get_bookmark_entries_file_size_and_mtime(self):
        """Each entry has correct size and modification time."""
        from src.utils.browser_detector import BrowserDetector

        with tempfile.TemporaryDirectory() as tmpdir:
            edge_dir = os.path.join(tmpdir, "Microsoft", "Edge", "User Data", "Default")
            os.makedirs(edge_dir)
            bookmark_path = os.path.join(edge_dir, "Bookmarks")
            content = "edge bookmarks data"
            with open(bookmark_path, "w") as f:
                f.write(content)

            with patch.dict(os.environ, {"LOCALAPPDATA": tmpdir}):
                detector = BrowserDetector()
                entries = detector.get_bookmark_entries()

                assert len(entries) == 1
                assert entries[0].size == len(content.encode())
                assert entries[0].modified_time > 0


class TestBrowserDetectorIntegration:
    """Test integration of BrowserDetector with DiskScanner."""

    def test_disk_scanner_with_browser_data(self):
        """DiskScanner.scan() with include_browser_data=True adds bookmark entries."""
        from src.scanners.disk_scanner import DiskScanner
        from src.scanners.file_classifier import FileClassifier

        with tempfile.TemporaryDirectory() as scan_root, \
             tempfile.TemporaryDirectory() as fake_localappdata:

            doc_path = os.path.join(scan_root, "report.docx")
            with open(doc_path, "w") as f:
                f.write("test")

            # Fake Chrome bookmark
            chrome_dir = os.path.join(
                fake_localappdata, "Google", "Chrome", "User Data", "Default"
            )
            os.makedirs(chrome_dir)
            with open(os.path.join(chrome_dir, "Bookmarks"), "w") as f:
                f.write("{}")

            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(project_root, "config", "default_rules.yaml")
            classifier = FileClassifier(config_path)
            scanner = DiskScanner(classifier)

            with patch.dict(os.environ, {"LOCALAPPDATA": fake_localappdata}):
                result = scanner.scan(
                    roots=[scan_root],
                    include_browser_data=True,
                )

            assert result.file_count >= 1
            browser_files = result.get_files_by_category(FileCategory.BROWSER_DATA)
            assert len(browser_files) == 1
            assert "Bookmarks" in browser_files[0].name

    def test_disk_scanner_without_browser_data(self):
        """include_browser_data=False skips browser detection entirely."""
        from src.scanners.disk_scanner import DiskScanner
        from src.scanners.file_classifier import FileClassifier

        with tempfile.TemporaryDirectory() as scan_root, \
             tempfile.TemporaryDirectory() as fake_localappdata:

            doc_path = os.path.join(scan_root, "doc.txt")
            with open(doc_path, "w") as f:
                f.write("hello")

            chrome_dir = os.path.join(
                fake_localappdata, "Google", "Chrome", "User Data", "Default"
            )
            os.makedirs(chrome_dir)
            with open(os.path.join(chrome_dir, "Bookmarks"), "w") as f:
                f.write("{}")

            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(project_root, "config", "default_rules.yaml")
            classifier = FileClassifier(config_path)
            scanner = DiskScanner(classifier)

            with patch.dict(os.environ, {"LOCALAPPDATA": fake_localappdata}):
                result = scanner.scan(
                    roots=[scan_root],
                    include_browser_data=False,
                )

            browser_files = result.get_files_by_category(FileCategory.BROWSER_DATA)
            assert len(browser_files) == 0

    def test_known_browser_list(self):
        """BrowserDetector has the expected set of known browsers."""
        from src.utils.browser_detector import BrowserDetector

        detector = BrowserDetector()
        assert len(detector._CHROMIUM_BROWSERS) == 5
        assert "Google Chrome" in detector._CHROMIUM_BROWSERS
        assert "Microsoft Edge" in detector._CHROMIUM_BROWSERS
        assert "Brave" in detector._CHROMIUM_BROWSERS
        assert "Vivaldi" in detector._CHROMIUM_BROWSERS
        assert "Opera" in detector._CHROMIUM_BROWSERS
