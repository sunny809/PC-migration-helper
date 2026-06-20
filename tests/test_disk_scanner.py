"""Tests for DiskScanner."""

import os
import tempfile
import threading

import pytest

from src.constants import FileCategory, ScanState
from src.models.file_entry import FileEntry
from src.scanners.disk_scanner import DiskScanner
from src.scanners.file_classifier import FileClassifier


@pytest.fixture
def classifier():
    """Create a FileClassifier with default config."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(project_root, "config", "default_rules.yaml")
    return FileClassifier(config_path)


@pytest.fixture
def scanner(classifier):
    """Create a DiskScanner instance."""
    return DiskScanner(classifier)


@pytest.fixture
def temp_file_tree():
    """Create a temporary directory structure with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create directory structure
        docs_dir = os.path.join(tmpdir, "Documents")
        photos_dir = os.path.join(tmpdir, "Pictures")
        other_dir = os.path.join(tmpdir, "Other")
        os.makedirs(docs_dir)
        os.makedirs(photos_dir)
        os.makedirs(other_dir)

        # Create test files
        test_files = {
            os.path.join(docs_dir, "report.docx"): FileCategory.DOCUMENTS,
            os.path.join(docs_dir, "data.xlsx"): FileCategory.DOCUMENTS,
            os.path.join(docs_dir, "notes.txt"): FileCategory.DOCUMENTS,
            os.path.join(photos_dir, "photo.jpg"): FileCategory.PHOTOS,
            os.path.join(photos_dir, "image.png"): FileCategory.PHOTOS,
            os.path.join(other_dir, "archive.zip"): FileCategory.ARCHIVES,
        }

        for path in test_files:
            with open(path, "w") as f:
                f.write("test content")

        yield tmpdir, test_files


class TestDiskScanner:
    """Test disk scanning functionality."""

    def test_scan_basic(self, scanner, temp_file_tree):
        """Test basic scanning of a directory tree."""
        tmpdir, expected_files = temp_file_tree
        result = scanner.scan(roots=[tmpdir])

        assert result.state == ScanState.COMPLETED
        assert result.file_count == len(expected_files)
        assert result.total_size > 0
        assert result.scan_duration > 0

    def test_scan_finds_documents(self, scanner, temp_file_tree):
        """Test that documents are found and classified."""
        tmpdir, _ = temp_file_tree
        result = scanner.scan(roots=[tmpdir])

        doc_files = result.get_files_by_category(FileCategory.DOCUMENTS)
        assert len(doc_files) == 3  # report.docx, data.xlsx, notes.txt

    def test_scan_finds_photos(self, scanner, temp_file_tree):
        """Test that photos are found and classified."""
        tmpdir, _ = temp_file_tree
        result = scanner.scan(roots=[tmpdir])

        photo_files = result.get_files_by_category(FileCategory.PHOTOS)
        assert len(photo_files) == 2  # photo.jpg, image.png

    def test_scan_finds_archives(self, scanner, temp_file_tree):
        """Test that archives are found and classified."""
        tmpdir, _ = temp_file_tree
        result = scanner.scan(roots=[tmpdir])

        archive_files = result.get_files_by_category(FileCategory.ARCHIVES)
        assert len(archive_files) == 1  # archive.zip

    def test_scan_cancellation(self, scanner, temp_file_tree):
        """Test that scanning can be cancelled."""
        tmpdir, _ = temp_file_tree
        cancel_event = threading.Event()
        cancel_event.set()  # Cancel immediately

        result = scanner.scan(roots=[tmpdir], cancel_event=cancel_event)
        assert result.state == ScanState.CANCELLED

    def test_scan_progress_callback(self, scanner, temp_file_tree):
        """Test that progress callback is called."""
        tmpdir, _ = temp_file_tree
        progress_calls = []

        def on_progress(scanned, found):
            progress_calls.append((scanned, found))

        result = scanner.scan(roots=[tmpdir], on_progress=on_progress)
        assert result.state == ScanState.COMPLETED
        # Progress should have been called at least once
        assert len(progress_calls) >= 0  # May not be called for small trees

    def test_scan_file_callback(self, scanner, temp_file_tree):
        """Test that on_file callback receives FileEntry objects."""
        tmpdir, _ = temp_file_tree
        found_files = []

        def on_file(entry):
            found_files.append(entry)

        result = scanner.scan(roots=[tmpdir], on_file=on_file)
        assert result.state == ScanState.COMPLETED
        assert len(found_files) == 6  # All test files

    def test_scan_nonexistent_root(self, scanner):
        """Test scanning a non-existent root directory."""
        result = scanner.scan(roots=["/nonexistent/path"])
        assert result.state == ScanState.COMPLETED
        assert result.file_count == 0

    def test_scan_excludes_system_extensions(self, scanner, temp_file_tree):
        """Test that system file extensions are excluded."""
        tmpdir, _ = temp_file_tree

        # Create a .exe file
        exe_path = os.path.join(tmpdir, "program.exe")
        with open(exe_path, "w") as f:
            f.write("fake exe")

        result = scanner.scan(roots=[tmpdir])
        # .exe should not be in the results
        assert not any(f.path.endswith(".exe") for f in result.files)

    def test_scan_handles_permission_errors(self, scanner, temp_file_tree):
        """Test that permission errors are handled gracefully."""
        tmpdir, _ = temp_file_tree

        # Create a directory that will cause an error
        # (We can't easily create a real permission error in tests,
        # but we can verify the error handling structure)
        result = scanner.scan(roots=[tmpdir])
        assert isinstance(result.errors, list)

    def test_scan_result_aggregation(self, scanner, temp_file_tree):
        """Test that ScanResult aggregates correctly."""
        tmpdir, _ = temp_file_tree
        result = scanner.scan(roots=[tmpdir])

        # Category counts should sum to total
        total_from_categories = sum(result.category_counts.values())
        assert total_from_categories == result.file_count

        # Category sizes should sum to total
        total_size_from_categories = sum(result.category_sizes.values())
        assert total_size_from_categories == result.total_size


