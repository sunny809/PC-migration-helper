"""FileTreeView — QTreeView subclass with checkbox click handling and context menu."""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Optional

from src.ui.widgets.file_tree_model import FileNode

try:
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QMenu, QTreeView, QHeaderView
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False


class FileTreeView(QTreeView if HAS_PYSIDE6 else object):
    """Custom QTreeView for the file review page.

    Features:
    - Click on checkbox area toggles check state
    - Click on row selects the row
    - Context menu with "Open file" and "Open containing folder"
    - Double-click opens file
    - Column resizing and sorting
    """

    # Signal emitted when a file is double-clicked
    file_double_clicked = Signal(str)  # file path

    def __init__(self, parent=None):
        if not HAS_PYSIDE6:
            return
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Configure the tree view appearance and behavior."""
        # Header setup
        header = self.header()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

        # Column widths
        self.setColumnWidth(0, 300)  # Name
        self.setColumnWidth(1, 100)  # Size
        self.setColumnWidth(2, 150)  # Modified
        self.setColumnWidth(3, 300)  # Path

        # Sorting
        self.setSortingEnabled(True)

        # Selection
        self.setSelectionMode(QTreeView.SelectionMode.SingleSelection)

        # Alternating row colors
        self.setAlternatingRowColors(True)

        # Double-click to expand (not open file)
        self.setExpandsOnDoubleClick(False)
        self.doubleClicked.connect(self._on_double_click)

        # Animated expand/collapse
        self.setAnimated(True)

        # Context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)

    def mousePressEvent(self, event):
        """Handle mouse press events for checkbox toggling."""
        if not HAS_PYSIDE6:
            return

        # Get the index at the click position
        index = self.indexAt(event.position().toPoint())

        if index.isValid():
            # Check if click is in the checkbox area (first column)
            if index.column() == 0:
                # Toggle check state
                current_state = self.model().data(
                    index, Qt.ItemDataRole.CheckStateRole
                )
                if current_state is not None:
                    new_state = (
                        Qt.CheckState.Unchecked
                        if current_state == Qt.CheckState.Checked
                        else Qt.CheckState.Checked
                    )
                    self.model().setData(
                        index, new_state, Qt.ItemDataRole.CheckStateRole
                    )
                    return

        super().mousePressEvent(event)

    def _on_double_click(self, index) -> None:
        """Handle double-click on a tree item."""
        if not HAS_PYSIDE6:
            return

        # Get file path from the model
        file_path = self.model().data(index, Qt.ItemDataRole.UserRole + 1)  # FULL_PATH_ROLE
        if file_path and os.path.isfile(file_path):
            self.file_double_clicked.emit(file_path)
            self._open_file(file_path)

    def _on_context_menu(self, position) -> None:
        """Show context menu for file operations."""
        if not HAS_PYSIDE6:
            return

        index = self.indexAt(position)
        if not index.isValid():
            return

        file_path = self.model().data(index, Qt.ItemDataRole.UserRole + 1)  # FULL_PATH_ROLE
        if not file_path:
            return

        menu = QMenu(self)

        # Open file action
        if os.path.isfile(file_path):
            open_action = QAction("打开文件 / Open File", self)
            open_action.triggered.connect(lambda: self._open_file(file_path))
            menu.addAction(open_action)

        # Open containing folder action
        folder_path = file_path if os.path.isdir(file_path) else os.path.dirname(file_path)
        if os.path.isdir(folder_path):
            folder_action = QAction("打开所在文件夹 / Open Containing Folder", self)
            folder_action.triggered.connect(lambda: self._open_folder(folder_path))
            menu.addAction(folder_action)

        if menu.actions():
            menu.exec(self.viewport().mapToGlobal(position))

    def _open_file(self, file_path: str) -> None:
        """Open a file with the system's default application."""
        try:
            if os.name == "nt":
                os.startfile(file_path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", file_path])
            else:
                subprocess.run(["xdg-open", file_path])
        except Exception as e:
            from src.utils.logger import setup_logging
            logger = setup_logging()
            logger.warning(f"Cannot open file {file_path}: {e}")

    def _open_folder(self, folder_path: str) -> None:
        """Open a folder in the system file explorer."""
        try:
            if os.name == "nt":
                os.startfile(folder_path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", folder_path])
            else:
                subprocess.run(["xdg-open", folder_path])
        except Exception as e:
            from src.utils.logger import setup_logging
            logger = setup_logging()
            logger.warning(f"Cannot open folder {folder_path}: {e}")

    def expand_all_categories(self) -> None:
        """Expand all category (top-level) nodes."""
        if not HAS_PYSIDE6:
            return
        model = self.model()
        if model is None:
            return
        for row in range(model.rowCount()):
            index = model.index(row, 0)
            self.expand(index)

    def collapse_all(self) -> None:
        """Collapse all nodes."""
        if not HAS_PYSIDE6:
            return
        self.collapseAll()
