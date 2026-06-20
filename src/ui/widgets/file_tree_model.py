"""FileTreeModel — custom QAbstractItemModel for the file review tree view.

Supports hierarchical display of files by category with tri-state checkboxes,
lazy loading, and parent/child check state propagation.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Set

from src.constants import CATEGORY_DISPLAY, FileCategory
from src.models.file_entry import FileEntry
from src.models.scan_result import ScanResult
from src.utils.human_size import format_size

try:
    from PySide6.QtCore import (
        QAbstractItemModel,
        QModelIndex,
        Qt,
        Signal,
    )
    from PySide6.QtGui import QBrush, QColor, QFont
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False
    # Stubs for non-Qt environments
    class QAbstractItemModel:  # type: ignore[no-redef]
        pass
    class QModelIndex:  # type: ignore[no-redef]
        pass
    class Qt:  # type: ignore[no-redef]
        DisplayRole = 0
        CheckStateRole = 10
        ItemIsUserCheckable = 32
        ItemIsEnabled = 32
        ItemIsSelectable = 16
        Checked = 2
        Unchecked = 0
        PartiallyChecked = 1


class TreeNode:
    """Base class for tree nodes in the file tree model."""

    def __init__(self, name: str, parent: Optional[TreeNode] = None):
        self.name = name
        self.parent_node = parent
        self.children: List[TreeNode] = []
        self._checked = True  # Default to checked

    def add_child(self, child: TreeNode) -> None:
        self.children.append(child)
        child.parent_node = self

    def child(self, row: int) -> Optional[TreeNode]:
        if 0 <= row < len(self.children):
            return self.children[row]
        return None

    def child_count(self) -> int:
        return len(self.children)

    def row(self) -> int:
        if self.parent_node is not None:
            return self.parent_node.children.index(self)
        return 0

    @property
    def checked(self) -> bool:
        return self._checked

    @checked.setter
    def checked(self, value: bool) -> None:
        self._checked = value


class CategoryNode(TreeNode):
    """Root-level node representing a file category (Documents, Photos, etc.)."""

    def __init__(self, category: FileCategory, parent: Optional[TreeNode] = None):
        display_name, _ = CATEGORY_DISPLAY.get(category, (category.value, ""))
        super().__init__(display_name, parent)
        self.category = category
        self.total_size: int = 0
        self.selected_size: int = 0

    def recalculate_sizes(self) -> None:
        """Recalculate total and selected sizes from children."""
        self.total_size = 0
        self.selected_size = 0
        for child in self.children:
            if isinstance(child, DirectoryNode):
                child.recalculate_sizes()
                self.total_size += child.total_size
                self.selected_size += child.selected_size
            elif isinstance(child, FileNode):
                self.total_size += child.file_entry.size
                if child.checked:
                    self.selected_size += child.file_entry.size


class DirectoryNode(TreeNode):
    """Node representing a directory containing files."""

    def __init__(self, dir_path: str, parent: Optional[TreeNode] = None):
        super().__init__(os.path.basename(dir_path) or dir_path, parent)
        self.dir_path = dir_path
        self.total_size: int = 0
        self.selected_size: int = 0

    def recalculate_sizes(self) -> None:
        """Recalculate total and selected sizes from children."""
        self.total_size = 0
        self.selected_size = 0
        for child in self.children:
            if isinstance(child, DirectoryNode):
                child.recalculate_sizes()
                self.total_size += child.total_size
                self.selected_size += child.selected_size
            elif isinstance(child, FileNode):
                self.total_size += child.file_entry.size
                if child.checked:
                    self.selected_size += child.file_entry.size


class FileNode(TreeNode):
    """Leaf node representing a single file."""

    def __init__(self, file_entry: FileEntry, parent: Optional[TreeNode] = None):
        super().__init__(file_entry.name, parent)
        self.file_entry = file_entry
        self._checked = file_entry.is_selected


class FileTreeModel(QAbstractItemModel if HAS_PYSIDE6 else object):
    """Custom tree model for displaying and selecting files by category.

    Hierarchy: CategoryNode -> DirectoryNode -> FileNode

    Features:
    - Tri-state checkboxes with parent/child propagation
    - Lazy population (only category nodes initially)
    - Size aggregation per category and directory
    - Sorting by name, size, date
    """

    # Custom roles
    FULL_PATH_ROLE = Qt.ItemDataRole.UserRole + 1 if HAS_PYSIDE6 else 256
    FILE_ENTRY_ROLE = Qt.ItemDataRole.UserRole + 2 if HAS_PYSIDE6 else 257
    CATEGORY_ROLE = Qt.ItemDataRole.UserRole + 3 if HAS_PYSIDE6 else 258

    # Columns
    COL_NAME = 0
    COL_SIZE = 1
    COL_MODIFIED = 2
    COL_PATH = 3
    COL_COUNT = 4

    # Signal emitted when selection changes
    if HAS_PYSIDE6:
        selection_changed = Signal()

    def __init__(self, parent=None):
        if HAS_PYSIDE6:
            super().__init__(parent)
        self._root = TreeNode("Root")
        self._category_nodes: Dict[FileCategory, CategoryNode] = {}
        self._file_nodes: List[FileNode] = []
        self._scan_result: Optional[ScanResult] = None

    def load_scan_result(self, result: ScanResult) -> None:
        """Load a ScanResult into the tree model.

        Builds the category -> directory -> file hierarchy.

        Args:
            result: The scan result containing discovered files.
        """
        if HAS_PYSIDE6:
            self.beginResetModel()

        self._root = TreeNode("Root")
        self._category_nodes = {}
        self._file_nodes = []
        self._scan_result = result

        # Create category nodes
        for category in FileCategory:
            cat_node = CategoryNode(category, self._root)
            self._category_nodes[category] = cat_node
            self._root.add_child(cat_node)

        # Group files by category, then by directory
        for file_entry in result.files:
            cat_node = self._category_nodes.get(file_entry.category)
            if cat_node is None:
                cat_node = self._category_nodes[FileCategory.OTHER]

            # Find or create directory node
            dir_path = file_entry.dir_path
            dir_node = self._find_or_create_dir_node(cat_node, dir_path)

            # Create file node
            file_node = FileNode(file_entry, dir_node)
            dir_node.add_child(file_node)
            self._file_nodes.append(file_node)

        # Remove empty category nodes and recalculate sizes
        for category in list(self._category_nodes.keys()):
            cat_node = self._category_nodes[category]
            if cat_node.child_count() == 0:
                self._root.children.remove(cat_node)
                del self._category_nodes[category]
            else:
                cat_node.recalculate_sizes()

        if HAS_PYSIDE6:
            self.endResetModel()

    def _find_or_create_dir_node(
        self, parent: TreeNode, dir_path: str
    ) -> DirectoryNode:
        """Find an existing directory node or create a new one."""
        for child in parent.children:
            if isinstance(child, DirectoryNode) and child.dir_path == dir_path:
                return child

        dir_node = DirectoryNode(dir_path, parent)
        parent.add_child(dir_node)
        return dir_node

    # --- QAbstractItemModel interface ---

    def index(self, row: int, column: int, parent=QModelIndex()) -> object:
        """Create a model index for the given row/column/parent."""
        if not HAS_PYSIDE6:
            return None

        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        parent_node = self._node_from_index(parent)
        child_node = parent_node.child(row)

        if child_node is not None:
            return self.createIndex(row, column, child_node)
        return QModelIndex()

    def parent(self, child_index=QModelIndex()) -> object:
        """Get the parent index of the given child index."""
        if not HAS_PYSIDE6:
            return None

        if not child_index.isValid():
            return QModelIndex()

        child_node = self._node_from_index(child_index)
        parent_node = child_node.parent_node

        if parent_node is None or parent_node is self._root:
            return QModelIndex()

        return self.createIndex(parent_node.row(), 0, parent_node)

    def rowCount(self, parent=QModelIndex()) -> int:
        """Return the number of rows under the given parent."""
        if not HAS_PYSIDE6:
            return 0

        if parent.column() > 0:
            return 0

        node = self._node_from_index(parent)
        return node.child_count()

    def columnCount(self, parent=QModelIndex()) -> int:
        """Return the number of columns."""
        return self.COL_COUNT

    def data(self, index, role=Qt.ItemDataRole.DisplayRole if HAS_PYSIDE6 else 0):
        """Return data for the given index and role."""
        if not HAS_PYSIDE6 or not index.isValid():
            return None

        node = self._node_from_index(index)
        column = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display_data(node, column)

        if role == Qt.ItemDataRole.CheckStateRole and column == self.COL_NAME:
            return self._check_state(node)

        if role == self.FULL_PATH_ROLE:
            if isinstance(node, FileNode):
                return node.file_entry.path
            if isinstance(node, DirectoryNode):
                return node.dir_path

        if role == self.FILE_ENTRY_ROLE:
            if isinstance(node, FileNode):
                return node.file_entry

        if role == self.CATEGORY_ROLE:
            if isinstance(node, CategoryNode):
                return node.category.value

        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole if HAS_PYSIDE6 else 2):
        """Set data for the given index and role. Handles checkbox changes."""
        if not HAS_PYSIDE6 or not index.isValid():
            return False

        if role == Qt.ItemDataRole.CheckStateRole and index.column() == self.COL_NAME:
            node = self._node_from_index(index)
            checked = value == Qt.CheckState.Checked
            self._set_checked_recursive(node, checked)
            self._update_ancestor_check_states(node)

            # Update file_entry.is_selected for FileNodes
            if isinstance(node, FileNode):
                node.file_entry.is_selected = checked

            # Emit data changed for the entire subtree
            self._emit_subtree_changed(index)

            if hasattr(self, 'selection_changed'):
                self.selection_changed.emit()
            return True

        return False

    def flags(self, index):
        """Return item flags for the given index."""
        if not HAS_PYSIDE6 or not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

        if index.column() == self.COL_NAME:
            flags |= Qt.ItemFlag.ItemIsUserCheckable

        return flags

    def headerData(self, section, orientation,
                   role=Qt.ItemDataRole.DisplayRole if HAS_PYSIDE6 else 0):
        """Return header data for the given section."""
        if not HAS_PYSIDE6:
            return None

        if orientation != Qt.Orientation.Horizontal:
            return None

        if role != Qt.ItemDataRole.DisplayRole:
            return None

        headers = [
            "名称 / Name",
            "大小 / Size",
            "修改日期 / Modified",
            "路径 / Path",
        ]
        if 0 <= section < len(headers):
            return headers[section]
        return None

    # --- Helper methods ---

    def _node_from_index(self, index) -> TreeNode:
        """Get the TreeNode from a QModelIndex."""
        if HAS_PYSIDE6 and index.isValid():
            node = index.internalPointer()
            if node is not None:
                return node
        return self._root

    def _display_data(self, node: TreeNode, column: int):
        """Get display text for a node and column."""
        if isinstance(node, CategoryNode):
            if column == self.COL_NAME:
                count = node.child_count()
                return f"{node.name} ({count})"
            if column == self.COL_SIZE:
                return format_size(node.total_size)
            return None

        if isinstance(node, DirectoryNode):
            if column == self.COL_NAME:
                return node.name
            if column == self.COL_SIZE:
                return format_size(node.total_size)
            if column == self.COL_PATH:
                return node.dir_path
            return None

        if isinstance(node, FileNode):
            if column == self.COL_NAME:
                return node.name
            if column == self.COL_SIZE:
                return format_size(node.file_entry.size)
            if column == self.COL_MODIFIED:
                return node.file_entry.modified_datetime.strftime("%Y-%m-%d %H:%M")
            if column == self.COL_PATH:
                return node.file_entry.dir_path
            return None

        return None

    def _check_state(self, node: TreeNode):
        """Get the check state for a node (tri-state support)."""
        if not HAS_PYSIDE6:
            return None

        if isinstance(node, FileNode):
            return Qt.CheckState.Checked if node.checked else Qt.CheckState.Unchecked

        # For category and directory nodes, compute from children
        if node.child_count() == 0:
            return Qt.CheckState.Unchecked

        checked_count = sum(1 for c in node.children if c.checked)
        total_count = node.child_count()

        if checked_count == 0:
            return Qt.CheckState.Unchecked
        if checked_count == total_count:
            return Qt.CheckState.Checked
        return Qt.CheckState.PartiallyChecked

    def _set_checked_recursive(self, node: TreeNode, checked: bool) -> None:
        """Set the checked state for a node and all its descendants."""
        node.checked = checked
        for child in node.children:
            self._set_checked_recursive(child, checked)
            if isinstance(child, FileNode):
                child.file_entry.is_selected = checked

    def _update_ancestor_check_states(self, node: TreeNode) -> None:
        """Update check states of ancestor nodes after a change."""
        current = node.parent_node
        while current is not None and current is not self._root:
            # Ancestor state is computed dynamically in _check_state
            # Just need to trigger dataChanged
            current = current.parent_node

    def _emit_subtree_changed(self, index) -> None:
        """Emit dataChanged for an index and all its descendants."""
        if not HAS_PYSIDE6:
            return

        # For simplicity, emit layoutChanged which refreshes the entire view
        self.layoutChanged.emit()

    # --- Public API ---

    def select_all(self, checked: bool = True) -> None:
        """Set all files to checked or unchecked."""
        for file_node in self._file_nodes:
            file_node.checked = checked
            file_node.file_entry.is_selected = checked

        if HAS_PYSIDE6:
            self.layoutChanged.emit()
            if hasattr(self, 'selection_changed'):
                self.selection_changed.emit()

    def get_selected_files(self) -> List[FileEntry]:
        """Get all currently selected file entries."""
        return [fn.file_entry for fn in self._file_nodes if fn.checked]

    def get_selected_size(self) -> int:
        """Get total size of selected files."""
        return sum(fn.file_entry.size for fn in self._file_nodes if fn.checked)

    def get_selected_count(self) -> int:
        """Get number of selected files."""
        return sum(1 for fn in self._file_nodes if fn.checked)

    def get_total_count(self) -> int:
        """Get total number of files."""
        return len(self._file_nodes)

    def get_total_size(self) -> int:
        """Get total size of all files."""
        return sum(fn.file_entry.size for fn in self._file_nodes)

    def get_category_stats(self) -> Dict[FileCategory, Dict]:
        """Get statistics per category.

        Returns:
            Dict mapping FileCategory to {'total': int, 'selected': int,
            'total_size': int, 'selected_size': int}.
        """
        stats = {}
        for category, cat_node in self._category_nodes.items():
            cat_node.recalculate_sizes()
            stats[category] = {
                "total": sum(1 for fn in self._file_nodes if fn.file_entry.category == category),
                "selected": sum(1 for fn in self._file_nodes if fn.file_entry.category == category and fn.checked),
                "total_size": cat_node.total_size,
                "selected_size": cat_node.selected_size,
            }
        return stats
