"""DriveListWidget — custom widget for displaying and selecting migration target drives."""

from __future__ import annotations

from typing import List, Optional

from src.models.migration_target import DriveType, MigrationTarget
from src.utils.human_size import format_size

try:
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtWidgets import (
        QButtonGroup,
        QFrame,
        QHBoxLayout,
        QLabel,
        QProgressBar,
        QRadioButton,
        QVBoxLayout,
        QWidget,
    )
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False


class DriveCard(QFrame if HAS_PYSIDE6 else object):
    """A card widget representing a single drive.

    Shows drive icon, letter, label, type, and space usage.
    """

    def __init__(self, target: MigrationTarget, parent=None):
        if not HAS_PYSIDE6:
            return
        super().__init__(parent)
        self.target = target
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the drive card UI."""
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setFixedHeight(80)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)

        # Radio button for selection
        self.radio = QRadioButton()
        layout.addWidget(self.radio)

        # Drive info section
        info_layout = QVBoxLayout()

        # Top line: icon + drive name
        top_line = QHBoxLayout()
        type_display, icon = self.target.type_display
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 24px;")
        top_line.addWidget(icon_label)

        name_label = QLabel(self.target.display_name)
        name_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        top_line.addWidget(name_label)

        type_label = QLabel(type_display)
        type_label.setStyleSheet("color: #888; font-size: 12px;")
        top_line.addWidget(type_label)
        top_line.addStretch()

        info_layout.addLayout(top_line)

        # Bottom line: space usage bar + free space text
        bottom_line = QHBoxLayout()

        # Space progress bar
        space_bar = QProgressBar()
        space_bar.setRange(0, 100)
        space_bar.setValue(int(self.target.usage_ratio * 100))
        space_bar.setFixedHeight(12)
        space_bar.setFormat("")
        space_bar.setStyleSheet("""
            QProgressBar {
                background-color: #e0e0e0;
                border-radius: 6px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 6px;
            }
        """)
        if self.target.usage_ratio > 0.9:
            space_bar.setStyleSheet("""
                QProgressBar {
                    background-color: #e0e0e0;
                    border-radius: 6px;
                }
                QProgressBar::chunk {
                    background-color: #f44336;
                    border-radius: 6px;
                }
            """)
        bottom_line.addWidget(space_bar, 1)

        # Free space text
        free_text = f"可用 / Free: {format_size(self.target.free_bytes)}"
        free_label = QLabel(free_text)
        free_label.setStyleSheet("color: #666; font-size: 12px;")
        bottom_line.addWidget(free_label)

        info_layout.addLayout(bottom_line)
        layout.addLayout(info_layout, 1)


class DriveListWidget(QWidget if HAS_PYSIDE6 else object):
    """Widget that displays a list of drive cards for target selection.

    Emits target_selected signal when a drive is selected.
    """

    target_selected = Signal(object)  # MigrationTarget

    def __init__(self, parent=None):
        if not HAS_PYSIDE6:
            return
        super().__init__(parent)
        self._targets: List[MigrationTarget] = []
        self._cards: List[DriveCard] = []
        self._selected_target: Optional[MigrationTarget] = None
        self._button_group = QButtonGroup(self)
        self._button_group.idClicked.connect(self._on_selection_changed)

        self._layout = QVBoxLayout(self)
        self._layout.setSpacing(8)
        self._layout.setContentsMargins(0, 0, 0, 0)

    def set_drives(self, targets: List[MigrationTarget]) -> None:
        """Update the drive list with new targets.

        Args:
            targets: List of MigrationTarget objects to display.
        """
        if not HAS_PYSIDE6:
            return

        # Clear existing cards
        for card in self._cards:
            self._layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()
        self._targets = targets

        # Create new cards
        for i, target in enumerate(targets):
            card = DriveCard(target, self)
            self._button_group.addButton(card.radio, i)
            self._layout.addWidget(card)
            self._cards.append(card)

        # Select first removable/network drive by default
        for i, target in enumerate(targets):
            if target.drive_type in (DriveType.REMOVABLE, DriveType.NETWORK):
                self._cards[i].radio.setChecked(True)
                self._selected_target = target
                break

        self._layout.addStretch()

    def get_selected_target(self) -> Optional[MigrationTarget]:
        """Get the currently selected migration target."""
        return self._selected_target

    def _on_selection_changed(self, button_id: int) -> None:
        """Handle drive selection change."""
        if 0 <= button_id < len(self._targets):
            self._selected_target = self._targets[button_id]
            self.target_selected.emit(self._selected_target)
