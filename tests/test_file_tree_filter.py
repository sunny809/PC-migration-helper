"""Tests for FileTreeFilterProxy — file tree filtering logic."""

import os
import pytest

from src.constants import FileCategory
from src.models.file_entry import FileEntry
from src.ui.widgets.file_tree_filter import FileTreeFilterProxy
from src.ui.widgets.file_tree_model import CategoryNode, DirectoryNode, FileNode


class TestFileMatches:
    """Test the _file_matches method of FileTreeFilterProxy."""

    def _make_proxy(self):
        """Create a filter proxy (without Qt if unavailable)."""
        try:
            from PySide6.QtCore import QObject
            return FileTreeFilterProxy()
        except ImportError:
            proxy = FileTreeFilterProxy()
            return proxy

    def _make_file_node(self, name="report.docx", category=FileCategory.DOCUMENTS,
                        path="C:\\Users\\test\\Documents\\report.docx"):
        entry = FileEntry(path=path, size=1000, modified_time=0, category=category)
        return FileNode(entry)

    def test_no_filter_matches_everything(self):
        proxy = self._make_proxy()
        node = self._make_file_node()
        assert proxy._file_matches(node) is True

    def test_text_filter_single_term_match(self):
        proxy = self._make_proxy()
        proxy._filter_text = "report"
        node = self._make_file_node(name="report.docx")
        assert proxy._file_matches(node) is True

    def test_text_filter_single_term_no_match(self):
        proxy = self._make_proxy()
        proxy._filter_text = "photo"
        node = self._make_file_node(name="report.docx")
        assert proxy._file_matches(node) is False

    def test_text_filter_case_insensitive(self):
        proxy = self._make_proxy()
        proxy._filter_text = "report"
        node = self._make_file_node(name="REPORT.docx")
        assert proxy._file_matches(node) is True

    def test_text_filter_multiple_terms_all_must_match(self):
        proxy = self._make_proxy()
        proxy._filter_text = "report docx"
        node = self._make_file_node(name="report.docx")
        assert proxy._file_matches(node) is True

    def test_text_filter_multiple_terms_partial_no_match(self):
        proxy = self._make_proxy()
        proxy._filter_text = "report photo"
        node = self._make_file_node(name="report.docx")
        assert proxy._file_matches(node) is False

    def test_text_filter_matches_extension(self):
        proxy = self._make_proxy()
        proxy._filter_text = "docx"
        node = self._make_file_node(name="report.docx")
        assert proxy._file_matches(node) is True

    def test_text_filter_matches_path(self):
        proxy = self._make_proxy()
        proxy._filter_text = "documents"
        node = self._make_file_node(path="C:\\Users\\test\\Documents\\report.docx")
        assert proxy._file_matches(node) is True

    def test_category_filter_match(self):
        proxy = self._make_proxy()
        proxy._filter_category = FileCategory.DOCUMENTS
        node = self._make_file_node(category=FileCategory.DOCUMENTS)
        assert proxy._file_matches(node) is True

    def test_category_filter_no_match(self):
        proxy = self._make_proxy()
        proxy._filter_category = FileCategory.PHOTOS
        node = self._make_file_node(category=FileCategory.DOCUMENTS)
        assert proxy._file_matches(node) is False

    def test_both_filters_text_and_category(self):
        proxy = self._make_proxy()
        proxy._filter_text = "report"
        proxy._filter_category = FileCategory.DOCUMENTS
        node = self._make_file_node(name="report.docx", category=FileCategory.DOCUMENTS)
        assert proxy._file_matches(node) is True

    def test_both_filters_text_matches_category_does_not(self):
        proxy = self._make_proxy()
        proxy._filter_text = "photo"
        proxy._filter_category = FileCategory.DOCUMENTS
        node = self._make_file_node(name="photo.jpg", category=FileCategory.PHOTOS)
        assert proxy._file_matches(node) is False


class TestNodeMatches:
    """Test the _node_matches method for category and directory nodes."""

    def _make_proxy(self):
        try:
            from PySide6.QtCore import QObject
            return FileTreeFilterProxy()
        except ImportError:
            return FileTreeFilterProxy()

    def test_file_node_passes_through(self):
        proxy = self._make_proxy()
        entry = FileEntry(path="test.txt", size=100, modified_time=0)
        node = FileNode(entry)
        assert proxy._node_matches(node) is True

    def test_category_node_with_matching_child(self):
        proxy = self._make_proxy()
        proxy._filter_text = "report"

        cat_node = CategoryNode(FileCategory.DOCUMENTS)
        entry = FileEntry(path="report.docx", size=100, modified_time=0, category=FileCategory.DOCUMENTS)
        file_node = FileNode(entry, cat_node)
        cat_node.add_child(file_node)

        assert proxy._node_matches(cat_node) is True

    def test_category_node_no_matching_children(self):
        proxy = self._make_proxy()
        proxy._filter_text = "photo"

        cat_node = CategoryNode(FileCategory.DOCUMENTS)
        entry = FileEntry(path="report.docx", size=100, modified_time=0, category=FileCategory.DOCUMENTS)
        file_node = FileNode(entry, cat_node)
        cat_node.add_child(file_node)

        assert proxy._node_matches(cat_node) is False

    def test_category_node_excluded_by_category_filter(self):
        proxy = self._make_proxy()
        proxy._filter_category = FileCategory.PHOTOS

        cat_node = CategoryNode(FileCategory.DOCUMENTS)
        # Even with children, category filter excludes this category
        assert proxy._node_matches(cat_node) is False

    def test_directory_node_with_matching_descendant(self):
        proxy = self._make_proxy()
        proxy._filter_text = "report"

        dir_node = DirectoryNode("C:\\Users\\test\\Documents")
        entry = FileEntry(path="report.docx", size=100, modified_time=0)
        file_node = FileNode(entry, dir_node)
        dir_node.add_child(file_node)

        assert proxy._node_matches(dir_node) is True

    def test_directory_node_no_matching_descendants(self):
        proxy = self._make_proxy()
        proxy._filter_text = "photo"

        dir_node = DirectoryNode("C:\\Users\\test\\Documents")
        entry = FileEntry(path="report.docx", size=100, modified_time=0)
        file_node = FileNode(entry, dir_node)
        dir_node.add_child(file_node)

        assert proxy._node_matches(dir_node) is False
