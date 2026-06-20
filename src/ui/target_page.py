"""TargetPage — Step 3: Choose migration destination."""

from __future__ import annotations

from typing import List, Optional

from src.models.migration_target import MigrationTarget
from src.targets.drive_detector import DriveDetector
from src.ui.widgets.drive_list_widget import DriveListWidget
from src.utils.human_size import format_size

try:
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import (
        QFileDialog,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False


class TargetPage(QWidget if HAS_PYSIDE6 else object):
    """Step 3 page: Choose migration target (USB drive, external disk, etc.).

    Features:
    - List of detected removable/network drives
    - Custom path input
    - Space availability check
    """

    def __init__(self, parent=None):
        if not HAS_PYSIDE6:
            return
        super().__init__(parent)
        self._selected_target: Optional[MigrationTarget] = None
        self._required_size: int = 0
        self._last_drive_letters: List[str] = []  # For change detection
        self._setup_ui()
        self._detect_drives()

        # Auto-refresh timer: poll drives every 3 seconds
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._auto_refresh_drives)
        self._refresh_timer.start(3000)

    def _setup_ui(self) -> None:
        """Build the target page UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(32, 24, 32, 24)

        # Title
        title = QLabel("选择迁移目标 / Choose Migration Target")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        # Description
        desc = QLabel(
            "选择迁移文件的目标位置，例如U盘或外接硬盘。\n"
            "Select a destination for your migration files, such as a USB drive or external hard disk."
        )
        desc.setObjectName("pageDescription")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Drive list section
        drive_label = QLabel("检测到的驱动器 / Detected Drives")
        drive_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(drive_label)

        # Refresh button
        refresh_layout = QHBoxLayout()
        self._refresh_button = QPushButton("刷新驱动器列表 / Refresh Drive List")
        self._refresh_button.setObjectName("secondaryButton")
        self._refresh_button.clicked.connect(self._detect_drives)
        refresh_layout.addWidget(self._refresh_button)
        refresh_layout.addStretch()
        layout.addLayout(refresh_layout)

        self._drive_list = DriveListWidget()
        self._drive_list.target_selected.connect(self._on_drive_selected)
        layout.addWidget(self._drive_list, 1)

        # Custom path section
        custom_label = QLabel("自定义路径 / Custom Path")
        custom_label.setStyleSheet("font-weight: bold; font-size: 14px; margin-top: 16px;")
        layout.addWidget(custom_label)

        path_layout = QHBoxLayout()
        self._custom_path_input = QLineEdit()
        self._custom_path_input.setObjectName("searchInput")
        self._custom_path_input.setPlaceholderText(
            "输入自定义目标路径 / Enter custom destination path..."
        )
        self._custom_path_input.textChanged.connect(self._on_custom_path_changed)
        path_layout.addWidget(self._custom_path_input, 1)

        self._browse_button = QPushButton("浏览 / Browse")
        self._browse_button.setObjectName("secondaryButton")
        self._browse_button.clicked.connect(self._on_browse)
        path_layout.addWidget(self._browse_button)

        layout.addLayout(path_layout)

        # Warning label
        self._warning_label = QLabel("")
        self._warning_label.setObjectName("warningLabel")
        self._warning_label.setWordWrap(True)
        layout.addWidget(self._warning_label)

        # Space info
        self._space_label = QLabel("")
        self._space_label.setStyleSheet("font-size: 13px; color: #555;")
        layout.addWidget(self._space_label)

        layout.addStretch()

    def _detect_drives(self) -> None:
        """Detect and display available migration target drives."""
        if not HAS_PYSIDE6:
            return

        detector = DriveDetector()
        targets = detector.detect_migration_targets()
        self._drive_list.set_drives(targets)
        self._last_drive_letters = [t.drive_letter for t in targets]

    def _auto_refresh_drives(self) -> None:
        """Auto-refresh drive list when drives change (USB insertion/removal)."""
        if not HAS_PYSIDE6:
            return

        try:
            detector = DriveDetector()
            targets = detector.detect_migration_targets()
            current_letters = [t.drive_letter for t in targets]

            # Only update UI if drives actually changed
            if current_letters != self._last_drive_letters:
                # Preserve selection if the selected drive still exists
                was_selected = self._selected_target
                self._drive_list.set_drives(targets)
                self._last_drive_letters = current_letters

                # Re-select previously selected drive if it still exists
                if was_selected:
                    for t in targets:
                        if t.drive_letter == was_selected.drive_letter:
                            self._selected_target = t
                            break
        except Exception:
            # Silently ignore errors during auto-refresh
            pass

    def _on_drive_selected(self, target: MigrationTarget) -> None:
        """Handle drive selection."""
        self._selected_target = target
        self._custom_path_input.setText("")
        self._check_space()
        self._check_filesystem(target)

    def _on_custom_path_changed(self, text: str) -> None:
        """Handle custom path input changes."""
        if text.strip():
            self._selected_target = None  # Using custom path
            self._check_space()
        else:
            self._warning_label.setText("")

    def _on_browse(self) -> None:
        """Handle the Browse button click."""
        if not HAS_PYSIDE6:
            return

        path = QFileDialog.getExistingDirectory(
            self,
            "选择目标文件夹 / Select Destination Folder",
        )
        if path:
            self._custom_path_input.setText(path)

    def set_required_size(self, size: int) -> None:
        """Set the required space for the migration.

        Args:
            size: Required size in bytes.
        """
        self._required_size = size
        self._check_space()

    def get_selected_target(self) -> Optional[MigrationTarget]:
        """Get the currently selected migration target."""
        # If custom path is set, create a synthetic target
        custom_path = self._custom_path_input.text().strip()
        if custom_path:
            import os
            if os.path.isdir(custom_path):
                # Get disk space info for custom path
                from src.utils.win_utils import get_disk_free_space
                space_info = get_disk_free_space(custom_path)
                if space_info:
                    free, total, available = space_info
                    return MigrationTarget(
                        drive_letter=custom_path[:2] if len(custom_path) >= 2 else custom_path,
                        label=os.path.basename(custom_path) or custom_path,
                        drive_type=self._get_drive_type_for_path(custom_path),
                        total_bytes=total,
                        free_bytes=available,
                        path=custom_path,
                    )
                return MigrationTarget(
                    drive_letter="",
                    label=custom_path,
                    drive_type=self._get_drive_type_for_path(custom_path),
                    total_bytes=0,
                    free_bytes=0,
                    path=custom_path,
                )
        return self._selected_target

    def _get_drive_type_for_path(self, path: str):
        """Determine drive type for a given path."""
        from src.models.migration_target import DriveType
        from src.utils.win_utils import get_drive_type, DRIVE_FIXED, DRIVE_REMOVABLE, DRIVE_REMOTE
        if len(path) >= 2 and path[1] == ":":
            win_type = get_drive_type(path[:2])
            type_map = {
                DRIVE_REMOVABLE: DriveType.REMOVABLE,
                DRIVE_REMOTE: DriveType.NETWORK,
                DRIVE_FIXED: DriveType.LOCAL,
            }
            return type_map.get(win_type, DriveType.UNKNOWN)
        return DriveType.NETWORK  # Assume network for UNC paths

    def _check_space(self) -> None:
        """Check if the selected target has sufficient space."""
        target = self.get_selected_target()
        if target is None:
            self._warning_label.setText("请选择迁移目标 / Please select a migration target")
            self._space_label.setText("")
            return

        if self._required_size == 0:
            self._space_label.setText(
                f"目标可用空间 / Target free space: {format_size(target.free_bytes)}"
            )
            self._warning_label.setText("")
            return

        if target.has_sufficient_space(self._required_size):
            self._warning_label.setText("")
            self._space_label.setText(
                f"需要 / Required: {format_size(self._required_size)}  |  "
                f"可用 / Available: {format_size(target.free_bytes)}  ✓"
            )
        else:
            deficit = target.space_deficit(self._required_size)
            self._warning_label.setText(
                f"⚠ 目标空间不足！还需要 / Insufficient space! Need additional: {format_size(deficit)}"
            )
            self._space_label.setText(
                f"需要 / Required: {format_size(self._required_size)}  |  "
                f"可用 / Available: {format_size(target.free_bytes)}"
            )

    def _check_filesystem(self, target: MigrationTarget) -> None:
        """Check the target drive's file system and warn about limitations.

        Warns if the file system is FAT32 and selected files include
        files larger than 4 GB.
        """
        from src.utils.win_utils import has_file_size_limit, FAT32_MAX_FILE_SIZE

        has_limit, fs_name = has_file_size_limit(target.path)

        if fs_name:
            self._space_label.setText(
                self._space_label.text() +
                f"  |  文件系统 / FS: {fs_name}"
            )

        if has_limit:
            # Check if any selected files exceed FAT32 limit
            large_files = []
            # We don't have direct access to selected files here,
            # so show a general warning
            self._warning_label.setText(
                self._warning_label.text() +
                ("\n⚠ 目标盘为 FAT32 格式，单个文件不能超过 4 GB。"
                 "建议格式化为 NTFS 或 exFAT，或使用分卷压缩。"
                 " / Target is FAT32, single files cannot exceed 4 GB. "
                 "Consider reformatting to NTFS/exFAT or using split archives."
                 if not self._warning_label.text().startswith("⚠")
                 else "")
            )
