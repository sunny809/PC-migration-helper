"""SizeStatsWidget — category size summary display for the review page."""

from __future__ import annotations

from typing import Dict

from src.constants import CATEGORY_DISPLAY, FileCategory
from src.utils.human_size import format_size

try:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QPainter, QPen
    from PySide6.QtWidgets import (
        QHBoxLayout,
        QLabel,
        QVBoxLayout,
        QWidget,
    )
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False


# Category colors for the bar chart
CATEGORY_COLORS = {
    FileCategory.DOCUMENTS: "#2196F3",  # Blue
    FileCategory.PHOTOS: "#4CAF50",     # Green
    FileCategory.VIDEOS: "#FF9800",     # Orange
    FileCategory.MUSIC: "#9C27B0",      # Purple
    FileCategory.ARCHIVES: "#795548",   # Brown
    FileCategory.BROWSER_DATA: "#E91E63",  # Pink
    FileCategory.OTHER: "#9E9E9E",      # Gray
}


class CategoryBar(QWidget if HAS_PYSIDE6 else object):
    """A horizontal bar showing the proportion of a single category."""

    def __init__(self, category: FileCategory, total_size: int,
                 selected_size: int, parent=None):
        if not HAS_PYSIDE6:
            return
        super().__init__(parent)
        self.category = category
        self.total_size = total_size
        self.selected_size = selected_size
        self.color = QColor(CATEGORY_COLORS.get(category, "#9E9E9E"))
        self.setFixedHeight(28)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the category bar UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        # Category name and icon
        display_name, _ = CATEGORY_DISPLAY.get(self.category, (self.category.value, ""))
        name_label = QLabel(display_name)
        name_label.setFixedWidth(160)
        name_label.setStyleSheet("font-size: 12px;")
        layout.addWidget(name_label)

        # Size bar (custom painted)
        self.bar_widget = QWidget()
        self.bar_widget.setFixedHeight(16)
        self.bar_widget.setMinimumWidth(200)
        layout.addWidget(self.bar_widget, 1)

        # Size text
        size_text = f"{format_size(self.selected_size)} / {format_size(self.total_size)}"
        size_label = QLabel(size_text)
        size_label.setFixedWidth(140)
        size_label.setStyleSheet("font-size: 12px; color: #555;")
        size_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(size_label)

    def paintEvent(self, event):
        """Paint the category bar."""
        if not HAS_PYSIDE6:
            return
        super().paintEvent(event)

        # Find the bar widget position
        bar = self.bar_widget
        if bar is None:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bar_rect = bar.geometry()

        # Background
        painter.setBrush(QColor("#e0e0e0"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(bar_rect, 4, 4)

        # Total bar
        if self.total_size > 0:
            total_ratio = 1.0
            total_width = int(bar_rect.width() * total_ratio)
            total_rect = bar_rect.__class__(
                bar_rect.x(), bar_rect.y(),
                total_width, bar_rect.height()
            )
            painter.setBrush(self.color.lighter(150))
            painter.drawRoundedRect(total_rect, 4, 4)

            # Selected bar
            selected_ratio = self.selected_size / self.total_size
            selected_width = int(bar_rect.width() * selected_ratio)
            if selected_width > 0:
                selected_rect = bar_rect.__class__(
                    bar_rect.x(), bar_rect.y(),
                    selected_width, bar_rect.height()
                )
                painter.setBrush(self.color)
                painter.drawRoundedRect(selected_rect, 4, 4)

        painter.end()


class SizeStatsWidget(QWidget if HAS_PYSIDE6 else object):
    """Widget showing a summary of file sizes by category.

    Displays horizontal bars for each category showing
    selected vs total size.
    """

    def __init__(self, parent=None):
        if not HAS_PYSIDE6:
            return
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setSpacing(4)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._bars: Dict[FileCategory, CategoryBar] = {}

        # Title
        title = QLabel("分类统计 / Category Statistics")
        title.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 4px;")
        self._layout.addWidget(title)

        # Total summary
        self._total_label = QLabel("")
        self._total_label.setStyleSheet("font-size: 13px; color: #333; margin-bottom: 8px;")
        self._layout.addWidget(self._total_label)

    def update_stats(self, stats: Dict[FileCategory, Dict]) -> None:
        """Update the statistics display.

        Args:
            stats: Dict from FileTreeModel.get_category_stats().
                   Maps FileCategory to {'total', 'selected', 'total_size', 'selected_size'}.
        """
        if not HAS_PYSIDE6:
            return

        # Clear existing bars
        for bar in self._bars.values():
            self._layout.removeWidget(bar)
            bar.deleteLater()
        self._bars.clear()

        # Create new bars for categories with files
        total_selected = 0
        total_all = 0

        for category in FileCategory:
            cat_stats = stats.get(category)
            if cat_stats is None or cat_stats.get("total", 0) == 0:
                continue

            bar = CategoryBar(
                category,
                cat_stats["total_size"],
                cat_stats["selected_size"],
                self,
            )
            self._layout.addWidget(bar)
            self._bars[category] = bar

            total_selected += cat_stats["selected_size"]
            total_all += cat_stats["total_size"]

        # Update total label
        self._total_label.setText(
            f"已选 / Selected: {format_size(total_selected)} / {format_size(total_all)}"
        )
