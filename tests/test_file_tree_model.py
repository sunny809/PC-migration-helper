"""Tests for FileTreeModel — tree model for file review."""

import pytest

from src.constants import FileCategory
from src.models.file_entry import FileEntry
from src.models.scan_result import ScanResult
from src.ui.widgets.file_tree_model import FileTreeModel


@pytest.fixture
def scan_result():
    """Create a ScanResult with files in multiple categories."""
    result = ScanResult()
    result.add_file(FileEntry(
        path="C:\\Users\\test\\Documents\\report.docx", size=1000,
        modified_time=0, category=FileCategory.DOCUMENTS,
    ))
    result.add_file(FileEntry(
        path="C:\\Users\\test\\Documents\\data.xlsx", size=2000,
        modified_time=0, category=FileCategory.DOCUMENTS,
    ))
    result.add_file(FileEntry(
        path="C:\\Users\\test\\Pictures\\photo.jpg", size=3000,
        modified_time=0, category=FileCategory.PHOTOS,
    ))
    result.add_file(FileEntry(
        path="D:\\Music\\song.mp3", size=4000,
        modified_time=0, category=FileCategory.MUSIC,
    ))
    return result


@pytest.fixture
def tree_model(scan_result):
    """Create a FileTreeModel loaded with the scan result."""
    model = FileTreeModel()
    model.load_scan_result(scan_result)
    return model


class TestFileTreeModel:
    """Test FileTreeModel core functionality."""

    def test_load_scan_result_creates_hierarchy(self, tree_model):
        """Loading a scan result should create category nodes."""
        # Root should have category nodes as children
        assert tree_model._root.child_count() > 0

    def test_load_scan_result_removes_empty_categories(self, tree_model):
        """Categories with no files should not appear."""
        from src.ui.widgets.file_tree_model import CategoryNode
        for child in tree_model._root.children:
            assert isinstance(child, CategoryNode)
            assert child.child_count() > 0

    def test_get_total_count(self, tree_model):
        """Total count should match scan result."""
        assert tree_model.get_total_count() == 4

    def test_get_total_size(self, tree_model):
        """Total size should match scan result."""
        assert tree_model.get_total_size() == 10000

    def test_get_selected_files_default_all(self, tree_model):
        """By default, all files should be selected."""
        selected = tree_model.get_selected_files()
        assert len(selected) == 4

    def test_get_selected_size_default(self, tree_model):
        """Default selected size should equal total size."""
        assert tree_model.get_selected_size() == 10000

    def test_select_all_true(self, tree_model):
        """Select all should select every file."""
        tree_model.select_all(True)
        assert tree_model.get_selected_count() == 4
        assert tree_model.get_selected_size() == 10000

    def test_select_all_false(self, tree_model):
        """Deselect all should deselect every file."""
        tree_model.select_all(False)
        assert tree_model.get_selected_count() == 0
        assert tree_model.get_selected_size() == 0

    def test_get_selected_count(self, tree_model):
        """Selected count should reflect current selection."""
        assert tree_model.get_selected_count() == 4
        tree_model.select_all(False)
        assert tree_model.get_selected_count() == 0

    def test_get_category_stats(self, tree_model):
        """Category stats should report correct counts and sizes."""
        stats = tree_model.get_category_stats()

        assert FileCategory.DOCUMENTS in stats
        assert stats[FileCategory.DOCUMENTS]["total"] == 2
        assert stats[FileCategory.DOCUMENTS]["total_size"] == 3000

        assert FileCategory.PHOTOS in stats
        assert stats[FileCategory.PHOTOS]["total"] == 1
        assert stats[FileCategory.PHOTOS]["total_size"] == 3000

        assert FileCategory.MUSIC in stats
        assert stats[FileCategory.MUSIC]["total"] == 1
        assert stats[FileCategory.MUSIC]["total_size"] == 4000

    def test_get_category_stats_selected(self, tree_model):
        """Category stats should track selected counts."""
        stats = tree_model.get_category_stats()
        assert stats[FileCategory.DOCUMENTS]["selected"] == 2

    def test_empty_scan_result(self):
        """Empty scan result should produce empty model."""
        model = FileTreeModel()
        model.load_scan_result(ScanResult())
        assert model.get_total_count() == 0
        assert model.get_total_size() == 0

    def test_column_count(self, tree_model):
        """Model should have 4 columns."""
        assert tree_model.columnCount() == 4
