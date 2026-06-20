"""ScanPage — Step 1: Scan for personal files."""

from __future__ import annotations

import threading
from typing import List, Optional

import os
import webbrowser

from src.constants import FileCategory, ScanState
from src.models.migration_result import MigrationResult
from src.models.scan_result import ScanResult
from src.scanners.file_classifier import FileClassifier
from src.scanners.scan_worker import ScanWorker
from src.targets.drive_detector import DriveDetector
from src.utils.human_size import format_size
from src.utils.logger import setup_logging
from src.utils.report_generator import ReportGenerator

logger = setup_logging()

try:
    from PySide6.QtCore import Qt, QUrl, Signal
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import (
        QCheckBox,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QProgressBar,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False


class ScanPage(QWidget if HAS_PYSIDE6 else object):
    """Step 1 page: Select drives and scan for personal files.

    Features:
    - Drive selection checkboxes
    - Start/Cancel scan buttons
    - Progress bar with current path
    - Scan result summary
    """

    # Signals
    scan_completed = Signal(object)  # ScanResult
    scan_started = Signal()

    def __init__(self, parent=None):
        if not HAS_PYSIDE6:
            return
        super().__init__(parent)
        self._scan_thread: Optional[threading.Thread] = None
        self._scan_worker: Optional[ScanWorker] = None
        self._classifier: Optional[FileClassifier] = None
        self._drive_checkboxes: List[QCheckBox] = []
        self._last_report_path: Optional[str] = None
        self._setup_ui()
        self._detect_drives()

    def _setup_ui(self) -> None:
        """Build the scan page UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(32, 24, 32, 24)

        # Title
        title = QLabel("扫描个人文件 / Scan Personal Files")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        # Description
        desc = QLabel(
            "选择要扫描的磁盘，然后点击开始扫描。扫描将发现不属于系统或应用程序的个人文档。\n"
            "Select drives to scan, then click Start Scan. The scan will discover "
            "personal documents that are not system or application files."
        )
        desc.setObjectName("pageDescription")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Drive selection group
        drive_group_label = QLabel("选择扫描磁盘 / Select Drives to Scan")
        drive_group_label.setStyleSheet("font-weight: bold; font-size: 14px; margin-top: 8px;")
        layout.addWidget(drive_group_label)

        self._drive_layout = QHBoxLayout()
        self._drive_layout.setSpacing(16)
        layout.addLayout(self._drive_layout)

        # Scan controls
        controls_layout = QHBoxLayout()

        self._start_button = QPushButton("开始扫描 / Start Scan")
        self._start_button.setObjectName("primaryButton")
        self._start_button.clicked.connect(self._on_start_scan)
        controls_layout.addWidget(self._start_button)

        self._cancel_button = QPushButton("取消扫描 / Cancel Scan")
        self._cancel_button.setObjectName("dangerButton")
        self._cancel_button.clicked.connect(self._on_cancel_scan)
        self._cancel_button.setVisible(False)
        controls_layout.addWidget(self._cancel_button)

        controls_layout.addStretch()
        layout.addLayout(controls_layout)

        # Progress section
        self._progress_frame = QFrame()
        self._progress_frame.setVisible(False)
        progress_layout = QVBoxLayout(self._progress_frame)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedHeight(20)
        progress_layout.addWidget(self._progress_bar)

        self._status_label = QLabel("准备扫描 / Ready to scan")
        self._status_label.setStyleSheet("color: #666; font-size: 12px;")
        progress_layout.addWidget(self._status_label)

        self._path_label = QLabel("")
        self._path_label.setStyleSheet("color: #888; font-size: 11px;")
        self._path_label.setWordWrap(True)
        progress_layout.addWidget(self._path_label)

        layout.addWidget(self._progress_frame)

        # Summary section (hidden until scan completes)
        self._summary_frame = QFrame()
        self._summary_frame.setObjectName("summaryCard")
        self._summary_frame.setVisible(False)
        summary_layout = QGridLayout(self._summary_frame)

        # Summary cards
        self._total_files_label = QLabel("0")
        self._total_files_label.setObjectName("summaryValue")
        summary_layout.addWidget(self._total_files_label, 0, 0)
        files_desc = QLabel("发现文件 / Files Found")
        files_desc.setObjectName("summaryLabel")
        summary_layout.addWidget(files_desc, 1, 0)

        self._total_size_label = QLabel("0 B")
        self._total_size_label.setObjectName("summaryValue")
        summary_layout.addWidget(self._total_size_label, 0, 1)
        size_desc = QLabel("总大小 / Total Size")
        size_desc.setObjectName("summaryLabel")
        summary_layout.addWidget(size_desc, 1, 1)

        self._errors_label = QLabel("0")
        self._errors_label.setObjectName("summaryValue")
        summary_layout.addWidget(self._errors_label, 0, 2)
        errors_desc = QLabel("跳过目录 / Skipped Dirs")
        errors_desc.setObjectName("summaryLabel")
        summary_layout.addWidget(errors_desc, 1, 2)

        self._duration_label = QLabel("0秒 / 0s")
        self._duration_label.setObjectName("summaryValue")
        summary_layout.addWidget(self._duration_label, 0, 3)
        duration_desc = QLabel("扫描用时 / Scan Duration")
        duration_desc.setObjectName("summaryLabel")
        summary_layout.addWidget(duration_desc, 1, 3)

        # Category breakdown
        self._category_label = QLabel("")
        self._category_label.setStyleSheet("font-size: 12px; color: #555; margin-top: 8px;")
        self._category_label.setWordWrap(True)
        summary_layout.addWidget(self._category_label, 2, 0, 1, 4)

        # Preview report button
        self._report_button = QPushButton("📋 查看报告 / View Report")
        self._report_button.setObjectName("secondaryButton")
        self._report_button.clicked.connect(self._on_open_report)
        self._report_button.setVisible(False)
        summary_layout.addWidget(self._report_button, 3, 0, 1, 4)

        layout.addWidget(self._summary_frame)
        layout.addStretch()

    def _detect_drives(self) -> None:
        """Detect available drives and create checkboxes."""
        if not HAS_PYSIDE6:
            return

        # Clear existing checkboxes
        for cb in self._drive_checkboxes:
            self._drive_layout.removeWidget(cb)
            cb.deleteLater()
        self._drive_checkboxes.clear()

        detector = DriveDetector()
        drives = detector.detect_all()

        for drive in drives:
            cb = QCheckBox(f"{drive.display_name} ({format_size(drive.free_bytes)} 可用/Free)")
            cb.setProperty("drive_letter", drive.drive_letter)
            cb.setProperty("drive_path", drive.path)

            # Default: check non-system drives
            if drive.drive_letter.upper() != "C:":
                cb.setChecked(True)

            self._drive_layout.addWidget(cb)
            self._drive_checkboxes.append(cb)

    def _get_selected_roots(self) -> List[str]:
        """Get the list of selected drive root paths."""
        roots = []
        for cb in self._drive_checkboxes:
            if cb.isChecked():
                path = cb.property("drive_path")
                if path:
                    roots.append(path)
        return roots

    def _on_start_scan(self) -> None:
        """Handle the Start Scan button click."""
        roots = self._get_selected_roots()
        if not roots:
            self._status_label.setText("请至少选择一个磁盘 / Please select at least one drive")
            return

        # Initialize classifier
        if self._classifier is None:
            self._classifier = FileClassifier()

        # Create worker
        self._scan_worker = ScanWorker(self._classifier, roots)

        # Create thread
        from PySide6.QtCore import QThread
        self._scan_thread_obj = QThread()
        self._scan_worker.moveToThread(self._scan_thread_obj)

        # Connect signals
        self._scan_thread_obj.started.connect(self._scan_worker.run)
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.completed.connect(self._on_scan_completed)
        self._scan_worker.error.connect(self._on_scan_error)
        self._scan_worker.completed.connect(self._scan_thread_obj.quit)
        self._scan_worker.error.connect(self._scan_thread_obj.quit)

        # Update UI
        self._start_button.setVisible(False)
        self._cancel_button.setVisible(True)
        self._progress_frame.setVisible(True)
        self._summary_frame.setVisible(False)
        self._status_label.setText("正在扫描 / Scanning...")
        self._progress_bar.setValue(0)

        # Start scan
        self._scan_thread_obj.start()
        self.scan_started.emit()

    def _on_cancel_scan(self) -> None:
        """Handle the Cancel Scan button click."""
        if self._scan_worker:
            self._scan_worker.cancel()
        self._status_label.setText("正在取消 / Cancelling...")
        self._cancel_button.setEnabled(False)

    def _on_scan_progress(self, scanned_dirs: int, files_found: int,
                          progress_pct: int, estimated_total: int) -> None:
        """Handle scan progress updates with percentage."""
        # Update progress bar with actual percentage
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(progress_pct)
        self._progress_bar.setFormat(f"{progress_pct}%")

        self._status_label.setText(
            f"已扫描 {scanned_dirs:,}/{estimated_total:,} 个目录，发现 {files_found:,} 个文件 / "
            f"Scanned {scanned_dirs:,}/{estimated_total:,} dirs, found {files_found:,} files"
        )

    def _on_scan_completed(self, result: ScanResult) -> None:
        """Handle scan completion."""
        self._start_button.setVisible(True)
        self._cancel_button.setVisible(False)
        self._progress_frame.setVisible(False)
        self._cancel_button.setEnabled(True)

        if result.state == ScanState.CANCELLED:
            self._status_label.setText("扫描已取消 / Scan cancelled")
            return

        # Show summary
        self._summary_frame.setVisible(True)
        self._total_files_label.setText(f"{result.file_count:,}")
        self._total_size_label.setText(format_size(result.total_size))
        self._errors_label.setText(f"{result.error_count:,}")
        self._duration_label.setText(f"{result.scan_duration:.1f}秒 / s")

        # Permission error hint: if many errors, suggest admin mode
        if result.error_count > 10:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self,
                "权限提示 / Permission Hint",
                f"扫描中有 {result.error_count} 个目录因权限不足被跳过。\n"
                f"如果需要扫描更多文件，请右键本程序选择\"以管理员身份运行\"。\n\n"
                f"{result.error_count} directories were skipped due to insufficient permissions.\n"
                f"To scan more files, right-click this program and select \"Run as administrator\".",
            )

        # Category breakdown
        cat_lines = []
        for category in FileCategory:
            count = result.category_counts.get(category, 0)
            size = result.category_sizes.get(category, 0)
            if count > 0:
                display_name, _ = {
                    FileCategory.DOCUMENTS: ("文档", "Docs"),
                    FileCategory.PHOTOS: ("照片", "Photos"),
                    FileCategory.VIDEOS: ("视频", "Videos"),
                    FileCategory.MUSIC: ("音乐", "Music"),
                    FileCategory.ARCHIVES: ("压缩包", "Archives"),
                    FileCategory.BROWSER_DATA: ("浏览器数据", "Browser"),
                    FileCategory.OTHER: ("其他", "Other"),
                }.get(category, (category.value, category.value))
                cat_lines.append(f"{display_name}/{display_name}: {count:,} 文件/files ({format_size(size)})")

        self._category_label.setText("  |  ".join(cat_lines))

        # Generate preview report
        self._last_report_path = None
        try:
            reports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "reports")
            reports_dir = os.path.normpath(reports_dir)
            migration_result = MigrationResult.from_scan_result(result)
            generator = ReportGenerator()
            _, html_path = generator.generate(migration_result, reports_dir)
            self._last_report_path = html_path
            self._report_button.setVisible(True)
        except Exception as e:
            logger.warning(f"Failed to generate preview report: {e}")

        # Emit signal
        self.scan_completed.emit(result)

    def _on_open_report(self) -> None:
        """Open the preview report in the default browser."""
        if self._last_report_path and os.path.exists(self._last_report_path):
            try:
                if HAS_PYSIDE6:
                    from PySide6.QtCore import QUrl
                    from PySide6.QtGui import QDesktopServices
                    QDesktopServices.openUrl(QUrl.fromLocalFile(self._last_report_path))
                else:
                    webbrowser.open(f"file://{self._last_report_path}")
            except Exception as e:
                logger.warning(f"Failed to open report: {e}")

    def _on_scan_error(self, error_msg: str) -> None:
        """Handle scan error."""
        self._start_button.setVisible(True)
        self._cancel_button.setVisible(False)
        self._cancel_button.setEnabled(True)
        self._status_label.setText(f"扫描出错 / Scan error: {error_msg}")

    def get_scan_result(self) -> Optional[ScanResult]:
        """Get the last scan result."""
        if self._scan_worker:
            # The result is emitted via signal, stored by main window
            pass
        return None