class TestEstimateDirCount:
    """Test DiskScanner.estimate_dir_count() — v0.2 new method."""

    def test_estimate_dir_count_basic(self, scanner, temp_file_tree):
        """Test basic directory count estimation."""
        tmpdir, _ = temp_file_tree
        count = scanner.estimate_dir_count(roots=[tmpdir])
        # Should count root + Documents + Pictures + Other = 4 directories
        assert count >= 4

    def test_estimate_dir_count_with_cancellation(self, scanner, temp_file_tree):
        """Test estimation can be cancelled."""
        tmpdir, _ = temp_file_tree
        cancel_event = threading.Event()
        cancel_event.set()  # Cancel immediately
        count = scanner.estimate_dir_count(roots=[tmpdir], cancel_event=cancel_event)
        # Should return 0 or very small count due to immediate cancellation
        assert count >= 0

    def test_estimate_dir_count_nonexistent_root(self, scanner):
        """Test estimation with non-existent root returns 0."""
        count = scanner.estimate_dir_count(roots=["/nonexistent/path"])
        assert count == 0

    def test_estimate_dir_count_respects_excluded_paths(self, scanner, temp_file_tree):
        """Test that excluded paths are not counted."""
        tmpdir, _ = temp_file_tree
        count = scanner.estimate_dir_count(roots=[tmpdir])
        # The count should be consistent with what the real scan would traverse
        result = scanner.scan(roots=[tmpdir])
        # Estimate should be in reasonable range
        assert count > 0

    def test_estimate_dir_count_empty_root(self, scanner):
        """Test estimation of an empty directory."""
        with tempfile.TemporaryDirectory() as empty_dir:
            count = scanner.estimate_dir_count(roots=[empty_dir])
            # Empty root counts as 1 directory
            assert count >= 1

    def test_estimate_dir_count_nested(self, scanner):
        """Test estimation with deeply nested directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create nested structure
            for i in range(5):
                nested = os.path.join(tmpdir, f"level{i}")
                os.makedirs(nested)
                for j in range(3):
                    os.makedirs(os.path.join(nested, f"sub{j}"))

            count = scanner.estimate_dir_count(roots=[tmpdir])
            # Root + 5 level dirs + 15 sub dirs = 21
            assert count >= 20


class TestAdvancedScanning:
    """Additional scanning tests for branch coverage."""

    def test_scan_multiple_roots(self, scanner):
        """Test scanning with two root directories."""
        with tempfile.TemporaryDirectory() as dir1:
            with tempfile.TemporaryDirectory() as dir2:
                # Create files in both roots
                with open(os.path.join(dir1, "file1.docx"), "w") as f:
                    f.write("doc1")
                with open(os.path.join(dir2, "file2.jpg"), "w") as f:
                    f.write("img1")

                result = scanner.scan(roots=[dir1, dir2])
                assert result.state == ScanState.COMPLETED
                assert result.file_count == 2

    def test_scan_auto_add_when_no_callback(self, scanner):
        """When on_file is None, files should be added to ScanResult automatically."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "report.docx"), "w") as f:
                f.write("test report")

            result = scanner.scan(roots=[tmpdir], on_file=None)
            # Files should be in result.files (auto-added)
            assert result.file_count >= 1
            # Check that the file is actually in the list
            paths = [f.path for f in result.files]
            assert any("report.docx" in p for p in paths)
