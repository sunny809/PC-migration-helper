"""PyInstaller build script for PC Migration Helper.

Usage:
    python scripts/build.py

This will create a distributable package in dist/ directory.
"""

import os
import sys
import subprocess


def build():
    """Build the application using PyInstaller."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)

    # PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=PC迁移助手",
        "--onedir",  # Create a directory (faster startup than --onefile)
        "--windowed",  # No console window
        "--noconfirm",  # Overwrite output directory
        "--clean",  # Clean cache

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

        # Icon
        # f"--icon={os.path.join('assets', 'icons', 'app.ico')}",

        # UAC admin (optional, for scanning some protected directories)
        # "--uac-admin",

        # Entry point
        "main.py",
    ]

    print("Building PC Migration Helper with PyInstaller...")
    print(f"Project root: {project_root}")
    print(f"Command: {' '.join(cmd)}")

    result = subprocess.run(cmd, cwd=project_root)

    if result.returncode == 0:
        print("\n✓ Build successful!")
        print(f"Output directory: {os.path.join(project_root, 'dist', 'PC迁移助手')}")
    else:
        print("\n✗ Build failed!")
        sys.exit(result.returncode)


if __name__ == "__main__":
    build()
