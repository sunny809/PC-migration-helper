"""ReviewPage — Step 2: Review and select files for migration."""

from __future__ import annotations

import os
from typing import Optional

from src.constants import CATEGORY_DISPLAY, FileCategory
from src.models.scan_result import ScanResult
from src.ui.widgets.file_tree_filter import FileTreeFilterProxy
from src.ui.widgets.file_tree_model import FileTreeModel
from src.ui.widgets.file_tree_view import FileTreeView
from src.ui.widgets.size_stats_widget import SizeStatsWidget
from src.utils.human_size import format_size

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QComboBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPushButton,
        QSplitter,
        QVBoxLayout,
        QWidget,
    )
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False


class ReviewPage(QWidget if HAS_PYSIDE6 else object):
    """Step 2 page: Review discovered files and select for migration.

    Features:
    - File tree view with tri-state checkboxes
    - Search/filter by name and category
    - Select All / Deselect All
    - Category size statistics
    - Double-click to open file, right-click to open folder
    """

    def __init__(self, parent=None):
        if not HAS_PYSIDE6:
            return
        super().__init__(parent)
        self._tree_model = FileTreeModel()
        self._filter_proxy = FileTreeFilterProxy()
        self._filter_proxy.setSourceModel(self._tree_model)
        self._scan_result: Optional[ScanResult] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the review page UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(32, 24, 32, 24)

        # Title
        title = QLabel("审查文件 / Review Files")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        # Description
        desc = QLabel(
            "检查发现的文件，取消勾选不需要迁移的文件。双击文件可预览。\n"
            "Review discovered files and uncheck those you don't want to migrate. "
            "Double-click a file to preview."
        )
        desc.setObjectName("pageDescription")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Toolbar: search + category filter + action buttons
        toolbar = QHBoxLayout()

        # Search input
        self._search_input = QLineEdit()
        self._search_input.setObjectName("searchInput")
        self._search_input.setPlaceholderText(
            "搜索文件名或路径 / Search file name or path..."
        )
        self._search_input.textChanged.connect(self._on_search)
        toolbar.addWidget(self._search_input, 1)

        # Category filter
        self._category_combo = QComboBox()
        self._category_combo.addItem("全部分类 / All Categories", None)
        for category in FileCategory:
            display_name, _ = CATEGORY_DISPLAY.get(category, (category.value, ""))
            self._category_combo.addItem(display_name, category)
        self._category_combo.currentIndexChanged.connect(self._on_category_filter)
        self._category_combo.setFixedWidth(200)
        toolbar.addWidget(self._category_combo)

        # Select All
        self._select_all_btn = QPushButton("全选 / Select All")
        self._select_all_btn.setObjectName("secondaryButton")
        self._select_all_btn.clicked.connect(self._on_select_all)
        toolbar.addWidget(self._select_all_btn)

        # Deselect All
        self._deselect_all_btn = QPushButton("取消全选 / Deselect All")
        self._deselect_all_btn.setObjectName("secondaryButton")
        self._deselect_all_btn.clicked.connect(self._on_deselect_all)
        toolbar.addWidget(self._deselect_all_btn)

        layout.addLayout(toolbar)

        # Main content: splitter with tree view and stats
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # File tree
        tree_container = QWidget()
        tree_layout = QVBoxLayout(tree_container)
        tree_layout.setContentsMargins(0, 0, 0, 0)

        self._tree_view = FileTreeView()
        self._tree_view.setModel(self._filter_proxy)  # Use proxy model
        self._tree_view.file_double_clicked.connect(self._on_file_double_clicked)
        tree_layout.addWidget(self._tree_view)

        # Filter result count
        self._filter_label = QLabel("")
        self._filter_label.setStyleSheet("color: #888; font-size: 11px;")
        tree_layout.addWidget(self._filter_label)

        splitter.addWidget(tree_container)

        # Size stats panel
        self._stats_widget = SizeStatsWidget()
        self._stats_widget.setMinimumWidth(280)
        self._stats_widget.setMaximumWidth(400)
        splitter.addWidget(self._stats_widget)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter, 1)

        # Bottom summary bar
        self._summary_bar = QLabel("")
        self._summary_bar.setStyleSheet(
            "background-color: #f0f7ff; padding: 8px 12px; "
            "border-radius: 4px; font-size: 13px; color: #333;"
        )
        layout.addWidget(self._summary_bar)

    def load_scan_result(self, result: ScanResult) -> None:
        """Load scan results into the review page.

        Args:
            result: The ScanResult from the scan operation.
        """
        if not HAS_PYSIDE6:
            return

        self._scan_result = result
        self._tree_model.load_scan_result(result)

        # Expand category nodes
        self._tree_view.expand_all_categories()

        # Update stats
        self._update_stats()

        # Connect model selection change signal
        self._tree_model.selection_changed.connect(self._update_stats)

        # Update summary
        self._update_summary()

        # Reset filter
        self._search_input.setText("")
        self._category_combo.setCurrentIndex(0)

    def get_selected_files(self):
        """Get the list of selected FileEntry objects."""
        if self._tree_model:
            return self._tree_model.get_selected_files()
        return []

    def get_selected_size(self) -> int:
        """Get total size of selected files."""
        if self._tree_model:
            return self._tree_model.get_selected_size()
        return 0

    def _update_stats(self) -> None:
        """Update the statistics panel and summary bar."""
        if self._tree_model:
            stats = self._tree_model.get_category_stats()
            self._stats_widget.update_stats(stats)
            self._update_summary()

    def _update_summary(self) -> None:
        """Update the bottom summary bar."""
        if self._tree_model:
            selected = self._tree_model.get_selected_count()
            total = self._tree_model.get_total_count()
            selected_size = self._tree_model.get_selected_size()
            total_size = self._tree_model.get_total_size()

            self._summary_bar.setText(
                f"已选 / Selected: {selected:,} / {total:,} 文件/files  |  "
                f"{format_size(selected_size)} / {format_size(total_size)}"
            )

    def _on_search(self, text: str) -> None:
        """Handle search input changes."""
        if self._filter_proxy:
            self._filter_proxy.set_filter_text(text)
            self._update_filter_label()

    def _on_category_filter(self, index: int) -> None:
        """Handle category filter combo box changes."""
        if self._filter_proxy:
            category = self._category_combo.currentData()
            self._filter_proxy.set_filter_category(category)
            self._update_filter_label()

    def _update_filter_label(self) -> None:
        """Update the filter result count label."""
        if not HAS_PYSIDE6:
            return
        total = self._tree_model.get_total_count()
        visible = self._filter_proxy.rowCount()
        if visible < total:
            self._filter_label.setText(
                f"显示 {visible:,} / {total:,} 个分类/目录 / "
                f"Showing {visible:,} / {total:,} categories/dirs"
            )
        else:
            self._filter_label.setText("")

    def _on_select_all(self) -> None:
        """Select all files."""
        if self._tree_model:
            self._tree_model.select_all(True)

    def _on_deselect_all(self) -> None:
        """Deselect all files."""
        if self._tree_model:
            self._tree_model.select_all(False)

    def _on_file_double_clicked(self, file_path: str) -> None:
        """Handle double-click on a file to open it."""
        if not HAS_PYSIDE6:
            return
        if os.path.isfile(file_path):
            if os.name == "nt":
                os.startfile(file_path)  # type: ignore[attr-defined]
            elif os.name == "posix":
                import subprocess
                import sys
                opener = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.run([opener, file_path])
