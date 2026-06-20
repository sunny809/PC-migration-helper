"""Tests for TreemapWidget — squarified treemap layout algorithm."""

import pytest

from src.constants import FileCategory


class TestTreemapLayout:
    """Test the squarified treemap layout logic in isolation."""

    def _QF(self):
        """Get QRectF stub from widget module (works without PySide6)."""
        from src.ui.widgets.treemap_widget import QRectF
        return QRectF

    def test_blocks_sorted_by_size(self):
        """Block data should be sorted descending by value."""
        from src.ui.widgets.treemap_widget import BlockData

        blocks = [
            BlockData("A", 100, "#000", FileCategory.DOCUMENTS, 10, 50, 5),
            BlockData("B", 300, "#000", FileCategory.PHOTOS, 20, 150, 10),
            BlockData("C", 50, "#000", FileCategory.VIDEOS, 5, 25, 2),
        ]
        blocks.sort(key=lambda b: -b.value)
        assert blocks[0].name == "B"
        assert blocks[1].name == "A"
        assert blocks[2].name == "C"

    def test_squarify_single_block(self):
        """Single block fills the entire rectangle."""
        from src.ui.widgets.treemap_widget import TreemapWidget, BlockData

        QF = self._QF()
        widget = TreemapWidget()
        block = BlockData("Test", 100, "#000", FileCategory.OTHER, 1, 100, 1)
        rect = QF(0, 0, 100, 100)
        result = widget._squarify([block], rect)

        assert len(result) == 1
        r = result[0].rect
        assert r.x() == 0
        assert r.y() == 0
        assert r.width() == 100
        assert r.height() == 100

    def test_squarify_two_blocks(self):
        """Two blocks should be laid out without overlap."""
        from src.ui.widgets.treemap_widget import TreemapWidget, BlockData

        QF = self._QF()
        widget = TreemapWidget()
        b1 = BlockData("Big", 300, "#000", FileCategory.DOCUMENTS, 3, 150, 1)
        b2 = BlockData("Small", 100, "#000", FileCategory.PHOTOS, 1, 100, 1)
        rect = QF(0, 0, 200, 100)

        result = widget._squarify([b1, b2], rect)
        assert len(result) == 2

        r1 = result[0].rect
        r2 = result[1].rect
        assert r1.width() > 0
        assert r1.height() > 0
        assert r2.width() > 0
        assert r2.height() > 0
        # Verify they don't overlap (just check bounds)
        r1_right = r1.x() + r1.width()
        r1_bottom = r1.y() + r1.height()
        assert r1_right <= r2.x() or r1_bottom <= r2.y()

    def test_squarify_proportional_sizes(self):
        """Equal blocks should get roughly equal area."""
        from src.ui.widgets.treemap_widget import TreemapWidget, BlockData

        QF = self._QF()
        widget = TreemapWidget()
        b1 = BlockData("A", 200, "#000", FileCategory.DOCUMENTS, 2, 100, 1)
        b2 = BlockData("B", 200, "#000", FileCategory.PHOTOS, 2, 100, 1)
        rect = QF(0, 0, 200, 100)

        result = widget._squarify([b1, b2], rect)
        assert len(result) == 2

        a1 = result[0].rect.width() * result[0].rect.height()
        a2 = result[1].rect.width() * result[1].rect.height()
        if a1 > 0 and a2 > 0:
            ratio = max(a1, a2) / min(a1, a2)
            assert ratio < 2.5  # Reasonable tolerance for equal split

    def test_empty_blocks(self):
        """No blocks returns empty list."""
        from src.ui.widgets.treemap_widget import TreemapWidget

        QF = self._QF()
        widget = TreemapWidget()
        result = widget._squarify([], QF(0, 0, 100, 100))
        assert result == []

    def test_zero_width_rect(self):
        """Zero-width rectangle returns empty list."""
        from src.ui.widgets.treemap_widget import TreemapWidget, BlockData

        QF = self._QF()
        widget = TreemapWidget()
        block = BlockData("A", 100, "#000", FileCategory.OTHER, 1, 0, 0)
        result = widget._squarify([block], QF(0, 0, 0, 100))
        assert result == []

    def test_three_blocks_fill_rect(self):
        """Three blocks should fill the rectangle completely."""
        from src.ui.widgets.treemap_widget import TreemapWidget, BlockData

        QF = self._QF()
        widget = TreemapWidget()
        blocks = [
            BlockData("A", 500, "#000", FileCategory.DOCUMENTS, 5, 250, 2),
            BlockData("B", 300, "#000", FileCategory.PHOTOS, 3, 150, 1),
            BlockData("C", 200, "#000", FileCategory.VIDEOS, 2, 100, 1),
        ]
        rect = QF(0, 0, 200, 150)

        result = widget._squarify(blocks, rect)

        total_block_area = sum(r.rect.width() * r.rect.height() for r in result)
        expected_area = rect.width() * rect.height()
        if expected_area > 0:
            assert abs(total_block_area - expected_area) / expected_area < 0.1
