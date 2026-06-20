"""MainWindow — main application window with step-based navigation."""

from __future__ import annotations

import os
from typing import Optional

from src.constants import APP_NAME, APP_NAME_ZH, WINDOW_MIN_HEIGHT, WINDOW_MIN_WIDTH
from src.models.migration_config import MigrationConfig
from src.models.scan_result import ScanResult
from src.ui.execute_page import ExecutePage
from src.ui.review_page import ReviewPage
from src.ui.scan_page import ScanPage
from src.ui.target_page import TargetPage
from src.utils.human_size import format_size

try:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import (
        QHBoxLayout,
        QLabel,
        QPushButton,
        QStackedWidget,
        QVBoxLayout,
        QWidget,
    )
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False


class StepIndicator(QWidget if HAS_PYSIDE6 else object):
    """Custom widget showing the current step in the workflow.

    Displays four circles connected by lines, with labels.
    Current step is highlighted, completed steps are green.
    """

    STEPS = [
        ("1", "扫描 / Scan"),
        ("2", "审查 / Review"),
        ("3", "目标 / Target"),
        ("4", "执行 / Execute"),
    ]

    def __init__(self, parent=None):
        if not HAS_PYSIDE6:
            return
        super().__init__(parent)
        self._current_step = 0
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the step indicator UI."""
        layout = QHBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(32, 8, 32, 8)

        self._step_labels = []
        self._circle_labels = []
        self._line_labels = []

        for i, (num, text) in enumerate(self.STEPS):
            # Step circle + number
            circle = QLabel(num)
            circle.setFixedSize(32, 32)
            circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
            circle.setStyleSheet(self._circle_style(i))
            layout.addWidget(circle)
            self._circle_labels.append(circle)

            # Step text
            label = QLabel(text)
            label.setStyleSheet(self._label_style(i))
            layout.addWidget(label)
            self._step_labels.append(label)

            # Connector line (except after last step)
            if i < len(self.STEPS) - 1:
                line = QLabel("")
                line.setFixedHeight(2)
                line.setMinimumWidth(40)
                line.setStyleSheet("background-color: #e0e0e0;")
                layout.addWidget(line, 1)
                self._line_labels.append(line)

        layout.addStretch()

    def _circle_style(self, step_index: int) -> str:
        """Get the style for a step circle."""
        if step_index < self._current_step:
            # Completed
            return (
                "background-color: #4CAF50; color: white; "
                "border-radius: 16px; font-weight: bold; font-size: 14px;"
            )
        if step_index == self._current_step:
            # Current
            return (
                "background-color: #2196F3; color: white; "
                "border-radius: 16px; font-weight: bold; font-size: 14px;"
            )
        # Future
        return (
            "background-color: #e0e0e0; color: #999; "
            "border-radius: 16px; font-weight: bold; font-size: 14px;"
        )

    def _label_style(self, step_index: int) -> str:
        """Get the style for a step label."""
        if step_index < self._current_step:
            return "color: #4CAF50; font-size: 12px; font-weight: bold; margin-left: 4px;"
        if step_index == self._current_step:
            return "color: #2196F3; font-size: 12px; font-weight: bold; margin-left: 4px;"
        return "color: #999; font-size: 12px; margin-left: 4px;"

    def set_current_step(self, step: int) -> None:
        """Set the current active step (0-3)."""
        self._current_step = step
        # Update all styles
        for i in range(len(self.STEPS)):
            self._circle_labels[i].setStyleSheet(self._circle_style(i))
            self._step_labels[i].setStyleSheet(self._label_style(i))

        # Update connector lines
        for i in range(len(self._line_labels)):
            if i < self._current_step:
                self._line_labels[i].setStyleSheet("background-color: #4CAF50;")
            else:
                self._line_labels[i].setStyleSheet("background-color: #e0e0e0;")


class MainWindow(QWidget if HAS_PYSIDE6 else object):
    """Main application window with step-based workflow.

    Contains:
    - Step indicator at the top
    - QStackedWidget for page switching
    - Navigation buttons at the bottom
    """

    # Page indices
    PAGE_SCAN = 0
    PAGE_REVIEW = 1
    PAGE_TARGET = 2
    PAGE_EXECUTE = 3

    def __init__(self, parent=None):
        if not HAS_PYSIDE6:
            return
        super().__init__(parent)
        self._scan_result: Optional[ScanResult] = None
        self._current_page = self.PAGE_SCAN
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the main window UI."""
        self.setWindowTitle(f"{APP_NAME_ZH} / {APP_NAME}")
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.resize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Step indicator
        self._step_indicator = StepIndicator()
        main_layout.addWidget(self._step_indicator)

        # Separator
        sep = QLabel("")
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #e0e0e0;")
        main_layout.addWidget(sep)

        # Page stack
        self._stack = QStackedWidget()
        self._scan_page = ScanPage()
        self._review_page = ReviewPage()
        self._target_page = TargetPage()
        self._execute_page = ExecutePage()

        self._stack.addWidget(self._scan_page)
        self._stack.addWidget(self._review_page)
        self._stack.addWidget(self._target_page)
        self._stack.addWidget(self._execute_page)

        main_layout.addWidget(self._stack, 1)

        # Separator
        sep2 = QLabel("")
        sep2.setFixedHeight(1)
        sep2.setStyleSheet("background-color: #e0e0e0;")
        main_layout.addWidget(sep2)

        # Navigation bar
        nav_bar = QWidget()
        nav_bar.setObjectName("navBar")
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(16, 8, 16, 8)

        self._back_button = QPushButton("上一步 / Back")
        self._back_button.setObjectName("secondaryButton")
        self._back_button.clicked.connect(self._on_back)
        self._back_button.setVisible(False)
        nav_layout.addWidget(self._back_button)

        nav_layout.addStretch()

        self._next_button = QPushButton("下一步 / Next")
        self._next_button.setObjectName("primaryButton")
        self._next_button.clicked.connect(self._on_next)
        self._next_button.setVisible(False)
        nav_layout.addWidget(self._next_button)

        self._cancel_button = QPushButton("取消 / Cancel")
        self._cancel_button.setObjectName("secondaryButton")
        self._cancel_button.clicked.connect(self._on_cancel)
        nav_layout.addWidget(self._cancel_button)

        main_layout.addWidget(nav_bar)

        # Connect page signals
        self._scan_page.scan_completed.connect(self._on_scan_completed)

    def _navigate_to(self, page: int) -> None:
        """Navigate to a specific page."""
        self._current_page = page
        self._stack.setCurrentIndex(page)
        self._step_indicator.set_current_step(page)

        # Update navigation buttons
        self._back_button.setVisible(page > self.PAGE_SCAN)
        self._next_button.setVisible(page < self.PAGE_EXECUTE)

        # Update next button text
        if page == self.PAGE_REVIEW:
            self._next_button.setText("下一步：选择目标 / Next: Choose Target")
        elif page == self.PAGE_TARGET:
            self._next_button.setText("下一步：执行迁移 / Next: Execute")
        else:
            self._next_button.setText("下一步 / Next")

    def _on_scan_completed(self, result: ScanResult) -> None:
        """Handle scan completion from scan page."""
        self._scan_result = result
        self._next_button.setVisible(True)
        self._next_button.setText("下一步：审查文件 / Next: Review Files")

    def _on_back(self) -> None:
        """Handle the Back button click."""
        if self._current_page > self.PAGE_SCAN:
            self._navigate_to(self._current_page - 1)

    def _on_next(self) -> None:
        """Handle the Next button click."""
        if self._current_page == self.PAGE_SCAN:
            # Move to review page
            if self._scan_result:
                self._review_page.load_scan_result(self._scan_result)
                self._navigate_to(self.PAGE_REVIEW)

        elif self._current_page == self.PAGE_REVIEW:
            # Move to target page
            selected_files = self._review_page.get_selected_files()
            if not selected_files:
                return  # No files selected
            selected_size = self._review_page.get_selected_size()
            self._target_page.set_required_size(selected_size)
            self._navigate_to(self.PAGE_TARGET)

        elif self._current_page == self.PAGE_TARGET:
            # Move to execute page
            target = self._target_page.get_selected_target()
            if target is None:
                return  # No target selected

            selected_files = self._review_page.get_selected_files()
            selected_size = self._review_page.get_selected_size()

            self._execute_page.setup(selected_files, target, selected_size)
            self._navigate_to(self.PAGE_EXECUTE)

    def _on_cancel(self) -> None:
        """Handle the Cancel button click."""
        if HAS_PYSIDE6:
            from PySide6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self,
                "确认退出 / Confirm Exit",
                "确定要退出PC迁移助手吗？/ Are you sure you want to exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.close()
