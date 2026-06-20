"""TreemapWidget — squarified treemap visualization for file category sizes.

Replaces the horizontal bar chart with a space-filling rectangle layout.
Each block size = proportion of total file size.
Click a block to filter the file tree to that category.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from src.constants import CATEGORY_DISPLAY, FileCategory
from src.utils.human_size import format_size

try:
    from PySide6.QtCore import Qt, QRect, QRectF, Signal
    from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPen
    from PySide6.QtWidgets import QWidget
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False
    # Stubs for testing
    class QWidget:  # type: ignore[no-redef]
        pass
    class Signal:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs): pass
        def emit(self, *args): pass
    class Qt:  # type: ignore[no-redef]
        class AlignmentFlag:
            AlignLeft = 0
            AlignTop = 0
        class PenStyle:
            NoPen = 0
        class TextElideMode:
            ElideRight = 0
        class MouseButton:
            LeftButton = 1
        class GlobalColor:
            white = "#FFFFFF"
    class QColor:  # type: ignore[no-redef]
        def __init__(self, *args): pass
        def lighter(self, *args): return self
    class QRectF:
        def __init__(self, *args):
            if len(args) == 4:
                self._x, self._y, self._w, self._h = args
            elif len(args) == 1 and hasattr(args[0], '_x'):
                # Copy from another QRectF
                other = args[0]
                self._x = other._x
                self._y = other._y
                self._w = other._w
                self._h = other._h
            elif len(args) == 2:
                self._x = self._y = 0
                self._w = args[0]
                self._h = args[1]
            else:
                self._x = self._y = self._w = self._h = 0
        def x(self): return self._x
        def y(self): return self._y
        def width(self): return self._w
        def height(self): return self._h


# Category colors (mirrors size_stats_widget.py)
CATEGORY_COLORS = {
    FileCategory.DOCUMENTS: "#2563EB",    # Blue
    FileCategory.PHOTOS: "#16A34A",       # Green
    FileCategory.VIDEOS: "#EA580C",       # Orange
    FileCategory.MUSIC: "#7C3AED",        # Purple
    FileCategory.ARCHIVES: "#78716C",     # Brown
    FileCategory.BROWSER_DATA: "#DB2777", # Pink
    FileCategory.OTHER: "#6B7280",        # Gray
}


class BlockData:
    """Internal data for a single treemap block.

    Uses plain types (str, float, tuple) so it's testable without Qt.
    The rect is a tuple (x, y, w, h) — converted to QRectF in paint code.
    """
    def __init__(self, name: str, value: float, color: str,
                 category: FileCategory, count: int,
                 selected_size: int, selected_count: int):
        self.name = name
        self.value = value
        self.color = color
        self.category = category
        self.count = count
        self.selected_size = selected_size
        self.selected_count = selected_count
        self.rect: Tuple[float, float, float, float] = (0, 0, 0, 0)


class TreemapWidget(QWidget if HAS_PYSIDE6 else object):
    """Squarified treemap showing file category sizes.

    Usage:
        widget = TreemapWidget()
        widget.set_data(stats)   # stats from FileTreeModel.get_category_stats()
        widget.block_clicked.connect(lambda cat: filter_tree(cat))
    """

    block_clicked = Signal(object)  # FileCategory
    block_hovered = Signal(object)  # FileCategory or None

    def __init__(self, parent=None):
        if not HAS_PYSIDE6:
            return
        super().__init__(parent)
        self._blocks: List[BlockData] = []
        self._layout_cache: List[BlockData] = []
        self._hover_index: int = -1
        self._padding = 4       # gap between blocks
        self._min_block_size = 40  # minimum pixel dimension to show text
        self.setMouseTracking(True)
        self.setMinimumHeight(200)

    def set_data(self, stats: Dict[FileCategory, Dict]) -> None:
        """Set category stats and redraw the treemap.

        Args:
            stats: Dict from FileTreeModel.get_category_stats().
                   Maps FileCategory to {'total', 'selected',
                                         'total_size', 'selected_size'}.
        """
        self._blocks = []
        for cat, s in stats.items():
            total = s.get("total", 0)
            total_size = s.get("total_size", 0)
            if total == 0 or total_size == 0:
                continue
            display_name, _ = CATEGORY_DISPLAY.get(cat, (cat.value, ""))
            color = CATEGORY_COLORS.get(cat, "#6B7280")
            self._blocks.append(BlockData(
                name=display_name,
                value=float(total_size),
                color=color,
                category=cat,
                count=total,
                selected_size=s.get("selected_size", 0),
                selected_count=s.get("selected", 0),
            ))

        # Sort descending by value (squarified algorithm requirement)
        self._blocks.sort(key=lambda b: -b.value)
        self._layout_cache = []
        self._hover_index = -1
        self.update()

    def _recalc_layout(self) -> None:
        """Recalculate the treemap layout for current widget size."""
        if not self._blocks:
            self._layout_cache = []
            return

        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            return

        available = QRectF(
            float(self._padding), float(self._padding),
            float(w - 2 * self._padding), float(h - 2 * self._padding),
        )

        self._layout_cache = self._squarify(
            self._blocks, available
        )

    def _squarify(self, items: List[BlockData], rect: QRectF
                   ) -> List[BlockData]:
        """Squarified treemap layout algorithm.

        Args:
            items: Blocks sorted by value descending.
            rect: Available bounding rectangle.

        Returns:
            List of BlockData with rect attributes set.
        """
        if not items or rect.width() <= 0 or rect.height() <= 0:
            return []

        total_value = sum(i.value for i in items)
        if total_value <= 0:
            return []

        result: List[BlockData] = []

        # Internal recursive squarification
        def _layout_row(row_items: List[BlockData], row_rect: QRectF):
            """Layout a single row of items within row_rect."""
            if not row_items:
                return
            row_total = sum(i.value for i in row_items)
            if row_total <= 0:
                return

            if row_rect.width() >= row_rect.height():
                # Horizontal row: divide width
                cur_x = row_rect.x()
                for item in row_items:
                    item_w = row_rect.width() * (item.value / row_total)
                    item.rect = QRectF(cur_x, row_rect.y(),
                                       item_w, row_rect.height())
                    cur_x += item_w
                    result.append(item)
            else:
                # Vertical row: divide height
                cur_y = row_rect.y()
                for item in row_items:
                    item_h = row_rect.height() * (item.value / row_total)
                    item.rect = QRectF(row_rect.x(), cur_y,
                                       row_rect.width(), item_h)
                    cur_y += item_h
                    result.append(item)

        def _worst_ratio(row_items: List[BlockData], length: float
                         ) -> float:
            """Calculate worst aspect ratio for a row.

            Args:
                row_items: Items in the current row.
                length: Available length (width or height of row area).

            Returns:
                Worst (largest) aspect ratio in the row.
            """
            if not row_items or length <= 0:
                return float('inf')
            row_sum = sum(i.value for i in row_items)
            if row_sum <= 0:
                return float('inf')
            worst = 0.0
            for item in row_items:
                ratio = (length * length * item.value) / (row_sum * row_sum)
                ratio = max(ratio, 1.0 / ratio)  # aspect ratio >= 1
                worst = max(worst, ratio)
            return worst

        # --- Main squarify loop ---
        remaining = list(items)
        remaining_rect = QRectF(rect)

        while remaining:
            if remaining_rect.width() <= 0 or remaining_rect.height() <= 0:
                break

            row: List[BlockData] = []
            remaining_total = sum(r.value for r in remaining)
            remaining_len = (remaining_rect.width()
                             if remaining_rect.width() >= remaining_rect.height()
                             else remaining_rect.height())

            # Calculate row area proportion
            while remaining:
                item = remaining.pop(0)
                row.append(item)

                # Calculate the length allocated to this row
                row_sum = sum(r.value for r in row)
                row_length = remaining_len * (row_sum / remaining_total)

                worst_current = _worst_ratio(row, row_length)

                if len(row) > 1:
                    # Check previous row without the last item
                    prev_row = row[:-1]
                    prev_sum = sum(r.value for r in prev_row)
                    prev_length = remaining_len * (prev_sum / remaining_total)
                    worst_prev = _worst_ratio(prev_row, prev_length)

                    if worst_current > worst_prev:
                        # Last item made it worse, freeze row without it
                        remaining.insert(0, item)
                        row.pop()
                        break

            # Layout the frozen row
            row_sum = sum(r.value for r in row)
            if remaining_rect.width() >= remaining_rect.height():
                # Horizontal row
                row_rect = QRectF(
                    remaining_rect.x(), remaining_rect.y(),
                    remaining_rect.width() * (row_sum / remaining_total),
                    remaining_rect.height(),
                )
                remaining_rect = QRectF(
                    remaining_rect.x() + row_rect.width(),
                    remaining_rect.y(),
                    remaining_rect.width() - row_rect.width(),
                    remaining_rect.height(),
                )
            else:
                # Vertical row
                row_rect = QRectF(
                    remaining_rect.x(), remaining_rect.y(),
                    remaining_rect.width(),
                    remaining_rect.height() * (row_sum / remaining_total),
                )
                remaining_rect = QRectF(
                    remaining_rect.x(), remaining_rect.y() + row_rect.height(),
                    remaining_rect.width(),
                    remaining_rect.height() - row_rect.height(),
                )

            _layout_row(row, row_rect)
            remaining_total -= row_sum

        return result

    def paintEvent(self, event) -> None:
        """Render the treemap."""
        if not HAS_PYSIDE6:
            return
        super().paintEvent(event)

        if not self._layout_cache:
            self._recalc_layout()
        if not self._layout_cache:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        for i, block in enumerate(self._layout_cache):
            rect = block.rect
            if rect.width() <= 0 or rect.height() <= 0:
                continue

            # Fill color (lighter if hovered)
            color = block.color
            if i == self._hover_index:
                color = color.lighter(130)
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(QColor("#FFFFFF"), 2))
            painter.drawRoundedRect(rect, 4, 4)

            # Draw text if block is large enough
            if (rect.width() >= self._min_block_size
                    and rect.height() >= self._min_block_size):
                painter.setPen(QColor("#FFFFFF"))

                # Block name (font size scales with block height)
                name_size = max(10, min(16, int(rect.height() / 6)))
                name_font = QFont()
                name_font.setPixelSize(name_size)
                name_font.setBold(True)
                painter.setFont(name_font)

                # Draw category name
                name_rect = QRectF(rect.x() + 6, rect.y() + 6,
                                   rect.width() - 12, rect.height() / 3)
                elided_name = self._elide_text(
                    painter, block.name, name_rect
                )
                painter.drawText(name_rect, Qt.AlignmentFlag.AlignLeft
                                 | Qt.AlignmentFlag.AlignTop, elided_name)

                # Draw size (smaller font)
                size_size = max(9, min(13, int(rect.height() / 8)))
                size_font = QFont()
                size_font.setPixelSize(size_size)
                painter.setFont(size_font)

                size_rect = QRectF(rect.x() + 6,
                                   rect.y() + rect.height() / 3 + 2,
                                   rect.width() - 12,
                                   rect.height() / 4)
                painter.drawText(size_rect, Qt.AlignmentFlag.AlignLeft
                                 | Qt.AlignmentFlag.AlignTop,
                                 format_size(int(block.value)))

                # Draw file count
                count_rect = QRectF(rect.x() + 6,
                                    rect.y() + rect.height() * 0.6,
                                    rect.width() - 12,
                                    rect.height() / 4)
                painter.drawText(count_rect, Qt.AlignmentFlag.AlignLeft
                                 | Qt.AlignmentFlag.AlignTop,
                                 f"{block.count:,} files")

        painter.end()

    def _elide_text(self, painter: QPainter, text: str,
                    rect: QRectF) -> str:
        """Elide text to fit within a rectangle."""
        fm = QFontMetrics(painter.font())
        elided = fm.elidedText(text, Qt.TextElideMode.ElideRight,
                               int(rect.width()))
        return elided

    def _get_block_at(self, pos) -> int:
        """Find the block index at a given position."""
        for i, block in enumerate(self._layout_cache):
            if block.rect.contains(pos.x(), pos.y()):
                return i
        return -1

    def mouseMoveEvent(self, event) -> None:
        """Handle mouse move for hover effects."""
        if not HAS_PYSIDE6:
            return
        idx = self._get_block_at(event.position())
        if idx != self._hover_index:
            self._hover_index = idx
            self.update()
            if 0 <= idx < len(self._layout_cache):
                self.block_hovered.emit(self._layout_cache[idx].category)
            else:
                self.block_hovered.emit(None)

    def mousePressEvent(self, event) -> None:
        """Handle mouse click to emit category signal."""
        if not HAS_PYSIDE6:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            idx = self._get_block_at(event.position())
            if 0 <= idx < len(self._layout_cache):
                self.block_clicked.emit(self._layout_cache[idx].category)

    def resizeEvent(self, event) -> None:
        """Recalculate layout on resize."""
        super().resizeEvent(event)
        self._layout_cache = []
        self._recalc_layout()
        self.update()

    def leaveEvent(self, event) -> None:
        """Clear hover state when mouse leaves."""
        self._hover_index = -1
        self.block_hovered.emit(None)
        self.update()
