"""ProgressWidget — composite progress display for scan and migration operations."""

from __future__ import annotations

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QHBoxLayout,
        QLabel,
        QProgressBar,
        QVBoxLayout,
        QWidget,
    )
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False

from src.utils.human_size import format_duration, format_size, format_speed


class ProgressWidget(QWidget if HAS_PYSIDE6 else object):
    """Composite widget showing operation progress.

    Includes:
    - Overall progress bar
    - Current file/path label
    - Speed label
    - ETA label
    - File count label
    """

    def __init__(self, parent=None):
        if not HAS_PYSIDE6:
            return
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the progress widget UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Overall progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(24)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 4px;
                text-align: center;
                font-size: 13px;
            }
            QProgressBar::chunk {
                background-color: #2196F3;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # Current file label
        self.current_label = QLabel("")
        self.current_label.setStyleSheet("color: #555; font-size: 12px;")
        self.current_label.setWordWrap(True)
        layout.addWidget(self.current_label)

        # Stats row: speed + ETA + file count
        stats_layout = QHBoxLayout()

        self.speed_label = QLabel("")
        self.speed_label.setStyleSheet("color: #666; font-size: 12px;")
        stats_layout.addWidget(self.speed_label)

        self.eta_label = QLabel("")
        self.eta_label.setStyleSheet("color: #666; font-size: 12px;")
        stats_layout.addWidget(self.eta_label)

        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color: #666; font-size: 12px;")
        stats_layout.addWidget(self.count_label)

        stats_layout.addStretch()
        layout.addLayout(stats_layout)

    def set_progress(self, value: int, text: str = "") -> None:
        """Set the progress bar value and optional text.

        Args:
            value: Progress percentage (0-100).
            text: Optional text to display on the progress bar.
        """
        if not HAS_PYSIDE6:
            return
        self.progress_bar.setValue(max(0, min(100, value)))
        if text:
            self.progress_bar.setFormat(text)

    def set_current_file(self, path: str) -> None:
        """Set the current file being processed.

        Args:
            path: File path (will be elided if too long).
        """
        if not HAS_PYSIDE6:
            return
        # Elide long paths
        metrics = self.current_label.fontMetrics()
        available_width = self.width() - 20
        if available_width > 0:
            elided = metrics.elidedText(path, Qt.TextElideMode.ElideMiddle, available_width)
        else:
            elided = path
        self.current_label.setText(f"正在处理 / Processing: {elided}")

    def set_speed(self, bytes_per_second: float) -> None:
        """Set the current processing speed.

        Args:
            bytes_per_second: Speed in bytes per second.
        """
        if not HAS_PYSIDE6:
            return
        self.speed_label.setText(f"速度 / Speed: {format_speed(bytes_per_second)}")

    def set_eta(self, seconds: float) -> None:
        """Set the estimated time remaining.

        Args:
            seconds: Estimated seconds remaining.
        """
        if not HAS_PYSIDE6:
            return
        self.eta_label.setText(f"剩余时间 / ETA: {format_duration(seconds)}")

    def set_file_count(self, done: int, total: int) -> None:
        """Set the file count display.

        Args:
            done: Number of files processed.
            total: Total number of files.
        """
        if not HAS_PYSIDE6:
            return
        self.count_label.setText(f"文件 / Files: {done:,} / {total:,}")

    def reset(self) -> None:
        """Reset all progress displays."""
        if not HAS_PYSIDE6:
            return
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("")
        self.current_label.setText("")
        self.speed_label.setText("")
        self.eta_label.setText("")
        self.count_label.setText("")
