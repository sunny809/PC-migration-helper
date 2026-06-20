"""FileTreeFilterProxy — QSortFilterProxyModel for the file review tree."""

from __future__ import annotations

import os
from typing import Optional

from src.ui.widgets.file_tree_model import CategoryNode, DirectoryNode, FileNode, TreeNode

try:
    from PySide6.QtCore import QSortFilterProxyModel, Qt
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False
    class QSortFilterProxyModel:  # type: ignore[no-redef]
        pass


class FileTreeFilterProxy(QSortFilterProxyModel if HAS_PYSIDE6 else object):
    """Filter proxy model for the file tree view.

    Supports filtering by:
    - File name (substring match, case-insensitive)
    - File extension
    - Category
    - Size range
    - Date range

    When a category or directory has at least one child that matches
    the filter, the category/directory is shown (even if the parent
    node itself doesn't match).
    """

    def __init__(self, parent=None):
        # Always initialize filter state (even without Qt)
        self._filter_text = ""
        self._filter_category = None  # Optional[FileCategory]

        if HAS_PYSIDE6:
            super().__init__(parent)

    def set_filter_text(self, text: str) -> None:
        """Set the text filter (file name substring match)."""
        self._filter_text = text.strip().lower()
        if HAS_PYSIDE6:
            self.invalidateFilter()

    def set_filter_category(self, category=None) -> None:
        """Set the category filter. None means no category filter."""
        self._filter_category = category
        if HAS_PYSIDE6:
            self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        """Determine whether a row should be shown.

        For category and directory nodes, the node is shown if any
        of its descendants match the filter (recursive check).
        """
        if not HAS_PYSIDE6:
            return True

        source_index = self.sourceModel().index(source_row, 0, source_parent)
        if not source_index.isValid():
            return True

        node = source_index.internalPointer()
        if node is None:
            return True

        return self._node_matches(node)

    def _node_matches(self, node) -> bool:
        """Check if a node or any of its descendants match the filter."""
        # File node: check directly
        if isinstance(node, FileNode):
            return self._file_matches(node)

        # Category/Directory node: show if any child matches
        if isinstance(node, (CategoryNode, DirectoryNode)):
            # Check category filter for category nodes
            if isinstance(node, CategoryNode) and self._filter_category is not None:
                if node.category != self._filter_category:
                    return False

            # Check if any descendant matches
            for child in node.children:
                if self._node_matches(child):
                    return True
            return False

        # Root or unknown node: show
        return True

    def _file_matches(self, node: FileNode) -> bool:
        """Check if a file node matches the current filters."""
        entry = node.file_entry

        # Category filter
        if self._filter_category is not None and entry.category != self._filter_category:
            return False

        # Text filter (match against name, path, and extension)
        if self._filter_text:
            name_lower = entry.name.lower()
            path_lower = entry.path.lower()
            ext_lower = entry.extension.lower()

            # Support space-separated terms (all must match)
            terms = self._filter_text.split()
            for term in terms:
                if not (term in name_lower or term in path_lower or term in ext_lower):
                    return False

        return True
