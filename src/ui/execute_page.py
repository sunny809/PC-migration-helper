"""ExecutePage — Step 4: Execute migration (compress and copy)."""

from __future__ import annotations

import os
import time
from typing import Optional

from src.constants import MigrationFormat, MigrationState
from src.models.file_entry import FileEntry
from src.models.migration_config import MigrationConfig
from src.models.migration_target import MigrationTarget
from src.migration.migration_worker import MigrationWorker
from src.ui.widgets.progress_widget import ProgressWidget
from src.utils.human_size import format_duration, format_size

try:
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtWidgets import (
        QComboBox,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QSlider,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False


class ExecutePage(QWidget if HAS_PYSIDE6 else object):
    """Step 4 page: Execute the migration operation.

    Features:
    - Compression format selection (ZIP / 7z / Copy Only)
    - Compression level slider
    - Start / Pause / Cancel buttons
    - Progress display with speed and ETA
    - Completion summary
    """

    # Signals
    migration_completed = Signal(dict)  # result dict

    def __init__(self, parent=None):
        if not HAS_PYSIDE6:
            return
        super().__init__(parent)
        self._worker: Optional[MigrationWorker] = None
        self._config: Optional[MigrationConfig] = None
        self._is_running = False
        self._is_paused = False
        self._start_time = 0.0
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the execute page UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(32, 24, 32, 24)

        # Title
        title = QLabel("执行迁移 / Execute Migration")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        # Description
        self._desc_label = QLabel(
            "选择压缩格式和级别，然后开始迁移。\n"
            "Select compression format and level, then start migration."
        )
        self._desc_label.setObjectName("pageDescription")
        self._desc_label.setWordWrap(True)
        layout.addWidget(self._desc_label)

        # Settings section
        settings_layout = QHBoxLayout()

        # Format selection
        format_label = QLabel("压缩格式 / Format:")
        format_label.setStyleSheet("font-weight: bold;")
        settings_layout.addWidget(format_label)

        self._format_combo = QComboBox()
        self._format_combo.addItem("7z (推荐/Recommended)", MigrationFormat.SEVEN_ZIP.value)
        self._format_combo.addItem("ZIP", MigrationFormat.ZIP.value)
        self._format_combo.addItem("不压缩直接复制 / Copy Only", MigrationFormat.COPY_ONLY.value)
        self._format_combo.currentIndexChanged.connect(self._on_format_changed)
        settings_layout.addWidget(self._format_combo)

        settings_layout.addSpacing(24)

        # Compression level
        self._level_label = QLabel("压缩级别 / Level:")
        self._level_label.setStyleSheet("font-weight: bold;")
        settings_layout.addWidget(self._level_label)

        self._level_slider = QSlider(Qt.Orientation.Horizontal)
        self._level_slider.setRange(1, 9)
        self._level_slider.setValue(5)
        self._level_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._level_slider.setTickInterval(1)
        self._level_slider.valueChanged.connect(self._on_level_changed)
        settings_layout.addWidget(self._level_slider)

        self._level_value_label = QLabel("5 - 标准/Standard")
        self._level_value_label.setFixedWidth(140)
        settings_layout.addWidget(self._level_value_label)

        settings_layout.addStretch()
        layout.addLayout(settings_layout)

        # Migration summary
        self._summary_label = QLabel("")
        self._summary_label.setStyleSheet(
            "background-color: #f0f7ff; padding: 8px 12px; "
            "border-radius: 4px; font-size: 13px; color: #333;"
        )
        layout.addWidget(self._summary_label)

        # Control buttons
        controls_layout = QHBoxLayout()

        self._start_button = QPushButton("开始迁移 / Start Migration")
        self._start_button.setObjectName("successButton")
        self._start_button.clicked.connect(self._on_start)
        controls_layout.addWidget(self._start_button)

        self._pause_button = QPushButton("暂停 / Pause")
        self._pause_button.setObjectName("secondaryButton")
        self._pause_button.clicked.connect(self._on_pause)
        self._pause_button.setVisible(False)
        controls_layout.addWidget(self._pause_button)

        self._cancel_button = QPushButton("取消 / Cancel")
        self._cancel_button.setObjectName("dangerButton")
        self._cancel_button.clicked.connect(self._on_cancel)
        self._cancel_button.setVisible(False)
        controls_layout.addWidget(self._cancel_button)

        controls_layout.addStretch()
        layout.addLayout(controls_layout)

        # Progress widget
        self._progress_widget = ProgressWidget()
        self._progress_widget.setVisible(False)
        layout.addWidget(self._progress_widget)

        # Completion section (hidden until done)
        self._completion_frame = QWidget()
        self._completion_frame.setVisible(False)
        completion_layout = QVBoxLayout(self._completion_frame)

        self._completion_label = QLabel("迁移完成！/ Migration Complete! ✓")
        self._completion_label.setStyleSheet(
            "font-size: 20px; font-weight: bold; color: #4CAF50;"
        )
        completion_layout.addWidget(self._completion_label)

        self._completion_details = QLabel("")
        self._completion_details.setStyleSheet("font-size: 13px; color: #555;")
        self._completion_details.setWordWrap(True)
        completion_layout.addWidget(self._completion_details)

        self._open_folder_button = QPushButton("打开目标文件夹 / Open Target Folder")
        self._open_folder_button.setObjectName("secondaryButton")
        self._open_folder_button.clicked.connect(self._on_open_folder)
        completion_layout.addWidget(self._open_folder_button)

        # Error details (hidden unless there are errors)
        self._error_details_label = QLabel("错误详情 / Error Details:")
        self._error_details_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #f44336; margin-top: 8px;")
        self._error_details_label.setVisible(False)
        completion_layout.addWidget(self._error_details_label)

        self._error_text = QTextEdit()
        self._error_text.setReadOnly(True)
        self._error_text.setMaximumHeight(120)
        self._error_text.setStyleSheet(
            "background-color: #fff3f3; border: 1px solid #ffcdd2; "
            "border-radius: 4px; font-size: 12px; color: #c62828; padding: 4px;"
        )
        self._error_text.setVisible(False)
        completion_layout.addWidget(self._error_text)

        layout.addWidget(self._completion_frame)
        layout.addStretch()

    def setup(self, selected_files: list, target: MigrationTarget,
              estimated_size: int) -> None:
        """Configure the execute page with migration details.

        Args:
            selected_files: List of FileEntry objects to migrate.
            target: Selected migration target.
            estimated_size: Estimated output size in bytes.
        """
        if not HAS_PYSIDE6:
            return

        self._config = MigrationConfig(
            selected_files=selected_files,
            target=target,
        )

        self._summary_label.setText(
            f"文件 / Files: {len(selected_files):,}  |  "
            f"大小 / Size: {format_size(sum(f.size for f in selected_files))}  |  "
            f"目标 / Target: {target.display_name} ({format_size(target.free_bytes)} 可用/Free)"
        )

        # Reset UI
        self._progress_widget.setVisible(False)
        self._completion_frame.setVisible(False)
        self._start_button.setVisible(True)
        self._pause_button.setVisible(False)
        self._cancel_button.setVisible(False)
        self._is_running = False
        self._is_paused = False

    def _on_format_changed(self, index: int) -> None:
        """Handle compression format change."""
        format_value = self._format_combo.currentData()
        # Disable level slider for Copy Only
        is_copy_only = format_value == MigrationFormat.COPY_ONLY.value
        self._level_slider.setEnabled(not is_copy_only)
        self._level_label.setEnabled(not is_copy_only)

    def _on_level_changed(self, value: int) -> None:
        """Handle compression level change."""
        level_names = {
            1: "快速/Fast",
            2: "较快/Faster",
            3: "较快/Faster",
            4: "标准/Standard",
            5: "标准/Standard",
            6: "较高/Higher",
            7: "较高/Higher",
            8: "最大/Maximum",
            9: "最大/Maximum",
        }
        name = level_names.get(value, str(value))
        self._level_value_label.setText(f"{value} - {name}")

    def _on_start(self) -> None:
        """Handle the Start Migration button click."""
        if self._config is None:
            return

        # Update config from UI
        format_value = self._format_combo.currentData()
        self._config.output_format = MigrationFormat(format_value)
        self._config.compression_level = self._level_slider.value()

        # Create worker
        self._worker = MigrationWorker(self._config)

        # Create thread
        from PySide6.QtCore import QThread
        self._thread = QThread()
        self._worker.moveToThread(self._thread)

        # Connect signals
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_migration_progress)
        self._worker.speed_updated.connect(self._on_speed_updated)
        self._worker.completed.connect(self._on_migration_completed)
        self._worker.error.connect(self._on_migration_error)
        self._worker.completed.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)

        # Update UI
        self._start_button.setVisible(False)
        self._pause_button.setVisible(True)
        self._cancel_button.setVisible(True)
        self._progress_widget.setVisible(True)
        self._completion_frame.setVisible(False)
        self._format_combo.setEnabled(False)
        self._level_slider.setEnabled(False)
        self._is_running = True
        self._start_time = time.time()

        # Start
        self._thread.start()

    def _on_pause(self) -> None:
        """Handle the Pause/Resume button click."""
        if self._worker is None:
            return

        if self._is_paused:
            self._worker.resume()
            self._is_paused = False
            self._pause_button.setText("暂停 / Pause")
        else:
            self._worker.pause()
            self._is_paused = True
            self._pause_button.setText("继续 / Resume")

    def _on_cancel(self) -> None:
        """Handle the Cancel button click."""
        if self._worker:
            self._worker.cancel()
        self._cancel_button.setEnabled(False)

    def _on_migration_progress(self, files_done: int, total_files: int,
                               bytes_done: int, current_path: str) -> None:
        """Handle migration progress updates."""
        if total_files > 0:
            progress_pct = int(files_done / total_files * 100)
            self._progress_widget.set_progress(progress_pct)
        self._progress_widget.set_current_file(current_path)
        self._progress_widget.set_file_count(files_done, total_files)

        # Estimate ETA
        if self._start_time > 0 and bytes_done > 0:
            elapsed = time.time() - self._start_time
            if elapsed > 0:
                total_bytes = sum(f.size for f in self._config.selected_files) if self._config else 0
                if total_bytes > 0:
                    rate = bytes_done / elapsed
                    remaining_bytes = total_bytes - bytes_done
                    if rate > 0:
                        eta = remaining_bytes / rate
                        self._progress_widget.set_eta(eta)

    def _on_speed_updated(self, bytes_per_second: float) -> None:
        """Handle speed update."""
        self._progress_widget.set_speed(bytes_per_second)

    def _on_migration_completed(self, result: dict) -> None:
        """Handle migration completion."""
        self._is_running = False
        self._pause_button.setVisible(False)
        self._cancel_button.setVisible(False)
        self._progress_widget.setVisible(False)
        self._completion_frame.setVisible(True)

        # Show completion details
        duration = result.get("duration", 0)
        files_processed = result.get("files_processed", 0)
        bytes_processed = result.get("bytes_processed", 0)
        errors = result.get("errors", [])
        verify_failures = result.get("verify_failures", [])

        # Completion status
        has_errors = len(errors) > 0
        has_verify_failures = len(verify_failures) > 0

        if has_verify_failures:
            self._completion_label.setText("⚠ 迁移完成，但校验发现问题 / Migration Complete with Verification Issues")
            self._completion_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #FF9800;")
        elif has_errors:
            self._completion_label.setText("⚠ 迁移完成，但有错误 / Migration Complete with Errors")
            self._completion_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #FF9800;")
        else:
            self._completion_label.setText("✅ 迁移完成！/ Migration Complete!")
            self._completion_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #4CAF50;")

        details = (
            f"处理文件 / Files processed: {files_processed:,}\n"
            f"数据量 / Data: {format_size(bytes_processed)}\n"
            f"用时 / Duration: {format_duration(duration)}\n"
            f"输出 / Output: {result.get('output_path', result.get('target_dir', 'N/A'))}"
        )
        if errors:
            details += f"\n❌ 错误 / Errors: {len(errors)}"
        if verify_failures:
            details += f"\n⚠ 校验失败 / Verify failures: {len(verify_failures)}"

        self._completion_details.setText(details)
        self._output_path = result.get("output_path", result.get("target_dir", ""))

        # Show error details if any
        all_errors = errors + verify_failures
        if all_errors:
            self._error_details_label.setVisible(True)
            self._error_text.setVisible(True)
            # Limit to first 50 errors to avoid UI lag
            display_errors = all_errors[:50]
            error_text = "\n".join(display_errors)
            if len(all_errors) > 50:
                error_text += f"\n... 还有 {len(all_errors) - 50} 项 / ... and {len(all_errors) - 50} more"
            self._error_text.setPlainText(error_text)
        else:
            self._error_details_label.setVisible(False)
            self._error_text.setVisible(False)

        self.migration_completed.emit(result)

    def _on_migration_error(self, error_msg: str) -> None:
        """Handle migration error."""
        self._is_running = False
        self._pause_button.setVisible(False)
        self._cancel_button.setVisible(False)
        self._progress_widget.set_progress(0)
        self._desc_label.setText(
            f"迁移出错 / Migration error: {error_msg}"
        )

    def _on_open_folder(self) -> None:
        """Open the target folder in the file explorer."""
        if hasattr(self, '_output_path') and self._output_path:
            if os.name == "nt":
                os.startfile(self._output_path)  # type: ignore[attr-defined]
            elif os.name == "posix":
                import subprocess
                subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", self._output_path])
