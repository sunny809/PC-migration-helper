"""PyInstaller build script for PC Migration Helper.

Usage:
    python scripts/build.py

This will create a distributable package in dist/ directory.
"""

import os
import sys
import subprocess


def _safe_print(msg: str) -> None:
    """Print with fallback encoding for Windows consoles that can't handle Unicode."""
    try:
        print(msg)
    except UnicodeEncodeError:
        # Replace unencodable characters with '?'
        safe = msg.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding)
        print(safe)


def build():
    """Build the application using PyInstaller."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)

    # Use ASCII-safe project name for PyInstaller to avoid encoding issues
    app_name = "PC-Migration-Helper"

    # PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        f"--name={app_name}",
        "--onedir",  # Create a directory (faster startup than --onefile)
        "--windowed",  # No console window
        "--noconfirm",  # Overwrite output directory
        "--clean",  # Clean cache
        "--strip",  # Strip debug symbols from binaries

        # Add data files
        f"--add-data={os.path.join('config', 'default_rules.yaml')}{os.pathsep}config",
        f"--add-data={os.path.join('src', 'ui', 'styles', 'theme.qss')}{os.pathsep}src/ui/styles",

        # Add assets directory
        f"--add-data={os.path.join('assets', 'icons')}{os.pathsep}assets/icons",
        f"--add-data={os.path.join('assets', 'i18n')}{os.pathsep}assets/i18n",

        # Hidden imports (PySide6 sometimes misses these)
        "--hidden-import=PySide6.QtWidgets",
        "--hidden-import=PySide6.QtCore",
        "--hidden-import=PySide6.QtGui",
        "--hidden-import=py7zr",
        "--hidden-import=YAML",

        # Exclude massive unused PySide6 modules (saves ~120MB)
        "--exclude-module=PySide6.QtWebEngine",
        "--exclude-module=PySide6.QtWebEngineCore",
        "--exclude-module=PySide6.QtWebEngineWidgets",
        "--exclude-module=PySide6.QtWebChannel",
        "--exclude-module=PySide6.QtQml",
        "--exclude-module=PySide6.QtQuick",
        "--exclude-module=PySide6.QtQuick3D",
        "--exclude-module=PySide6.QtQuickControls2",
        "--exclude-module=PySide6.QtBluetooth",
        "--exclude-module=PySide6.QtSensors",
        "--exclude-module=PySide6.QtPositioning",
        "--exclude-module=PySide6.QtDataVisualization",

        # Exclude other unused packages (these are often large)
        "--exclude-module=pandas",
        "--exclude-module=numpy",
        "--exclude-module=matplotlib",
        "--exclude-module=scipy",
        "--exclude-module=PIL",

        # Icon
        # f"--icon={os.path.join('assets', 'icons', 'app.ico')}",

        # UAC admin (optional, for scanning some protected directories)
        # "--uac-admin",

        # Entry point
        "main.py",
    ]

    _safe_print("Building PC Migration Helper with PyInstaller...")
    _safe_print(f"Project root: {project_root}")

    result = subprocess.run(cmd, cwd=project_root)

    dist_dir = os.path.join(project_root, 'dist', app_name)
    if result.returncode == 0:
        _safe_print("\nBuild successful!")
        _safe_print(f"Output directory: {dist_dir}")
    else:
        _safe_print("\nBuild failed!")
        sys.exit(result.returncode)


if __name__ == "__main__":
    build()
